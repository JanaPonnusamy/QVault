from pathlib import Path

import yt_dlp

from app.config.settings import settings
from app.shared.logging import get_logger

logger = get_logger("ytdlp")


class CookieSource:
    """Resolves QVault's yt-dlp cookie configuration once, so the options built
    for yt-dlp and what's logged at startup can never drift apart.

    Precedence: a cookies file always wins over browser extraction over no
    auth -- a configured file short-circuits the browser path entirely (the
    browser branch is structurally unreachable once a file is set), and a
    configured-but-missing file fails fast instead of silently downloading
    with zero cookies (which previously surfaced hours later as a confusing
    "empty media response" error with no clue why cookies weren't applied).
    """

    def __init__(self) -> None:
        self.file = settings.ytdlp_cookies_file
        self.browser = settings.ytdlp_cookies_from_browser
        if self.file and not Path(self.file).is_file():
            raise FileNotFoundError(
                f"QVAULT_YTDLP_COOKIES_FILE is set to '{self.file}' but no file exists "
                "there. Export cookies.txt to that exact path (e.g. via the 'Get "
                "cookies.txt LOCALLY' browser extension) or update the path in "
                "config/.env."
            )

    @property
    def active(self) -> str:
        if self.file:
            return "file"
        if self.browser:
            return "browser"
        return "none"

    def describe(self) -> str:
        if self.active == "file":
            return f"Cookies Source:\n✓ Cookies File\nPath: {self.file}"
        if self.active == "browser":
            return f"Cookies Source:\n✓ Browser: {self.browser.split(':')[0].title()}"
        return "Cookies Source:\n✗ None configured"

    def apply(self, opts: dict) -> None:
        if self.file:
            opts["cookiefile"] = self.file
        elif self.browser:
            browser, _, profile = self.browser.partition(":")
            opts["cookiesfrombrowser"] = (browser, profile or None, None, None)


def log_cookie_source() -> None:
    """Called once at app startup so the active cookie source is always
    visible in the server logs -- never silently stale."""
    try:
        source = CookieSource()
    except FileNotFoundError as exc:
        logger.warning("Cookies Source:\n✗ Misconfigured: %s", exc)
        return
    logger.info(source.describe())


class YtDlp:
    @staticmethod
    def probe_metadata(url: str) -> dict:
        """Metadata-only probe (no download) -- used to estimate frame counts
        before a job runs. Falls back to zeros if the source can't be probed
        (estimate becomes advisory only; the job itself still runs normally)."""
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
        CookieSource().apply(opts)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:  # noqa: BLE001
            return {"duration": 0.0, "fps": 0.0}
        return {
            "duration": float(info.get("duration") or 0.0),
            "fps": float(info.get("fps") or 0.0),
        }

    @staticmethod
    def download_video(url: str, output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "merge_output_format": "mp4",
            "outtmpl": str(output_dir / "video.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
        }
        CookieSource().apply(opts)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            message = str(exc).lower()
            if "could not copy" in message and "cookie database" in message:
                raise yt_dlp.utils.DownloadError(
                    f"{exc}\n\nThe browser must be fully closed (all background processes, "
                    "not just windows) for QVAULT_YTDLP_COOKIES_FROM_BROWSER to read its cookie "
                    "database on Windows. More reliably, export cookies to a file instead (e.g. "
                    "the 'Get cookies.txt LOCALLY' extension) and set QVAULT_YTDLP_COOKIES_FILE "
                    "to that file's path in config/.env."
                ) from exc
            if not (settings.ytdlp_cookies_file or settings.ytdlp_cookies_from_browser) and (
                "empty media response" in message or "logged-in" in message
            ):
                raise yt_dlp.utils.DownloadError(
                    f"{exc}\n\nThis source requires an authenticated session. Set "
                    "QVAULT_YTDLP_COOKIES_FILE (path to a cookies.txt) or "
                    "QVAULT_YTDLP_COOKIES_FROM_BROWSER (e.g. 'chrome') in config/.env "
                    "and retry."
                ) from exc
            raise

        path = output_dir / "video.mp4"
        if not path.exists():
            for candidate in output_dir.glob("video.*"):
                path = candidate
                break

        meta_keys = (
            "id", "ext", "width", "height", "fps", "view_count", "like_count",
            "comment_count", "webpage_url", "uploader_url", "channel", "extractor",
        )
        return {
            "title": info.get("title") or "",
            "video_id": info.get("id") or "",
            "duration": int(info.get("duration") or 0),
            "path": str(path),
            "caption": info.get("description") or "",
            "author": info.get("uploader") or info.get("channel") or info.get("uploader_id") or "",
            "upload_date": info.get("upload_date") or "",
            "thumbnail": info.get("thumbnail") or "",
            "meta": {k: info.get(k) for k in meta_keys if info.get(k) is not None},
        }
