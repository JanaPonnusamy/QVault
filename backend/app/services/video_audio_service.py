"""Audio mixdown for generated videos.

Assembles the final soundtrack from the timeline: narration clips at their
exact start offsets, synthesized countdown ticks, and (when the template names
a file that exists under ``assets/music``) a low-volume background music bed.
Everything is mixed as int32 to avoid clipping, normalized back to int16 and
written as a plain WAV that ffmpeg muxes during rendering. Clips are decoded
one at a time — the full mix buffer is the only large allocation
(~5 MB per minute, independent of clip count).
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

from app.config.settings import settings
from app.services.video_timeline_service import VideoTimeline
from app.shared.logging import get_logger

logger = get_logger("video_audio")

SAMPLE_RATE = 44100


def _decode_pcm(path: str) -> np.ndarray:
    """Decode any audio file to mono 44.1 kHz int16 via ffmpeg."""
    result = subprocess.run(
        [
            settings.ffmpeg_path,
            "-v", "error",
            "-i", path,
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", str(SAMPLE_RATE),
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(result.stdout, dtype=np.int16)


def _tick(frequency: float = 1000.0, seconds: float = 0.14, volume: float = 0.22) -> np.ndarray:
    t = np.linspace(0.0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    envelope = np.exp(-t * 22.0)
    return (np.sin(2 * np.pi * frequency * t) * envelope * volume * 32767).astype(np.int32)


class VideoAudioService:
    def assemble(self, timeline: VideoTimeline, template: dict, out_path: Path) -> Path:
        total = int(timeline.duration * SAMPLE_RATE) + SAMPLE_RATE
        mix = np.zeros(total, dtype=np.int32)

        for clip in timeline.audio_clips:
            pcm = _decode_pcm(clip.path).astype(np.int32)
            start = int(clip.start * SAMPLE_RATE)
            end = min(start + len(pcm), total)
            mix[start:end] += pcm[: end - start]

        tick = _tick()
        for i, at in enumerate(timeline.tick_times):
            # the final tick of each countdown lands slightly higher
            pcm = _tick(1320.0) if (i + 1) % timeline.countdown_seconds == 0 else tick
            start = int(at * SAMPLE_RATE)
            end = min(start + len(pcm), total)
            mix[start:end] += pcm[: end - start]

        music_name = template.get("music")
        if music_name:
            music_path = settings.assets_dir / "music" / music_name
            if music_path.exists():
                volume = float(template.get("music_volume", 0.07))
                bed = _decode_pcm(str(music_path)).astype(np.int32)
                if len(bed):
                    reps = total // len(bed) + 1
                    bed = np.tile(bed, reps)[:total]
                    fade = SAMPLE_RATE * 2
                    ramp = np.linspace(1.0, 0.0, min(fade, total))
                    bed[-len(ramp):] = (bed[-len(ramp):] * ramp).astype(np.int32)
                    mix += (bed * volume).astype(np.int32)
            else:
                logger.warning("Template music '%s' not found under assets/music", music_name)

        peak = int(np.abs(mix).max()) or 1
        if peak > 32000:
            mix = (mix * (32000 / peak)).astype(np.int32)

        with wave.open(str(out_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(mix.astype(np.int16).tobytes())
        return out_path
