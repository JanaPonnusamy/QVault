from pathlib import Path

import yt_dlp


class YtDlp:
    @staticmethod
    def download_video(url: str, output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "merge_output_format": "mp4",
            "outtmpl": str(output_dir / "video.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        path = output_dir / "video.mp4"
        if not path.exists():
            for candidate in output_dir.glob("video.*"):
                path = candidate
                break

        return {
            "title": info.get("title", ""),
            "video_id": info.get("id", ""),
            "duration": int(info.get("duration") or 0),
            "path": str(path),
        }
