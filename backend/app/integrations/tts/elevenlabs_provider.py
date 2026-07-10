"""ElevenLabs TTS via REST (no extra SDK dependency)."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, register

VOICES = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "label": "Rachel — Female", "language": "en", "gender": "female"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "label": "Bella — Female", "language": "en", "gender": "female"},
    {"id": "pNInz6obpgDQGcFmaJgB", "label": "Adam — Male", "language": "en", "gender": "male"},
]


class ElevenLabsProvider:
    name = "elevenlabs"
    label = "ElevenLabs"

    def available(self) -> bool:
        return bool(settings.tts_elevenlabs_api_key)

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(self, text: str, voice: str | None, out_path: Path) -> SynthesisResult:
        voice_id = voice or VOICES[0]["id"]
        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": settings.tts_elevenlabs_api_key},
            json={
                "text": text,
                "model_id": settings.tts_elevenlabs_model,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=120,
        )
        response.raise_for_status()
        out_path.write_bytes(response.content)
        from app.integrations.ffmpeg import FFmpeg

        return SynthesisResult(path=out_path, duration=FFmpeg.probe_duration(str(out_path)))


register(ElevenLabsProvider())
