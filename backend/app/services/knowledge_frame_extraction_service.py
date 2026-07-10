import shutil
import subprocess
from pathlib import Path


class FrameExtractionService:
    """Samples still frames from a video with ffmpeg so OCR can read on-screen
    text. Reuses the ffmpeg binary already required by yt-dlp's audio
    postprocessor; no additional external dependency."""

    DEFAULT_INTERVAL_SECONDS = 10
    MAX_FRAMES = 60
    FRAME_HEIGHT = 720

    def __init__(self):
        self._ffmpeg = shutil.which("ffmpeg")

        if not self._ffmpeg:
            raise RuntimeError(
                "ffmpeg not found on PATH. It is required for frame extraction."
            )

    def extract_frames(
        self,
        video_path,
        output_dir,
        interval_seconds=None,
        max_frames=None,
    ):
        """Extracts one frame every ``interval_seconds`` into ``output_dir``
        as frame_0001.jpg, ... Returns the sorted list of frame paths."""

        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(str(video_path))

        interval = interval_seconds or self.DEFAULT_INTERVAL_SECONDS
        limit = max_frames or self.MAX_FRAMES

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pattern = str(output_dir / "frame_%04d.jpg")

        command = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vf", f"fps=1/{interval},scale=-2:{self.FRAME_HEIGHT}",
            "-frames:v", str(limit),
            "-q:v", "4",
            "-y",
            pattern,
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
        )

        frames = sorted(output_dir.glob("frame_*.jpg"))

        # ffmpeg errors with no frames produced is a real failure; an error
        # alongside produced frames (e.g. truncated tail) is usable output.
        if result.returncode != 0 and not frames:
            raise RuntimeError(
                f"ffmpeg frame extraction failed: {result.stderr.strip()[:500]}"
            )

        return [str(frame) for frame in frames]
