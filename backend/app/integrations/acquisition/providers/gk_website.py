"""GK Scraper website provider — the first concrete implementation of the
Phase 2A acquisition provider framework (`integrations/acquisition/`).

Unlike the fixed, singleton-registered providers the framework's docstrings
anticipate (NCERT, YouTube, ...), this one is parameterized by whatever
homepage URL an admin submits, so it is instantiated per scan rather than
registered once at import time.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

from app.config.settings import settings
from app.integrations.acquisition.dto import AcquisitionDocument, JobSpec
from app.integrations.acquisition.provider import AcquisitionProvider
from app.integrations.acquisition.storage import AcquisitionStorage
from app.integrations.gk_http import get as http_get
from app.integrations.gk_site_analyzer import classify_page, discover_urls

CATEGORY = "General Knowledge"


class GkWebsiteProvider(AcquisitionProvider):
    def __init__(self, homepage_url: str):
        self.homepage_url = homepage_url
        self.domain = urlparse(homepage_url).netloc.replace(":", "_")
        self.name = f"gk_{self.domain}"
        self.discovery_method = "crawl"

    def discover(self) -> Iterable[AcquisitionDocument]:
        result = discover_urls(self.homepage_url, settings.gk_scraper_pool_size)
        self.discovery_method = result.method
        for page in result.pages:
            yield AcquisitionDocument(
                provider=self.name,
                source_id=self._source_id(page.url),
                source_url=page.url,
                document_type="unknown",
                metadata={"origin": page.origin, "homepage_url": self.homepage_url},
            )

    def fetch(self, document: AcquisitionDocument) -> AcquisitionDocument:
        result = http_get(document.source_url)
        if not result:
            raise RuntimeError(f"Fetch failed: {document.source_url}")

        is_pdf = "pdf" in result.content_type.lower() or document.source_url.lower().endswith(".pdf")
        filename = self._filename(document.source_url, is_pdf)
        path = AcquisitionStorage.save(document, result.content, filename, exam=CATEGORY, year="")
        checksum = hashlib.sha256(result.content).hexdigest()[:32]

        return AcquisitionDocument(
            provider=document.provider,
            source_id=document.source_id,
            source_url=document.source_url,
            document_type="pdf" if is_pdf else "html",
            language=document.language,
            checksum=checksum,
            metadata={**document.metadata, "content_type": result.content_type},
            local_file=str(path),
        )

    def validate(self, document: AcquisitionDocument) -> bool:
        return bool(document.local_file) and document.document_type in ("html", "pdf")

    def extract_metadata(self, document: AcquisitionDocument) -> dict:
        if document.document_type != "html" or not document.local_file:
            return {}
        html = Path(document.local_file).read_text(encoding="utf-8", errors="ignore")
        classification = classify_page(document.source_url, document.metadata.get("content_type", ""), html)
        return {"page_type": classification.page_type, "plugin": classification.plugin, **classification.signals}

    def create_job(self, **kwargs) -> JobSpec:
        return JobSpec(job_type="gk_website_scrape", source="gk_scraper", payload={"homepage_url": self.homepage_url, **kwargs})

    def health(self) -> dict:
        result = http_get(self.homepage_url)
        if not result:
            return {"status": "error", "detail": "homepage unreachable"}
        return {"status": "ok"}

    def _source_id(self, url: str) -> str:
        # Always a hash, never the raw URL: source_id doubles as a filesystem
        # path segment in AcquisitionStorage, and URLs contain ':' and '/'
        # which are invalid/misleading path components (esp. on Windows).
        return hashlib.sha256(url.encode()).hexdigest()[:40]

    def _filename(self, url: str, is_pdf: bool) -> str:
        name = Path(urlparse(url).path).name or hashlib.sha256(url.encode()).hexdigest()[:16]
        ext = ".pdf" if is_pdf else ".html"
        return name if name.lower().endswith(ext) else name + ext
