"""Provider-abstracted text-to-speech.

Narration synthesis for the video generation engine is expressed purely as a
:class:`TTSProvider`: given text, a voice and an output path it produces an
audio file and returns its duration plus (when the provider supports it)
word-level timings used for subtitle word highlighting. Providers that cannot
report word boundaries return an empty list and the subtitle service estimates
timings from word lengths instead.

No provider lock-in: the active provider is selected per request (falling back
to ``settings.tts_provider``), and adding a provider is a module in this
package plus one ``register(...)`` call — no pipeline change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class WordTiming:
    """One spoken word with start/end offsets in seconds from clip start."""

    word: str
    start: float
    end: float


@dataclass
class SynthesisResult:
    path: Path
    duration: float
    words: list[WordTiming] = field(default_factory=list)


@runtime_checkable
class TTSProvider(Protocol):
    #: provider key persisted on the video row and used in API requests
    name: str
    #: human label for the frontend voice selector
    label: str

    def available(self) -> bool:
        """Whether the provider can run right now (keys configured / binary found)."""
        ...

    def voices(self) -> list[dict]:
        """Curated voice list: ``{"id", "label", "language", "gender"}``."""
        ...

    def synthesize(
        self,
        text: str,
        voice: str | None,
        out_path: Path,
        rate: str | None = None,
        pitch: str | None = None,
    ) -> SynthesisResult:
        """Write an audio file to ``out_path`` and return duration + word timings.

        ``rate`` ("-4%") and ``pitch`` ("+10Hz") carry per-segment voice
        modulation; providers apply what their API supports and ignore the rest.
        """
        ...


_PROVIDERS: dict[str, TTSProvider] = {}


def register(provider: TTSProvider) -> TTSProvider:
    _PROVIDERS[provider.name] = provider
    return provider


def get_tts_provider(name: str | None) -> TTSProvider:
    from app.config.settings import settings

    key = (name or settings.tts_provider).lower()
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise ValueError(f"No TTS provider registered for '{key}'")
    if not provider.available():
        raise RuntimeError(
            f"TTS provider '{key}' is not configured (missing API key, model or binary)"
        )
    return provider


def list_tts_providers() -> list[dict]:
    """All registered providers with availability + voices, for the frontend."""
    out = []
    for provider in _PROVIDERS.values():
        ok = provider.available()
        out.append(
            {
                "name": provider.name,
                "label": provider.label,
                "available": ok,
                "voices": provider.voices() if ok else provider.voices(),
            }
        )
    return out


# Self-registering provider modules. Import order defines display order.
from app.integrations.tts import (  # noqa: E402  (registration imports)
    azure_provider,
    edge_provider,
    elevenlabs_provider,
    google_provider,
    kokoro_provider,
    openai_provider,
    piper_provider,
)

__all__ = [
    "SynthesisResult",
    "TTSProvider",
    "WordTiming",
    "get_tts_provider",
    "list_tts_providers",
    "register",
]
