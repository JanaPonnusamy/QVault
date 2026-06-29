import subprocess
from pathlib import Path

from app.config.settings import settings


class FFmpeg:
    @staticmethod
    def probe_duration(video_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    settings.ffprobe_path,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip() or 0.0)
        except (subprocess.CalledProcessError, ValueError):
            return 0.0

    @staticmethod
    def extract_frames(video_path: str, frames_dir: Path, interval: float) -> list[tuple[str, float]]:
        frames_dir.mkdir(parents=True, exist_ok=True)
        fps = 1.0 / interval if interval > 0 else 0.5
        subprocess.run(
            [
                settings.ffmpeg_path,
                "-i", video_path,
                "-vf", f"fps={fps}",
                "-q:v", "2",
                str(frames_dir / "frame_%05d.jpg"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        frames: list[tuple[str, float]] = []
        for i, file in enumerate(sorted(frames_dir.glob("frame_*.jpg"))):
            frames.append((file.name, round(i * interval, 2)))
        return frames
