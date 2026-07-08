"""Source-agnostic video acquisition providers.

The ingestion pipeline (frame extraction -> OCR/analysis -> classification ->
question extraction) operates on a downloaded ``video.mp4`` plus a metadata dict
and never needs to know *where* the video came from. Each acquisition source is
expressed purely as a :class:`VideoProvider`: given a reference (a URL now, or a
local path later) and an output directory, it produces ``video.mp4`` and returns
the shared metadata shape.

Adding Facebook / TikTok / X / Vimeo / a local MP4 is therefore a single
``register(...)`` call here -- no change to the worker, frame extraction, OCR,
classification or question-extraction stages. yt-dlp already handles most video
sites natively, so a new URL source is one line; a non-URL source (e.g. a local
MP4) is a small provider class implementing ``fetch`` (copy the file into
``output_dir`` and return the same dict shape) with no other pipeline change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.integrations.ytdlp import YtDlp


@runtime_checkable
class VideoProvider(Protocol):
    #: source discriminator persisted on ExtractionJob.source
    name: str
    #: whether the downstream deterministic content-classification stage runs
    classify_frames: bool

    def fetch(self, ref: str, output_dir: Path) -> dict:
        """Produce ``<output_dir>/video.mp4`` and return shared video metadata.

        The returned dict has the shape produced by ``YtDlp.download_video``:
        ``title``, ``video_id``, ``duration``, ``path``, ``caption``, ``author``,
        ``upload_date``, ``thumbnail``, ``meta``.
        """
        ...


class YtDlpProvider:
    """URL-based provider backed by yt-dlp.

    Works for every site yt-dlp supports natively -- YouTube, Instagram, and
    (future) Facebook, TikTok, X, Vimeo -- so a new URL source only needs its own
    registration with the desired ``classify_frames`` policy.
    """

    def __init__(self, name: str, classify_frames: bool = False) -> None:
        self.name = name
        self.classify_frames = classify_frames

    def fetch(self, ref: str, output_dir: Path) -> dict:
        return YtDlp.download_video(ref, output_dir)


_PROVIDERS: dict[str, VideoProvider] = {}


def register(provider: VideoProvider) -> VideoProvider:
    _PROVIDERS[provider.name] = provider
    return provider


def get_provider(source: str | None) -> VideoProvider:
    provider = _PROVIDERS.get(source or "")
    if provider is None:
        raise ValueError(f"No video provider registered for source '{source}'")
    return provider


# Live sources. Future sources slot in here (or via register()) with no
# downstream pipeline change. Instagram classifies frame content; YouTube does not.
register(YtDlpProvider("youtube", classify_frames=False))
register(YtDlpProvider("instagram", classify_frames=True))
