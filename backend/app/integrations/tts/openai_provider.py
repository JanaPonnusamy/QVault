"""OpenAI TTS (``/v1/audio/speech``) via the already-bundled ``openai`` SDK.

Uses its own key (``QVAULT_TTS_OPENAI_API_KEY``) — deliberately separate from
the Knowledge Research OpenRouter key, which does not serve audio endpoints.
"""

from __future__ import annotations

from pathlib import Path

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, register

VOICES = [
    {"id": "nova", "label": "Nova — Female", "language": "en", "gender": "female"},
    {"id": "shimmer", "label": "Shimmer — Female", "language": "en", "gender": "female"},
    {"id": "alloy", "label": "Alloy — Neutral", "language": "en", "gender": "neutral"},
    {"id": "onyx", "label": "Onyx — Male", "language": "en", "gender": "male"},
]


class OpenAIProvider:
    name = "openai"
    label = "OpenAI TTS"

    def available(self) -> bool:
        return bool(settings.tts_openai_api_key)

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(
        self,
        text: str,
        voice: str | None,
        out_path: Path,
        rate: str | None = None,
        pitch: str | None = None,  # no pitch control in the OpenAI speech API
    ) -> SynthesisResult:
        from openai import OpenAI

        speed = max(0.25, min(4.0, 1.0 + float((rate or settings.tts_rate).rstrip("%")) / 100))
        client = OpenAI(api_key=settings.tts_openai_api_key)
        response = client.audio.speech.create(
            model=settings.tts_openai_model,
            voice=voice or "nova",
            input=text,
            response_format="mp3",
            speed=speed,
        )
        out_path.write_bytes(response.content)
        from app.integrations.ffmpeg import FFmpeg

        return SynthesisResult(path=out_path, duration=FFmpeg.probe_duration(str(out_path)))


register(OpenAIProvider())
