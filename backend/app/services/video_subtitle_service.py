"""SRT subtitle export from the video timeline's caption chunks."""

from __future__ import annotations

from pathlib import Path

from app.services.video_timeline_service import VideoTimeline


def _stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(timeline: VideoTimeline, out_path: Path) -> Path:
    lines: list[str] = []
    for i, chunk in enumerate(timeline.captions, start=1):
        text = " ".join(w.text for w in chunk.words)
        lines.append(str(i))
        lines.append(f"{_stamp(chunk.start)} --> {_stamp(chunk.end)}")
        lines.append(text)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
