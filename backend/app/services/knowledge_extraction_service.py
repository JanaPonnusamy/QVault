import hashlib
from pathlib import Path

from app.config.knowledge_config import PIPELINE_VERSION
from app.models.extraction_result import ExtractionResult
from app.services.knowledge_frame_extraction_service import FrameExtractionService
from app.services.ocr_service import OCRService
from app.services.subtitle_parser import SubtitleParser
from app.services.whisper_wrapper import WhisperWrapper
from app.services.yt_dlp_wrapper import YTDLPWrapper


class KnowledgeExtractionService:
    """Turns any supported source into text files on disk (never into SQLite).

    Dispatcher architecture: ``extract`` routes on ``document_type``. Adding
    PDF/audio/image/website support later means adding one extractor method
    and one dispatch entry - callers never change."""

    WHISPER_VERSION = "faster-whisper-base"

    # Text artifacts are the product; large media is deleted after extraction.
    KEEP_MEDIA = False

    def __init__(self):
        self.frames = FrameExtractionService()

        self._extractors = {
            "youtube_video": self._extract_video,
        }

    @property
    def processing_version(self):
        return (
            f"pipeline-{PIPELINE_VERSION}"
            f"|{self.WHISPER_VERSION}"
            f"|{OCRService.ENGINE_VERSION}"
        )

    def extract(
        self,
        document_type,
        url,
        source_reference,
        title,
        document_dir,
        progress=None,
    ) -> ExtractionResult:
        extractor = self._extractors.get(document_type)

        if extractor is None:
            raise RuntimeError(
                f"Unsupported document type '{document_type}'. "
                f"Available: {', '.join(self._extractors)}"
            )

        return extractor(url, source_reference, title, document_dir, progress)

    # ------------------------------------------------------------- video --

    def _extract_video(self, url, source_reference, title, document_dir, progress):
        notify = progress or (lambda stage: None)

        doc_dir = Path(document_dir)
        doc_dir.mkdir(parents=True, exist_ok=True)

        # -- metadata ------------------------------------------------------
        notify("DOWNLOADING")

        language = ""
        duration = 0

        try:
            info = YTDLPWrapper.extract(url) or {}
            title = info.get("title") or title
            language = info.get("language") or ""
            duration = int(info.get("duration") or 0)
        except Exception:
            # metadata is best-effort; extraction continues with search-provided title
            pass

        # -- downloads (audio required, video/subtitles best-effort) --------
        audio_path = doc_dir / "audio.mp3"
        video_path = doc_dir / "video.mp4"

        audio_error = None

        try:
            YTDLPWrapper.download_audio(url, str(doc_dir / "audio.%(ext)s"))
        except Exception as error:  # noqa: BLE001
            audio_error = error

        try:
            YTDLPWrapper.download_video(url, str(doc_dir / "video.%(ext)s"))
        except Exception:
            pass

        try:
            YTDLPWrapper.download_subtitles(url, str(doc_dir / "subs.%(ext)s"))
        except Exception:
            pass

        media_bytes = sum(
            f.stat().st_size
            for f in (audio_path, video_path)
            if f.exists()
        )

        # -- transcript (whisper) -------------------------------------------
        notify("TRANSCRIBING")

        transcript_text = ""

        if audio_path.exists():
            transcript_text = WhisperWrapper.transcribe_file(str(audio_path)).strip()

        transcript_path = None

        if transcript_text:
            transcript_path = doc_dir / "transcript.txt"
            transcript_path.write_text(transcript_text, encoding="utf-8")

        # -- subtitles -------------------------------------------------------
        subtitle_text = ""
        subtitle_path = None

        vtt_files = sorted(doc_dir.glob("*.vtt"))

        if vtt_files:
            subtitle_text = SubtitleParser.to_text(vtt_files[0]).strip()

            if subtitle_text:
                subtitle_path = doc_dir / "subtitle.txt"
                subtitle_path.write_text(subtitle_text, encoding="utf-8")

        # -- OCR --------------------------------------------------------------
        notify("OCR")

        ocr_text = ""
        ocr_path = None

        if video_path.exists():
            try:
                frame_paths = self.frames.extract_frames(
                    video_path, doc_dir / "frames"
                )
                ocr_lines = OCRService.read_frames(frame_paths)
                ocr_text = "\n".join(ocr_lines).strip()
            except Exception:
                # on-screen text is supplementary; transcript remains primary
                ocr_text = ""

        if ocr_text:
            ocr_path = doc_dir / "ocr.txt"
            ocr_path.write_text(ocr_text, encoding="utf-8")

        # -- merge -------------------------------------------------------------
        sections = []

        if transcript_text:
            sections.append("=== TRANSCRIPT (AUDIO) ===\n" + transcript_text)

        if subtitle_text:
            sections.append("=== SUBTITLES ===\n" + subtitle_text)

        if ocr_text:
            sections.append("=== ON-SCREEN TEXT (OCR) ===\n" + ocr_text)

        merged_text = "\n\n".join(sections).strip()

        if not merged_text:
            detail = f" Audio download failed: {audio_error}." if audio_error else ""
            raise RuntimeError(
                f"No text could be extracted from {url}."
                f"{detail} No transcript, subtitles or on-screen text found."
            )

        merged_path = doc_dir / "merged.txt"
        merged_path.write_text(merged_text, encoding="utf-8")

        # -- cleanup large media ------------------------------------------------
        if not self.KEEP_MEDIA:
            self._cleanup_media(doc_dir)

        result = ExtractionResult(
            document_type="youtube_video",
            source_reference=source_reference,
            title=title,
            url=url,
            language=language,
            duration=duration,
            word_count=len(merged_text.split()),
            character_count=len(merged_text),
            file_size=media_bytes,
            checksum=hashlib.sha256(merged_text.encode("utf-8")).hexdigest(),
            processing_version=self.processing_version,
            transcript_path=str(transcript_path) if transcript_path else None,
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            ocr_path=str(ocr_path) if ocr_path else None,
            merged_text_path=str(merged_path),
        )

        return result

    # ------------------------------------------------------------ cleanup --

    # media remnants including yt-dlp partial downloads
    _MEDIA_PATTERNS = (
        "*.mp3", "*.mp4", "*.m4a", "*.webm", "*.mkv",
        "*.vtt", "*.part", "*.ytdl",
    )

    @classmethod
    def _cleanup_media(cls, doc_dir):
        doc_dir = Path(doc_dir)

        for pattern in cls._MEDIA_PATTERNS:
            for media in doc_dir.glob(pattern):
                try:
                    media.unlink()
                except OSError:
                    pass

        frames_dir = doc_dir / "frames"

        if frames_dir.exists():
            for frame in frames_dir.glob("*.jpg"):
                try:
                    frame.unlink()
                except OSError:
                    pass

            try:
                frames_dir.rmdir()
            except OSError:
                pass
