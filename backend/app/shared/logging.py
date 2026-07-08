import logging
import sys

from app.config.settings import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    # Some Windows consoles default to a non-UTF-8 codepage; without this,
    # log lines containing non-ASCII characters (e.g. the cookie-source
    # startup banner) silently fail to print instead of raising.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
