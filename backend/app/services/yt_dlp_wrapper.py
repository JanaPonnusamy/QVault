
import yt_dlp

from app.integrations.ytdlp import CookieSource

# The default "web" player client alone increasingly gets a hard "The
# following content is not available on this app" error from YouTube for
# some videos, even with cookies. "android" bypasses that check for info
# extraction; keeping "web" alongside it still supplies the actual stream
# URLs (android's own formats require a PO token yt-dlp doesn't provide).
_YOUTUBE_PLAYER_CLIENTS = ["android", "web"]


def _apply_youtube_args(opts: dict, extra_opts: dict | None = None) -> dict:
    extra_opts = dict(extra_opts or {})
    youtube_args = {"player_client": list(_YOUTUBE_PLAYER_CLIENTS)}
    youtube_args.update((extra_opts.pop("extractor_args", None) or {}).get("youtube", {}))
    opts.update(extra_opts)
    opts["extractor_args"] = {"youtube": youtube_args}
    CookieSource().apply(opts)
    return opts


class YTDLPWrapper:

    @staticmethod
    def extract(url: str, extra_opts: dict | None = None):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        _apply_youtube_args(opts, extra_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def download_audio(url, output_template):
        opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
        _apply_youtube_args(opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    @staticmethod
    def download_video(url, output_template):
        opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
        }
        _apply_youtube_args(opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    @staticmethod
    def download_subtitles(url, output_template):
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt",
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True,
        }
        _apply_youtube_args(opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
