"""Tests for yt-dlp cookie-auth configuration (Instagram/YouTube auth-wall workaround).

Instagram frequently returns "empty media response" for logged-out requests;
yt-dlp's own guidance is to pass cookies. These tests lock in `CookieSource`'s
precedence (file > browser > none), that a configured-but-missing cookies file
fails fast instead of silently downloading with zero cookies, that
`YtDlp.download_video` wires the resolved source into yt-dlp's options without
a network call, and that error messages point users at the right config keys.
"""
import logging

import pytest
import yt_dlp

from app.config.settings import settings
from app.integrations.ytdlp import CookieSource, YtDlp, log_cookie_source


class _FakeYoutubeDL:
    captured_opts: dict = {}

    def __init__(self, opts):
        _FakeYoutubeDL.captured_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        return {"id": "x", "title": "t", "duration": 1}


@pytest.fixture(autouse=True)
def _reset_cookie_settings():
    orig_file = settings.ytdlp_cookies_file
    orig_browser = settings.ytdlp_cookies_from_browser
    yield
    settings.ytdlp_cookies_file = orig_file
    settings.ytdlp_cookies_from_browser = orig_browser


@pytest.fixture()
def cookies_file(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n")
    return str(path)


# ---------- CookieSource precedence ----------

def test_no_cookies_configured_is_active_none():
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = None
    assert CookieSource().active == "none"


def test_file_configured_and_present_is_active_file(cookies_file):
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = None
    assert CookieSource().active == "file"


def test_browser_configured_is_active_browser():
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = "chrome"
    assert CookieSource().active == "browser"


def test_file_takes_precedence_over_browser_even_when_both_set(cookies_file):
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = "chrome"
    source = CookieSource()
    assert source.active == "file"

    opts: dict = {}
    source.apply(opts)
    assert opts == {"cookiefile": cookies_file}
    assert "cookiesfrombrowser" not in opts


def test_configured_but_missing_file_fails_fast(tmp_path):
    missing = str(tmp_path / "instagram_cookies.txt")
    settings.ytdlp_cookies_file = missing
    settings.ytdlp_cookies_from_browser = "chrome"

    with pytest.raises(FileNotFoundError) as exc_info:
        CookieSource()

    message = str(exc_info.value)
    assert "instagram_cookies.txt" in message
    assert "config/.env" in message


# ---------- describe() / startup logging ----------

def test_describe_reports_file(cookies_file):
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = None
    desc = CookieSource().describe()
    assert "Cookies File" in desc
    assert cookies_file in desc


def test_describe_reports_browser():
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = "chrome"
    desc = CookieSource().describe()
    assert "Browser: Chrome" in desc


def test_describe_reports_none():
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = None
    desc = CookieSource().describe()
    assert "None configured" in desc


def test_log_cookie_source_warns_on_misconfiguration(caplog, tmp_path):
    settings.ytdlp_cookies_file = str(tmp_path / "instagram_cookies.txt")
    settings.ytdlp_cookies_from_browser = None
    with caplog.at_level(logging.WARNING):
        log_cookie_source()  # must not raise -- app startup can't crash on this
    assert any("Misconfigured" in r.message for r in caplog.records)


def test_log_cookie_source_logs_active_source(caplog, cookies_file):
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = None
    with caplog.at_level(logging.INFO):
        log_cookie_source()
    assert any("Cookies File" in r.message for r in caplog.records)


# ---------- YtDlp.download_video wiring ----------

def test_no_cookies_configured_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = None

    YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert "cookiefile" not in _FakeYoutubeDL.captured_opts
    assert "cookiesfrombrowser" not in _FakeYoutubeDL.captured_opts


def test_cookies_file_is_passed_through(monkeypatch, tmp_path, cookies_file):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = None

    YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert _FakeYoutubeDL.captured_opts["cookiefile"] == cookies_file
    assert "cookiesfrombrowser" not in _FakeYoutubeDL.captured_opts


def test_cookies_from_browser_with_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = "firefox:Default"

    YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert _FakeYoutubeDL.captured_opts["cookiesfrombrowser"] == ("firefox", "Default", None, None)


def test_cookies_file_takes_precedence_over_browser(monkeypatch, tmp_path, cookies_file):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = "chrome"

    YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert _FakeYoutubeDL.captured_opts["cookiefile"] == cookies_file
    assert "cookiesfrombrowser" not in _FakeYoutubeDL.captured_opts


def test_download_fails_fast_when_configured_file_is_missing(tmp_path):
    missing = tmp_path / "cookies"
    output_dir = tmp_path / "job"
    settings.ytdlp_cookies_file = str(missing / "instagram_cookies.txt")
    settings.ytdlp_cookies_from_browser = None

    with pytest.raises(FileNotFoundError):
        YtDlp.download_video("https://instagram.com/reel/x", output_dir)


# ---------- error-message hints ----------

def test_auth_wall_error_hints_at_cookie_settings(monkeypatch, tmp_path):
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = None

    class _FailingYoutubeDL(_FakeYoutubeDL):
        def extract_info(self, url, download=True):
            raise yt_dlp.utils.DownloadError(
                "ERROR: [Instagram] xyz: Instagram sent an empty media response."
            )

    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FailingYoutubeDL)

    with pytest.raises(yt_dlp.utils.DownloadError) as exc_info:
        YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert "QVAULT_YTDLP_COOKIES_FILE" in str(exc_info.value)
    assert "QVAULT_YTDLP_COOKIES_FROM_BROWSER" in str(exc_info.value)


def test_auth_wall_error_not_rewritten_when_cookies_already_configured(monkeypatch, tmp_path, cookies_file):
    settings.ytdlp_cookies_file = cookies_file
    settings.ytdlp_cookies_from_browser = None

    class _FailingYoutubeDL(_FakeYoutubeDL):
        def extract_info(self, url, download=True):
            raise yt_dlp.utils.DownloadError(
                "ERROR: [Instagram] xyz: Instagram sent an empty media response."
            )

    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FailingYoutubeDL)

    with pytest.raises(yt_dlp.utils.DownloadError) as exc_info:
        YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    assert "QVAULT_YTDLP_COOKIES_FILE" not in str(exc_info.value)


def test_locked_cookie_database_hints_at_closing_browser_or_cookies_file(monkeypatch, tmp_path):
    """Windows locks the live Chrome cookie DB while Chrome is running (even with all
    windows closed, via background apps) -- yt-dlp/yt-dlp#7271. The hint should point
    users at fully closing the browser or switching to a static cookies file."""
    settings.ytdlp_cookies_file = None
    settings.ytdlp_cookies_from_browser = "chrome"

    class _FailingYoutubeDL(_FakeYoutubeDL):
        def extract_info(self, url, download=True):
            raise yt_dlp.utils.DownloadError(
                "ERROR: Could not copy Chrome cookie database. See "
                "https://github.com/yt-dlp/yt-dlp/issues/7271 for more info"
            )

    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FailingYoutubeDL)

    with pytest.raises(yt_dlp.utils.DownloadError) as exc_info:
        YtDlp.download_video("https://instagram.com/reel/x", tmp_path)

    message = str(exc_info.value)
    assert "fully closed" in message.lower()
    assert "QVAULT_YTDLP_COOKIES_FILE" in message
