"""Kokoro local neural TTS (optional ``kokoro`` + ``soundfile`` packages)."""

from __future__ import annotations

from pathlib import Path

from app.integrations.tts import SynthesisResult, register

VOICES = [
    {"id": "hf_alpha", "label": "Alpha — Hindi-accent English, Female", "language": "hi", "gender": "female"},
    {"id": "hf_beta", "label": "Beta — Hindi-accent English, Female", "language": "hi", "gender": "female"},
    {"id": "af_heart", "label": "Heart — US English, Female", "language": "en-US", "gender": "female"},
    {"id": "bf_emma", "label": "Emma — British English, Female", "language": "en-GB", "gender": "female"},
]

_SAMPLE_RATE = 24000


class KokoroProvider:
    name = "kokoro"
    label = "Kokoro (local)"

    def __init__(self) -> None:
        self._pipelines: dict[str, object] = {}

    def available(self) -> bool:
        try:
            import kokoro  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError:
            return False
        return True

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(
        self,
        text: str,
        voice: str | None,
        out_path: Path,
        rate: str | None = None,  # kokoro exposes no rate/pitch controls
        pitch: str | None = None,
    ) -> SynthesisResult:
        import numpy as np
        import soundfile
        from kokoro import KPipeline

        voice_id = voice or VOICES[0]["id"]
        lang_code = voice_id[0]  # kokoro convention: first letter selects the language pack
        pipeline = self._pipelines.get(lang_code)
        if pipeline is None:
            pipeline = self._pipelines[lang_code] = KPipeline(lang_code=lang_code)
        chunks = [audio for _, _, audio in pipeline(text, voice=voice_id)]
        samples = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
        soundfile.write(str(out_path), samples, _SAMPLE_RATE)
        return SynthesisResult(path=out_path, duration=len(samples) / _SAMPLE_RATE)


register(KokoroProvider())
