import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

from app.config.settings import settings
from app.shared.logging import get_logger

logger = get_logger("ytdlp")

_INSTAGRAM_REELS_RE = re.compile(r"^(https?://(?:www\.)?instagram\.com)/reels/([^/?#]+)")


def _normalize_instagram_url(url: str) -> str:
    """Instagram's own app links share reels as `/reels/<code>/` (the
    reels-feed viewer route), but that path isn't a stable single-post
    permalink -- yt-dlp's Instagram extractor resolves it as a feed entry
    point and can come back with an unrelated reel instead of the one the
    user pasted. `/reel/<code>/` (singular) is the canonical single-post
    permalink and always resolves to the exact post, so rewrite before
    handing the URL to yt-dlp."""
    match = _INSTAGRAM_REELS_RE.match(url)
    if not match:
        return url
    return f"{match.group(1)}/reel/{match.group(2)}/"


class CookieSource:
    """Resolves QVault's yt-dlp cookie configuration once, so the options built
    for yt-dlp and what's logged at startup can never drift apart.

    Precedence: for Instagram, the session saved by the in-app Instagram Login
    (Instagram Acquisition page) always wins -- it's the account the admin just
    signed into, and using a stale global file/browser cookie instead would be
    surprising. Otherwise a configured cookies file wins over browser
    extraction over no auth -- a configured file short-circuits the browser
    path entirely (the browser branch is structurally unreachable once a file
    is set), and a configured-but-missing file fails fast instead of silently
    downloading with zero cookies (which previously surfaced hours later as a
    confusing "empty media response" error with no clue why cookies weren't
    applied).
    """

    def __init__(self, source: str | None = None) -> None:
        if source == "instagram" and settings.instagram_cookies_path.is_file():
            self.file = str(settings.instagram_cookies_path)
            self.browser = None
            return
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
    def probe_metadata(url: str, source: str | None = None) -> dict:
        """Metadata-only probe (no download) -- used to estimate frame counts
        before a job runs. Falls back to zeros if the source can't be probed
        (estimate becomes advisory only; the job itself still runs normally)."""
        if source == "instagram":
            url = _normalize_instagram_url(url)
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
        CookieSource(source).apply(opts)
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
    def download_video(url: str, output_dir: Path, source: str | None = None) -> dict:
        if source == "instagram":
            url = _normalize_instagram_url(url)
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
        cookies = CookieSource(source)
        cookies.apply(opts)

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
            if not cookies.file and not cookies.browser and (
                "empty media response" in message or "logged-in" in message
            ):
                hint = (
                    "Log in from the Instagram Acquisition page (Instagram Login card)."
                    if source == "instagram"
                    else "Set QVAULT_YTDLP_COOKIES_FILE (path to a cookies.txt) or "
                    "QVAULT_YTDLP_COOKIES_FROM_BROWSER (e.g. 'chrome') in config/.env."
                )
                raise yt_dlp.utils.DownloadError(
                    f"{exc}\n\nThis source requires an authenticated session. {hint} and retry."
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


class InstagramSession:
    """The in-app "Instagram Login" (Instagram Acquisition page): signs in with
    yt-dlp's native username/password auth against a stable public profile page,
    which persists the resulting session cookies to
    `settings.instagram_cookies_path`. `CookieSource` then picks that file up
    automatically for every subsequent Instagram job -- no env var, no manual
    cookies.txt export.

    Instagram's anti-bot defenses make the username/password flow above fail
    for many accounts regardless of whether the password is correct (a known
    yt-dlp/Instagram issue, not a QVault bug). `ensure_seeded` and the
    auto-adopt branch in `status` give a working fallback: a cookies.txt
    exported from an already-logged-in browser (or the repo's bundled
    `config/instagram_cookies.txt`) is auto-detected as the active session on
    first use, with no in-app login step required.
    """

    _PROBE_URL = "https://www.instagram.com/instagram/"

    @staticmethod
    def ensure_seeded() -> None:
        """Called once at app startup. If no session cookie jar exists yet but
        a bundled/manually-dropped `config/instagram_cookies.txt` does, adopt
        it as the initial Instagram session -- so a fresh checkout or a
        manually exported cookies.txt "just works" without visiting the login
        form first."""
        if settings.instagram_cookies_path.is_file():
            return
        seed = settings.storage_dir.parent / "config" / "instagram_cookies.txt"
        if not seed.is_file():
            return
        settings.instagram_dir.mkdir(parents=True, exist_ok=True)
        settings.instagram_cookies_path.write_bytes(seed.read_bytes())
        logger.info("Instagram: seeded session cookies from %s", seed)

    @staticmethod
    def _cookie_value(name: str) -> str | None:
        path = settings.instagram_cookies_path
        if not path.is_file():
            return None
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 7 and fields[5] == name:
                return fields[6]
        return None

    @staticmethod
    def login(username: str, password: str) -> None:
        settings.instagram_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "username": username,
            "password": password,
            "cookiefile": str(settings.instagram_cookies_path),
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(InstagramSession._PROBE_URL, download=False)
        except yt_dlp.utils.DownloadError as exc:
            settings.instagram_cookies_path.unlink(missing_ok=True)
            message = str(exc).lower()
            if "checkpoint" in message or "challenge" in message or "two-factor" in message:
                raise yt_dlp.utils.DownloadError(
                    f"{exc}\n\nInstagram is asking for extra verification (checkpoint/2FA) that "
                    "can't be completed here. Approve the login attempt in the Instagram app, "
                    "then retry, or export cookies.txt via a browser extension instead."
                ) from exc
            raise

        settings.instagram_session_path.write_text(
            json.dumps({"username": username, "connected_at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )

    @staticmethod
    def status() -> dict:
        if not settings.instagram_cookies_path.is_file():
            return {"connected": False, "username": None, "connected_at": None}
        if not settings.instagram_session_path.is_file():
            # A cookies.txt exists (seeded at startup or dropped in manually)
            # but the in-app login never ran -- auto-adopt it as the active
            # session rather than showing "not connected" for a jar that
            # actually works.
            settings.instagram_session_path.write_text(
                json.dumps({
                    "username": InstagramSession._cookie_value("ds_user_id") or "seeded session",
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                }),
                encoding="utf-8",
            )
        try:
            data = json.loads(settings.instagram_session_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"connected": False, "username": None, "connected_at": None}
        return {
            "connected": True,
            "username": data.get("username"),
            "connected_at": data.get("connected_at"),
        }

    @staticmethod
    def logout() -> None:
        settings.instagram_cookies_path.unlink(missing_ok=True)
        settings.instagram_session_path.unlink(missing_ok=True)


class InstagramQueue:
    """Lists reel/post URLs from a hashtag or profile page (e.g.
    `https://www.instagram.com/explore/tags/<tag>/` or
    `https://www.instagram.com/<username>/`) so the Instagram Acquisition page
    can auto-queue several acquisitions from one input instead of pasting URLs
    one at a time. Uses `extract_flat` -- a listing only, no video download --
    and the same Instagram session `CookieSource` already resolves for every
    other Instagram request."""

    @staticmethod
    def list_urls(source_url: str, limit: int) -> list[str]:
        limit = max(1, min(limit, 50))
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": limit,
        }
        CookieSource("instagram").apply(opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
        entries = info.get("entries") if info.get("entries") is not None else [info]
        urls: list[str] = []
        for entry in entries:
            if not entry:
                continue
            url = entry.get("url") or entry.get("webpage_url")
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
        return urls
