"""Google Cloud Text-to-Speech via REST API key (no extra SDK dependency)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, register

VOICES = [
    {"id": "en-IN-Neural2-A", "label": "Neural2-A — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "en-IN-Neural2-D", "label": "Neural2-D — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "en-IN-Neural2-B", "label": "Neural2-B — Indian English, Male", "language": "en-IN", "gender": "male"},
    {"id": "ta-IN-Standard-A", "label": "Standard-A — Tamil, Female", "language": "ta-IN", "gender": "female"},
]


class GoogleProvider:
    name = "google"
    label = "Google Cloud TTS"

    def available(self) -> bool:
        return bool(settings.tts_google_api_key)

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(self, text: str, voice: str | None, out_path: Path) -> SynthesisResult:
        voice_id = voice or VOICES[0]["id"]
        language = "-".join(voice_id.split("-")[:2])
        response = httpx.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": settings.tts_google_api_key},
            json={
                "input": {"text": text},
                "voice": {"languageCode": language, "name": voice_id},
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=120,
        )
        response.raise_for_status()
        out_path.write_bytes(base64.b64decode(response.json()["audioContent"]))
        from app.integrations.ffmpeg import FFmpeg

        return SynthesisResult(path=out_path, duration=FFmpeg.probe_duration(str(out_path)))


register(GoogleProvider())
