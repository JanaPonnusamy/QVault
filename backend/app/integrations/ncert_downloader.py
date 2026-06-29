import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests

from app.config.settings import settings

# NCERT's WAF resets plain Python TLS clients; impersonate a real browser.
_IMPERSONATE = "chrome"


@dataclass
class DownloadResult:
    file_path: str
    file_size: int
    checksum: str
    version_hash: str


def _remote_signature(url: str) -> str:
    """Lightweight signature of the remote file (size + last-modified) for
    update detection, obtained with a 1-byte ranged request (NCERT blocks HEAD)."""
    try:
        resp = requests.get(
            url,
            headers={"Range": "bytes=0-0"},
            impersonate=_IMPERSONATE,
            timeout=settings.ncert_timeout,
        )
        total = resp.headers.get("Content-Range", "").split("/")[-1]
        last_modified = resp.headers.get("Last-Modified", "")
        raw = f"{total}|{last_modified}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        return ""


class NcertDownloader:
    @staticmethod
    def remote_signature(url: str) -> str:
        return _remote_signature(url)

    @staticmethod
    def download(url: str, dest: Path) -> DownloadResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        attempts = max(1, settings.ncert_retry_count)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                sha = hashlib.sha256()
                size = 0
                tmp = dest.with_suffix(dest.suffix + ".part")
                resp = requests.get(
                    url,
                    impersonate=_IMPERSONATE,
                    timeout=settings.ncert_timeout,
                    stream=True,
                )
                try:
                    resp.raise_for_status()
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                fh.write(chunk)
                                sha.update(chunk)
                                size += len(chunk)
                finally:
                    resp.close()
                tmp.replace(dest)

                return DownloadResult(
                    file_path=str(dest),
                    file_size=size,
                    checksum=sha.hexdigest()[:32],
                    version_hash=_remote_signature(url),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < attempts:
                    time.sleep(min(2 * attempt, 8))

        raise RuntimeError(f"Download failed after {attempts} attempts: {last_error}")
