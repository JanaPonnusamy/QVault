"""Microsoft Edge neural TTS (free, no API key).

Default provider: natural Indian-English female voices (Neerja) and native
word-boundary events, which give exact word timings for subtitle highlighting
without any forced alignment step.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, WordTiming, register

_TICKS_PER_SECOND = 10_000_000

VOICES = [
    {"id": "en-IN-NeerjaNeural", "label": "Neerja — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "en-IN-NeerjaExpressiveNeural", "label": "Neerja Expressive — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "en-IN-PrabhatNeural", "label": "Prabhat — Indian English, Male", "language": "en-IN", "gender": "male"},
    {"id": "ta-IN-PallaviNeural", "label": "Pallavi — Tamil, Female", "language": "ta-IN", "gender": "female"},
    {"id": "en-US-AriaNeural", "label": "Aria — US English, Female", "language": "en-US", "gender": "female"},
]


class EdgeProvider:
    name = "edge"
    label = "Edge Neural (free)"

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(self, text: str, voice: str | None, out_path: Path) -> SynthesisResult:
        words = asyncio.run(self._stream(text, voice or settings.tts_voice, out_path))
        from app.integrations.ffmpeg import FFmpeg

        duration = FFmpeg.probe_duration(str(out_path))
        # Edge reports word starts reliably but durations conservatively; extend
        # each word's end to the next word's start so highlighting never gaps.
        for i in range(len(words) - 1):
            words[i].end = max(words[i].end, words[i + 1].start)
        if words:
            words[-1].end = max(words[-1].end, duration)
        return SynthesisResult(path=out_path, duration=duration, words=words)

    async def _stream(self, text: str, voice: str, out_path: Path) -> list[WordTiming]:
        import edge_tts

        communicate = edge_tts.Communicate(
            text, voice, rate=settings.tts_rate, pitch=settings.tts_pitch
        )
        words: list[WordTiming] = []
        with open(out_path, "wb") as fh:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    fh.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / _TICKS_PER_SECOND
                    words.append(
                        WordTiming(
                            word=str(chunk["text"]),
                            start=start,
                            end=start + chunk["duration"] / _TICKS_PER_SECOND,
                        )
                    )
        return words


register(EdgeProvider())
