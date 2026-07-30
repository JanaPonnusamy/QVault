"""Generic GK-site analyzer: given only a homepage URL, discovers its pages
(sitemap first, same-domain link crawl as a fallback) and classifies each page
deterministically as mcq / essay / fill_blank / pdf / unsupported.

Classification is signal-based, not site-specific: a small `KNOWN_PLUGINS`
fingerprint registry lets a page be tied to a deterministic per-plugin parser
(see `gk_extractors.py`) once its markup has actually been inspected; anything
else falls back to generic heuristics (and, for MCQ/fill-blank, an AI-assisted
extraction pass — see `gk_extractors.py`).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from app.integrations.gk_http import FetchResult, get

_SITEMAP_NAMES = ("sitemap.xml", "sitemap_index.xml")
_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js",
    ".woff", ".woff2", ".ico", ".mp4", ".mp3", ".zip",
)

# url substring markers that, together, identify a known quiz plugin so its
# deterministic parser (gk_extractors.py) can be used instead of AI fallback.
KNOWN_PLUGINS = {
    # Checked first: GKToday runs two quiz formats concurrently. This one
    # (confirmed live on both topic quizzes AND "Daily Current Affairs Quiz"
    # pages — the wrapper div class differs, sques_quiz vs ques_print, but
    # the actual question/options/answer markup is identical) has the answer
    # + explanation already in static HTML — no AJAX needed at all. Fingerprint
    # on the question/answer markers themselves, not the wrapper, so both
    # wrapper variants match.
    "sques_quiz": ("wp_quiz_question_options", "ques_answer"),
    "wp_basic_quiz": ("load_quiz_container", "wp_basic_quiz"),
}

_BLANK_RE = re.compile(r"_{3,}|\.{5,}")
_OPTION_LINE_RE = re.compile(r"^[A-D][\).]\s", re.MULTILINE)


@dataclass
class DiscoveredPage:
    url: str
    origin: str  # "sitemap" | "crawl"


@dataclass
class DiscoveryResult:
    pages: list[DiscoveredPage] = field(default_factory=list)
    method: str = "crawl"


@dataclass
class Classification:
    page_type: str  # mcq | essay | fill_blank | pdf | unsupported
    plugin: str | None = None
    signals: dict = field(default_factory=dict)


def fetch(url: str) -> FetchResult | None:
    return get(url)


# URL shapes that reliably ARE a single quiz/MCQ page (not a listing/index
# page that merely mentions "quiz" in its slug) — checked first.
_STRONG_QUIZ_URL_RE = re.compile(r"/quiz-\d+-|/quizbase/|/gk-questions-answers")
# Weaker fallback signal — still worth trying before generic content.
_QUIZ_URL_HINTS = ("quiz", "mcq", "gk-questions", "gk-quiz")
# Navigational/index hub pages: author archives, PDF/category listing pages,
# tag pages, section landing pages. These never contain real quiz/essay
# content themselves (they only link to it) and would otherwise pollute
# results just because their slug happens to contain "quiz" (e.g.
# "/pdfs/category/daily-current-affairs-quiz-pdf-compilations/"). Excluded
# outright rather than merely deprioritized.
_EXCLUDE_URL_RE = re.compile(
    r"/author/|/pdfs/category/|/module-category/|/category/|/tag/|/hindi/section/"
)

def discover_urls(homepage_url: str, max_pages: int) -> DiscoveryResult:
    parsed = urlparse(homepage_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    # A homepage_url with a real path (not just "/" or "") is the user pointing
    # at a specific page they already know is relevant — always include it,
    # even if a capped sitemap pool wouldn't otherwise surface it.
    seed_url = homepage_url if parsed.path not in ("", "/") else None

    # The raw sitemap pool cap used to be a hardcoded 2000, silently
    # overriding gk_scraper_pool_size (a real site can have 50,000+ pages —
    # confirmed against gktoday.in's own sitemap and the legacy TNPSC
    # scraper's 45k-page visited-URL history) so no config change to
    # max_pages could ever surface more than the first 2000 sitemap entries.
    # Now driven directly by max_pages (with a floor so prioritization still
    # has more candidates than it needs to choose from on smaller runs).
    sitemap_pool = _from_sitemap(origin, max(max_pages, 2000))
    if sitemap_pool:
        pages = _prioritize(sitemap_pool, seed_url, max_pages)
        return DiscoveryResult(pages=pages, method="sitemap")

    crawled = _crawl(homepage_url, origin, max_pages)
    return DiscoveryResult(pages=_prioritize([p.url for p in crawled], seed_url, max_pages), method="crawl")


def _prioritize(urls: list[str], seed_url: str | None, max_pages: int) -> list[DiscoveredPage]:
    ordered: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url not in seen:
            seen.add(url)
            ordered.append(url)

    candidates = [u for u in urls if not _EXCLUDE_URL_RE.search(u.lower())]

    if seed_url:
        add(seed_url)
    for url in candidates:
        if _STRONG_QUIZ_URL_RE.search(url.lower()):
            add(url)
    for url in candidates:
        if any(hint in url.lower() for hint in _QUIZ_URL_HINTS):
            add(url)
    for url in candidates:
        add(url)

    return [DiscoveredPage(url=u, origin="sitemap") for u in ordered[:max_pages]]


def _from_sitemap(origin: str, pool_cap: int) -> list[str]:
    for name in _SITEMAP_NAMES:
        result = fetch(f"{origin}/{name}")
        if not result or not result.text:
            continue
        locs = _parse_sitemap(result.text, pool_cap)
        if locs:
            return locs
    return []


def _parse_sitemap(xml_text: str, pool_cap: int, depth: int = 0) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    locs = [el.text.strip() for el in root.iter() if el.tag.lower().endswith("loc") and el.text]

    if root.tag.lower().endswith("sitemapindex") and depth == 0:
        collected: list[str] = []
        # WordPress-native sitemap indexes (this is one — "wp-sitemap-*.xml"
        # children) split by content type: real articles/quizzes live in
        # "posts-post-*"/"posts-<custom-type>-*" sitemaps; "taxonomies-*" and
        # "users-*" are pure index/archive sitemaps (category/tag/author
        # listings) that never contain real content. An earlier "just walk
        # the last N child sitemaps" heuristic assumed chronological order
        # and happened to land entirely on those index sitemaps instead of
        # the 46 real content ones — found by inspecting gktoday.in's actual
        # sitemap_index.xml. Prefer content sitemaps, skip index ones, and
        # within content sitemaps prefer higher-numbered (newer) files first.
        def sort_key(url: str) -> tuple[int, int]:
            lower = url.lower()
            is_index_sitemap = "taxonom" in lower or "-users-" in lower
            match = re.search(r"-(\d+)\.xml$", lower)
            number = int(match.group(1)) if match else 0
            return (1 if is_index_sitemap else 0, -number)

        for child_url in sorted(locs, key=sort_key)[:30]:
            child = fetch(child_url)
            if child and child.text:
                collected.extend(_parse_sitemap(child.text, pool_cap, depth=1))
            if len(collected) >= pool_cap:
                break
        return collected[:pool_cap]

    return [u for u in locs if not u.lower().endswith(_SKIP_EXTENSIONS)][:pool_cap]


def _crawl(homepage_url: str, origin: str, max_pages: int) -> list[DiscoveredPage]:
    robots = RobotFileParser()
    robots.set_url(f"{origin}/robots.txt")
    try:
        robots.read()
    except Exception:
        robots = None  # unreadable robots.txt -> assume allowed

    seen = {homepage_url}
    queue = [homepage_url]
    pages: list[DiscoveredPage] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if robots is not None and not robots.can_fetch("*", url):
            continue
        result = fetch(url)
        if not result or not result.text:
            continue
        pages.append(DiscoveredPage(url=url, origin="crawl"))

        soup = BeautifulSoup(result.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"]).split("#")[0]
            if not link.startswith(origin) or link in seen or link.lower().endswith(_SKIP_EXTENSIONS):
                continue
            seen.add(link)
            queue.append(link)
            if len(seen) >= max_pages * 3:
                break

    return pages


def classify_page(url: str, content_type: str, text: str) -> Classification:
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        return Classification(page_type="pdf")

    if not text:
        return Classification(page_type="unsupported")

    for plugin, markers in KNOWN_PLUGINS.items():
        if all(marker in text for marker in markers):
            return Classification(page_type="mcq", plugin=plugin, signals={"matched_plugin": plugin})

    soup = BeautifulSoup(text, "html.parser")
    radio_count = len(soup.find_all("input", attrs={"type": "radio"}))
    visible = soup.get_text("\n", strip=True)
    option_lines = len(_OPTION_LINE_RE.findall(visible))

    if radio_count >= 3 or option_lines >= 3:
        return Classification(page_type="mcq", signals={"radio_count": radio_count, "option_lines": option_lines})

    blank_matches = len(_BLANK_RE.findall(visible))
    if blank_matches:
        return Classification(page_type="fill_blank", signals={"blank_matches": blank_matches})

    article = soup.find("article") or soup.find("main")
    word_count = len((article.get_text(" ", strip=True) if article else visible).split())
    if word_count >= 150:
        return Classification(page_type="essay", signals={"word_count": word_count})

    return Classification(page_type="unsupported", signals={"word_count": word_count})
