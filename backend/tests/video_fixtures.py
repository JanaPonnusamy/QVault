"""Synthetic local MP4 generation for frame-extraction tests.

Pure ffmpeg lavfi sources -- no network, no real media files -- so tests are
fast, deterministic, and double as genuine "local MP4" verification for the
frame extraction engine (every acquisition source downloads to a local
video.mp4 before this stage runs; these fixtures exercise that exact input).
"""
import subprocess
from pathlib import Path

from app.config.settings import settings


def make_color_video(path: Path, segments: list[tuple[str, float]], size: str = "320x240", rate: int = 10) -> None:
    """`segments`: list of (ffmpeg color name, duration seconds). Concatenates
    solid-color clips so a scene-detection filter sees a clean cut at each boundary."""
    inputs: list[str] = []
    refs: list[str] = []
    for i, (color, dur) in enumerate(segments):
        inputs += ["-f", "lavfi", "-i", f"color=c={color}:size={size}:duration={dur}:rate={rate}"]
        refs.append(f"[{i}:v]")
    filter_complex = "".join(refs) + f"concat=n={len(segments)}:v=1:a=0[out]"
    subprocess.run(
        [settings.ffmpeg_path, "-y", *inputs, "-filter_complex", filter_complex, "-map", "[out]", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )


def make_color_text_video(
    path: Path, segments: list[tuple[str, str, float]], size: str = "320x240", rate: int = 10
) -> None:
    """`segments`: list of (ffmpeg color name, text, duration). Each segment has
    both a distinct background color (a real scene-detection trigger) and
    distinct text (an OCR-diff trigger), concatenated -- for tests that need
    both signals to change together."""
    import tempfile

    with tempfile.TemporaryDirectory(dir=path.parent) as tmpdir:
        parts = []
        for i, (color, text, dur) in enumerate(segments):
            part = Path(tmpdir) / f"seg_{i}.mp4"
            safe = text.replace("'", "\\'").replace(":", "\\:")
            subprocess.run(
                [
                    settings.ffmpeg_path, "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:size={size}:duration={dur}:rate={rate}",
                    "-vf", f"drawtext=text='{safe}':fontcolor=white:fontsize=24:x=10:y=10",
                    str(part),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            parts.append(part)

        inputs: list[str] = []
        refs: list[str] = []
        for i, part in enumerate(parts):
            inputs += ["-i", str(part)]
            refs.append(f"[{i}:v]")
        filter_complex = "".join(refs) + f"concat=n={len(parts)}:v=1:a=0[out]"
        subprocess.run(
            [settings.ffmpeg_path, "-y", *inputs, "-filter_complex", filter_complex, "-map", "[out]", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )


def make_text_video(path: Path, segments: list[tuple[str, float]], size: str = "320x240", rate: int = 5) -> None:
    """`segments`: list of (text, duration seconds) on a white background, each
    shown only during its own time window (so OCR sampling sees distinct text
    per segment and repeats within a segment)."""
    total = sum(d for _, d in segments)
    filters = []
    t = 0.0
    for text, dur in segments:
        safe = text.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"drawtext=text='{safe}':fontcolor=black:fontsize=28:x=10:y=10:enable='between(t,{t},{t + dur})'"
        )
        t += dur
    subprocess.run(
        [
            settings.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"color=c=white:size={size}:duration={total}:rate={rate}",
            "-vf", ",".join(filters),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
