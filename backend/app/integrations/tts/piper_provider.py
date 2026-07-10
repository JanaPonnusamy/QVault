"""Piper local TTS via the ``piper`` executable (offline, CPU-only)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.config.settings import settings
from app.integrations.tts import SynthesisResult, register


class PiperProvider:
    name = "piper"
    label = "Piper (local)"

    def available(self) -> bool:
        exe = settings.tts_piper_exe
        model = settings.tts_piper_model
        return bool(exe and model and Path(exe).exists() and Path(model).exists())

    def voices(self) -> list[dict]:
        model = settings.tts_piper_model or ""
        label = Path(model).stem if model else "configured model"
        return [{"id": "default", "label": label, "language": "", "gender": ""}]

    def synthesize(self, text: str, voice: str | None, out_path: Path) -> SynthesisResult:
        subprocess.run(
            [
                settings.tts_piper_exe,
                "--model",
                settings.tts_piper_model,
                "--output_file",
                str(out_path),
            ],
            input=text.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        from app.integrations.ffmpeg import FFmpeg

        return SynthesisResult(path=out_path, duration=FFmpeg.probe_duration(str(out_path)))


register(PiperProvider())
