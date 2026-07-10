"""Azure Cognitive Services TTS via REST (no extra SDK dependency)."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import httpx

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, register

VOICES = [
    {"id": "en-IN-NeerjaNeural", "label": "Neerja — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "en-IN-AartiNeural", "label": "Aarti — Indian English, Female", "language": "en-IN", "gender": "female"},
    {"id": "ta-IN-PallaviNeural", "label": "Pallavi — Tamil, Female", "language": "ta-IN", "gender": "female"},
    {"id": "en-IN-PrabhatNeural", "label": "Prabhat — Indian English, Male", "language": "en-IN", "gender": "male"},
]


class AzureProvider:
    name = "azure"
    label = "Azure Speech"

    def available(self) -> bool:
        return bool(settings.tts_azure_key and settings.tts_azure_region)

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(self, text: str, voice: str | None, out_path: Path) -> SynthesisResult:
        voice_id = voice or VOICES[0]["id"]
        lang = "-".join(voice_id.split("-")[:2])
        ssml = (
            f'<speak version="1.0" xml:lang="{lang}">'
            f'<voice name="{voice_id}">{escape(text)}</voice></speak>'
        )
        response = httpx.post(
            f"https://{settings.tts_azure_region}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": settings.tts_azure_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            },
            content=ssml.encode("utf-8"),
            timeout=120,
        )
        response.raise_for_status()
        out_path.write_bytes(response.content)
        from app.integrations.ffmpeg import FFmpeg

        return SynthesisResult(path=out_path, duration=FFmpeg.probe_duration(str(out_path)))


register(AzureProvider())
