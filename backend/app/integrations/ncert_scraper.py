import re
import time
from dataclasses import dataclass

from curl_cffi import requests

from app.config.settings import settings

# NCERT's WAF resets plain Python TLS clients; impersonate a real browser.
_IMPERSONATE = "chrome"

ROMAN = {
    "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI",
    "7": "VII", "8": "VIII", "9": "IX", "10": "X", "11": "XI", "12": "XII",
    "13": "XI & XII",
}

_COND = re.compile(
    r"tclass\.value==(\d+).*?tsubject\.options\[sind\]\.text==\"([^\"]+)\""
)
_TEXT = re.compile(r"tbook\.options\[(\d+)\]\.text=\"([^\"]*)\"")
_VALUE = re.compile(r"tbook\.options\[(\d+)\]\.value=\"textbook\.php\?([a-z0-9]+)=0-(\d+)\"")


@dataclass
class ScannedBook:
    book_code: str
    class_level: str
    class_label: str
    subject: str
    title: str
    part: str
    language: str
    url: str


def _language(code: str) -> str:
    # Code's second character encodes the medium for the common series.
    mapping = {"e": "English", "h": "Hindi", "u": "Urdu"}
    if len(code) > 1:
        return mapping.get(code[1], "Other")
    return "Other"


def _part(code: str) -> str:
    match = re.search(r"(\d+)$", code)
    return match.group(1) if match else ""


class NcertScraper:
    @staticmethod
    def fetch_page() -> str:
        attempts = max(1, settings.ncert_retry_count)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = requests.get(
                    settings.ncert_page_url,
                    impersonate=_IMPERSONATE,
                    timeout=settings.ncert_timeout,
                )
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < attempts:
                    time.sleep(min(2 * attempt, 8))
        raise RuntimeError(f"NCERT scan failed after {attempts} attempts: {last_error}")

    @staticmethod
    def parse(html: str) -> list[ScannedBook]:
        books: list[ScannedBook] = []
        seen: set[str] = set()
        cls = subject = None
        idx_text: dict[str, str] = {}

        for raw in html.splitlines():
            line = raw.strip()
            if line.startswith("//"):
                continue

            cond = _COND.search(line)
            if cond:
                cls, subject = cond.group(1), cond.group(2).strip()
                idx_text = {}
                continue

            text_m = _TEXT.search(line)
            if text_m and text_m.group(2).strip():
                idx_text[text_m.group(1)] = text_m.group(2).strip()

            value_m = _VALUE.search(line)
            if value_m and cls:
                index, code, _last = value_m.groups()
                title = idx_text.get(index, "")
                if not title or code in seen:
                    continue
                seen.add(code)
                books.append(
                    ScannedBook(
                        book_code=code,
                        class_level=cls,
                        class_label=f"Class {ROMAN.get(cls, cls)}",
                        subject=subject or "",
                        title=title,
                        part=_part(code),
                        language=_language(code),
                        url=f"{settings.ncert_files_base}/{code}dd.zip",
                    )
                )
        return books

    @classmethod
    def scan(cls) -> list[ScannedBook]:
        return cls.parse(cls.fetch_page())
