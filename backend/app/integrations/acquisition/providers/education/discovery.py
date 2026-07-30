from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from app.integrations.acquisition.dto import AcquisitionDocument, JobSpec
from app.integrations.acquisition.provider import AcquisitionProvider
from app.integrations.acquisition.storage import AcquisitionStorage
from app.integrations.gk_http import FetchResult, get as http_get

_SEARCH_FILE_EXTENSIONS = (".pdf", ".doc", ".docx", ".zip", ".xml", ".rss", ".txt")
_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js",
    ".woff", ".woff2", ".ico", ".mp4", ".mp3",
)


def _safe_provider_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "education"


def _source_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:40]


def _filename(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or _source_id(url)[:16]
    lower = name.lower()
    if "." in name:
        return name
    if "pdf" in content_type:
        return name + ".pdf"
    if "wordprocessingml" in content_type or "msword" in content_type:
        return name + ".docx"
    if "xml" in content_type or lower.endswith(".rss"):
        return name + ".xml"
    if "zip" in content_type:
        return name + ".zip"
    if "text/plain" in content_type:
        return name + ".txt"
    return name + ".html"


def _document_type_from(url: str, content_type: str) -> str:
    lower = url.lower()
    ct = content_type.lower()
    if lower.endswith(".pdf") or "pdf" in ct:
        return "pdf"
    if lower.endswith(".docx") or "wordprocessingml" in ct or "msword" in ct:
        return "docx"
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")) or ct.startswith("image/"):
        return "image"
    if lower.endswith(".zip") or "zip" in ct:
        return "zip"
    if lower.endswith(".xml") or "xml" in ct:
        return "xml"
    if lower.endswith(".txt") or "text/plain" in ct:
        return "txt"
    return "html"


class EducationDiscoveryProvider(AcquisitionProvider):
    source_kind = "website"

    def __init__(self, provider_name: str, label: str):
        self.name = provider_name
        self.label = label

    def discover(self) -> Iterable[AcquisitionDocument]:
        raise NotImplementedError

    def fetch(self, document: AcquisitionDocument) -> AcquisitionDocument:
        result = http_get(document.source_url)
        if not result:
            raise RuntimeError(f"Fetch failed: {document.source_url}")
        filename = _filename(document.source_url, result.content_type.lower())
        path = AcquisitionStorage.save(document, result.content, filename, exam="education", year="")
        return AcquisitionDocument(
            provider=document.provider,
            source_id=document.source_id,
            source_url=document.source_url,
            document_type=_document_type_from(document.source_url, result.content_type),
            language=document.language,
            checksum=hashlib.sha256(result.content).hexdigest()[:32],
            metadata={**document.metadata, "content_type": result.content_type},
            local_file=str(path),
        )

    def validate(self, document: AcquisitionDocument) -> bool:
        return bool(document.local_file)

    def extract_metadata(self, document: AcquisitionDocument) -> dict:
        return {"source_kind": self.source_kind, **document.metadata}

    def create_job(self, **kwargs) -> JobSpec:
        return JobSpec(job_type="education_scrape", source="education_acquisition", payload=kwargs)

    def health(self) -> dict:
        return {"status": "ok"}

    def _doc(self, url: str, document_type: str = "unknown", metadata: dict | None = None) -> AcquisitionDocument:
        return AcquisitionDocument(
            provider=self.name,
            source_id=_source_id(url),
            source_url=url,
            document_type=document_type,
            metadata=metadata or {},
        )


class ManualUrlProvider(EducationDiscoveryProvider):
    source_kind = "manual_url"

    def __init__(self, urls: list[str]):
        super().__init__("education_manual_url", "Manual URL")
        self.urls = urls

    def discover(self) -> Iterable[AcquisitionDocument]:
        for url in self.urls:
            yield self._doc(url, metadata={"origin": "manual"})


class SitemapProvider(EducationDiscoveryProvider):
    source_kind = "sitemap"

    def __init__(self, roots: list[str]):
        super().__init__("education_sitemap", "Sitemap")
        self.roots = roots

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for root in self.roots:
            parsed = urlparse(root)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            for name in ("sitemap.xml", "sitemap_index.xml"):
                result = http_get(f"{origin}/{name}")
                if not result or not result.text:
                    continue
                for url in _parse_sitemap(result.text):
                    if url not in seen:
                        seen.add(url)
                        yield self._doc(url, metadata={"origin": "sitemap", "seed": root})


class WebsiteCrawlProvider(EducationDiscoveryProvider):
    source_kind = "website_crawl"

    def __init__(self, roots: list[str], max_pages: int):
        super().__init__("education_website_crawl", "Website Crawl")
        self.roots = roots
        self.max_pages = max_pages

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for root in self.roots:
            for url in _crawl(root, self.max_pages):
                if url not in seen:
                    seen.add(url)
                    yield self._doc(url, metadata={"origin": "crawl", "seed": root})


class RssProvider(EducationDiscoveryProvider):
    source_kind = "rss"

    def __init__(self, feeds: list[str]):
        super().__init__("education_rss", "RSS")
        self.feeds = feeds

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for feed in self.feeds:
            result = http_get(feed)
            if not result or not result.text:
                continue
            try:
                root = ET.fromstring(result.text)
            except ET.ParseError:
                continue
            for link in [el.text.strip() for el in root.iter() if el.tag.lower().endswith("link") and el.text]:
                if link.startswith("http") and link not in seen:
                    seen.add(link)
                    yield self._doc(link, metadata={"origin": "rss", "feed": feed})


class SearchResultProvider(EducationDiscoveryProvider):
    source_kind = "search"
    query_url_template = ""

    def __init__(self, provider_name: str, label: str, queries: list[str], max_results: int):
        super().__init__(provider_name, label)
        self.queries = queries
        self.max_results = max_results

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for query in self.queries:
            result = http_get(self.query_url_template.format(query=quote_plus(query)))
            if not result or not result.text:
                continue
            for url in self._extract_urls(result):
                if url.startswith("http") and url not in seen:
                    seen.add(url)
                    yield self._doc(url, metadata={"origin": "search", "query": query, "search_provider": self.label})
                if len(seen) >= self.max_results:
                    return

    def _extract_urls(self, result: FetchResult) -> list[str]:
        raise NotImplementedError


class DuckDuckGoProvider(SearchResultProvider):
    query_url_template = "https://duckduckgo.com/html/?q={query}"

    def __init__(self, queries: list[str], max_results: int):
        super().__init__("education_duckduckgo", "DuckDuckGo", queries, max_results)

    def _extract_urls(self, result: FetchResult) -> list[str]:
        soup = BeautifulSoup(result.text, "html.parser")
        urls: list[str] = []
        for link in soup.select("a.result__a"):
            href = link.get("href", "")
            if href:
                urls.append(href)
        return urls


class BingProvider(SearchResultProvider):
    query_url_template = "https://www.bing.com/search?q={query}"

    def __init__(self, queries: list[str], max_results: int):
        super().__init__("education_bing", "Bing", queries, max_results)

    def _extract_urls(self, result: FetchResult) -> list[str]:
        soup = BeautifulSoup(result.text, "html.parser")
        return [a.get("href", "") for a in soup.select("li.b_algo h2 a")]


class GoogleSearchProvider(SearchResultProvider):
    query_url_template = "https://www.google.com/search?q={query}&hl=en"

    def __init__(self, queries: list[str], max_results: int):
        super().__init__("education_google", "Google", queries, max_results)

    def _extract_urls(self, result: FetchResult) -> list[str]:
        soup = BeautifulSoup(result.text, "html.parser")
        urls: list[str] = []
        for link in soup.select("a[href^='/url?']"):
            href = link.get("href", "")
            if not href:
                continue
            qs = parse_qs(urlparse(href).query)
            target = qs.get("q", [""])[0]
            if target.startswith("http"):
                urls.append(target)
        return urls


class DocumentDiscoveryProvider(EducationDiscoveryProvider):
    source_kind = "document_discovery"

    def __init__(self, roots: list[str], max_pages: int):
        super().__init__("education_document_discovery", "Document Discovery")
        self.roots = roots
        self.max_pages = max_pages

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for root in self.roots:
            for url in _crawl(root, self.max_pages):
                if url.lower().endswith(_SEARCH_FILE_EXTENSIONS) and url not in seen:
                    seen.add(url)
                    yield self._doc(url, metadata={"origin": "document_discovery", "seed": root})


class PdfDiscoveryProvider(EducationDiscoveryProvider):
    source_kind = "pdf_discovery"

    def __init__(self, roots: list[str], max_pages: int):
        super().__init__("education_pdf_discovery", "PDF Discovery")
        self.roots = roots
        self.max_pages = max_pages

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for root in self.roots:
            for url in _crawl(root, self.max_pages):
                if url.lower().endswith(".pdf") and url not in seen:
                    seen.add(url)
                    yield self._doc(url, metadata={"origin": "pdf_discovery", "seed": root})


class GovernmentPortalProvider(EducationDiscoveryProvider):
    source_kind = "government_portal"

    def __init__(self, roots: list[str], max_pages: int):
        super().__init__("education_government_portal", "Government Portal")
        self.roots = roots
        self.max_pages = max_pages

    def discover(self) -> Iterable[AcquisitionDocument]:
        seen: set[str] = set()
        for root in self.roots:
            parsed = urlparse(root)
            if not parsed.netloc.endswith(".gov.in"):
                continue
            for url in _crawl(root, self.max_pages):
                if url not in seen:
                    seen.add(url)
                    yield self._doc(url, metadata={"origin": "government_portal", "seed": root})


def _parse_sitemap(xml_text: str, depth: int = 0) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    locs = [el.text.strip() for el in root.iter() if el.tag.lower().endswith("loc") and el.text]
    if root.tag.lower().endswith("sitemapindex") and depth == 0:
        urls: list[str] = []
        for child_url in locs[:20]:
            child = http_get(child_url)
            if child and child.text:
                urls.extend(_parse_sitemap(child.text, depth=1))
        return urls
    return [u for u in locs if not u.lower().endswith(_SKIP_EXTENSIONS)]


def _crawl(root_url: str, max_pages: int) -> list[str]:
    parsed = urlparse(root_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots = RobotFileParser()
    robots.set_url(f"{origin}/robots.txt")
    try:
        robots.read()
    except Exception:
        robots = None

    seen = {root_url}
    queue = [root_url]
    found: list[str] = []

    while queue and len(found) < max_pages:
        current = queue.pop(0)
        if robots is not None and not robots.can_fetch("*", current):
            continue
        result = http_get(current)
        if not result or not result.text:
            continue
        found.append(current)
        soup = BeautifulSoup(result.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = urljoin(current, link["href"]).split("#")[0]
            if not href.startswith(origin) or href in seen or href.lower().endswith(_SKIP_EXTENSIONS):
                continue
            seen.add(href)
            queue.append(href)
            if len(seen) >= max_pages * 3:
                break
    return found


@dataclass
class EducationDiscoveryConfig:
    queries: list[str]
    manual_urls: list[str]
    root_urls: list[str]
    rss_urls: list[str]
    government_urls: list[str]
    providers: list[str]
    max_pages_per_root: int
    max_search_results: int


def build_discovery_providers(config: EducationDiscoveryConfig) -> list[EducationDiscoveryProvider]:
    providers: list[EducationDiscoveryProvider] = []
    selected = set(config.providers)
    if config.manual_urls and "manual_url" in selected:
        providers.append(ManualUrlProvider(config.manual_urls))
    if config.root_urls and "sitemap" in selected:
        providers.append(SitemapProvider(config.root_urls))
    if config.root_urls and "website_crawl" in selected:
        providers.append(WebsiteCrawlProvider(config.root_urls, config.max_pages_per_root))
    if config.rss_urls and "rss" in selected:
        providers.append(RssProvider(config.rss_urls))
    if config.government_urls and "government_portal" in selected:
        providers.append(GovernmentPortalProvider(config.government_urls, config.max_pages_per_root))
    if config.root_urls and "pdf_discovery" in selected:
        providers.append(PdfDiscoveryProvider(config.root_urls, config.max_pages_per_root))
    if config.root_urls and "document_discovery" in selected:
        providers.append(DocumentDiscoveryProvider(config.root_urls, config.max_pages_per_root))
    if config.queries and "duckduckgo" in selected:
        providers.append(DuckDuckGoProvider(config.queries, config.max_search_results))
    if config.queries and "bing" in selected:
        providers.append(BingProvider(config.queries, config.max_search_results))
    if config.queries and "google" in selected:
        providers.append(GoogleSearchProvider(config.queries, config.max_search_results))
    return providers
