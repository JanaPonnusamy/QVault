import re
import subprocess
from pathlib import Path

from app.config.settings import settings

_PTS_TIME_RE = re.compile(r"pts_time:([\d.]+)")


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
    def probe_fps(video_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    settings.ffprobe_path,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=avg_frame_rate",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            raw = result.stdout.strip()
            if "/" in raw:
                num, den = raw.split("/")
                return float(num) / float(den) if float(den) else 0.0
            return float(raw or 0.0)
        except (subprocess.CalledProcessError, ValueError, ZeroDivisionError):
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

    @staticmethod
    def extract_frames_sampled(
        video_path: str, frames_dir: Path, fps: float | None
    ) -> list[tuple[str, float]]:
        """Frame Sampling stage: `fps=None` decodes and writes every frame (no
        `fps=` filter at all -- needed to catch sub-300ms flash content); a
        numeric `fps` resamples to that rate. Streams frame-by-frame through
        ffmpeg's own decoder/muxer the whole way -- the video and its frames are
        never loaded into this process's memory at once, only one JPG at a time
        is written to disk by ffmpeg itself."""
        frames_dir.mkdir(parents=True, exist_ok=True)
        vf = f"fps={fps},showinfo" if fps else "showinfo"
        try:
            result = subprocess.run(
                [
                    settings.ffmpeg_path,
                    "-i", video_path,
                    "-vf", vf,
                    "-vsync", "0",
                    "-q:v", "2",
                    str(frames_dir / "sample_%06d.jpg"),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            if "received no packets" in (exc.stderr or ""):
                return []
            raise
        timestamps = [round(float(m), 3) for m in _PTS_TIME_RE.findall(result.stderr)]
        files = sorted(frames_dir.glob("sample_*.jpg"))
        return list(zip((f.name for f in files), timestamps))

    @staticmethod
    def extract_frames_scene(
        video_path: str, frames_dir: Path, threshold: float = 0.35, sample_fps: float | None = None
    ) -> list[tuple[str, float]]:
        """Extract only frames where the scene changes significantly (new slide,
        camera cut, screen change). Never fires on the very first frame -- callers
        needing an opening frame should extract it separately. `sample_fps`
        optionally pre-resamples before scene comparison (None = examine every
        decoded frame, catching brief flash cuts; a coarser fps trades recall for
        speed on longer videos)."""
        frames_dir.mkdir(parents=True, exist_ok=True)
        select = f"select='gt(scene,{threshold})',showinfo"
        vf = f"fps={sample_fps},{select}" if sample_fps else select
        try:
            result = subprocess.run(
                [
                    settings.ffmpeg_path,
                    "-i", video_path,
                    "-vf", vf,
                    "-vsync", "vfr",
                    "-q:v", "2",
                    str(frames_dir / "scene_%05d.jpg"),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            # A video with no scene changes above `threshold` is a valid outcome,
            # not a failure -- ffmpeg's image2 muxer errors out ("Nothing was
            # written... received no packets") when the select filter matches
            # zero frames, since it has nothing to write to the %05d sequence.
            if "received no packets" in (exc.stderr or ""):
                return []
            raise
        timestamps = [round(float(m), 2) for m in _PTS_TIME_RE.findall(result.stderr)]
        files = sorted(frames_dir.glob("scene_*.jpg"))
        return list(zip((f.name for f in files), timestamps))

    @staticmethod
    def extract_single_frame(video_path: str, frames_dir: Path, filename: str, timestamp: float = 0.0) -> None:
        frames_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                settings.ffmpeg_path,
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                str(frames_dir / filename),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
