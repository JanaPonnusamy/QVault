import re
from pathlib import Path


class SubtitleParser:
    """Converts WebVTT subtitle files (as downloaded by the existing
    YTDLPWrapper.download_subtitles) into plain deduplicated text."""

    _TIMESTAMP = re.compile(r"^\d{2}:\d{2}(:\d{2})?\.\d{3}\s+-->")
    _TAG = re.compile(r"<[^>]+>")

    @classmethod
    def to_text(cls, vtt_path):
        path = Path(vtt_path)

        if not path.exists():
            return ""

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

        seen = set()
        output = []

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
                continue

            if cls._TIMESTAMP.match(line):
                continue

            # cue identifiers are bare integers
            if line.isdigit():
                continue

            text = cls._TAG.sub("", line).strip()

            if not text:
                continue

            key = text.lower()

            # auto-generated captions repeat lines across rolling cues
            if key in seen:
                continue

            seen.add(key)
            output.append(text)

        return "\n".join(output)
