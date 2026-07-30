"""Shared HTTP helper for the GK Scraper (Phase 2A's first concrete
acquisition provider). Uses `curl_cffi` (already a dependency, proven against
NCERT's WAF) for browser-TLS impersonation, since arbitrary GK sites may sit
behind Cloudflare or similar. Polite by design: single request at a time per
call site, a small delay between requests, and callers are expected to honour
robots.txt (see `gk_site_analyzer._crawl`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from curl_cffi import requests

from app.config.settings import settings

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_IMPERSONATE = "chrome"


@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str
    text: str
    content: bytes


def _looks_textual(content_type: str) -> bool:
    ct = content_type.lower()
    return ct == "" or "html" in ct or "xml" in ct or "text" in ct


def get(url: str, timeout: int | None = None) -> FetchResult | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA},
            timeout=timeout or settings.gk_scraper_timeout,
            impersonate=_IMPERSONATE,
        )
    except Exception:
        return None
    finally:
        if settings.gk_scraper_request_delay:
            time.sleep(settings.gk_scraper_request_delay)

    if resp.status_code >= 400:
        return None
    content_type = resp.headers.get("content-type", "")
    return FetchResult(
        url=url,
        status_code=resp.status_code,
        content_type=content_type,
        text=resp.text if _looks_textual(content_type) else "",
        content=resp.content,
    )


def post_form(url: str, data: dict, referer: str | None = None, timeout: int | None = None) -> dict | None:
    """`referer`/`X-Requested-With` matter here: this is used to simulate a
    quiz plugin's jQuery AJAX submit (see gk_extractors._extract_wp_basic_quiz),
    and several WP quiz plugins (and the WAFs in front of them) only reveal the
    real answer/explanation when the request looks like it came from the quiz
    page itself via XHR — a bare POST with no Referer was silently accepted but
    returned no usable answer data, which is why a chunk of scraped MCQs ended
    up with a correct_answer_text/solution_text gap."""
    headers = {"User-Agent": _UA, "X-Requested-With": "XMLHttpRequest"}
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.post(
            url,
            data=data,
            headers=headers,
            timeout=timeout or settings.gk_scraper_timeout,
            impersonate=_IMPERSONATE,
        )
    except Exception:
        return None
    finally:
        if settings.gk_scraper_request_delay:
            time.sleep(settings.gk_scraper_request_delay)

    if resp.status_code >= 400:
        return None
    try:
        return resp.json()
    except Exception:
        return None
