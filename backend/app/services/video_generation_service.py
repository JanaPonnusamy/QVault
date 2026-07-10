"""Video generation orchestrator.

Queues render jobs on the shared ``acquisition_jobs`` table / acquisition
worker (``job_type="video_render"``) and drives the full pipeline for one
video: load questions → narration script → TTS → timeline → audio mixdown →
streamed frame rendering → SRT → thumbnail → registry row update.

Renders are CPU-bound, so a semaphore caps concurrent renders at
``settings.video_concurrent_renders`` regardless of worker pool size.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core import acquisition_worker
from app.models.acquisition import AcquisitionJob
from app.models.video import Video
from app.repositories.video_repository import VideoRepository
from app.services import notification_service
from app.services.video_audio_service import VideoAudioService
from app.services.video_render_service import VideoRenderService, list_templates, load_template
from app.services.video_source_service import VideoSourceService
from app.services.video_timeline_service import VideoTimelineService
from app.shared.logging import get_logger

logger = get_logger("video_generation")

_render_gate = threading.Semaphore(max(1, settings.video_concurrent_renders))

KIND_DIRS = {"video": "videos", "short": "shorts", "reel": "reels"}
KIND_DEFAULT_COUNT = {"video": 25, "short": 1, "reel": 1}
RESOLUTIONS = {"landscape": (1920, 1080), "portrait": (1080, 1920)}


def _slug(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:limit].rstrip("-") or "quiz"


class VideoGenerationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VideoRepository(db)
        self.sources = VideoSourceService()
        self.timeline_service = VideoTimelineService()

    # ---------------- queueing
    def queue(
        self,
        *,
        source_file: str,
        kind: str = "video",
        orientation: str | None = None,
        category: str = "General Knowledge",
        topic: str | None = None,
        question_count: int | None = None,
        offset: int = 0,
        shuffle_seed: int | None = None,
        template: str | None = None,
        tts_provider: str | None = None,
        tts_voice: str | None = None,
        user_id: int | None = None,
    ) -> tuple[Video, AcquisitionJob]:
        if kind not in KIND_DIRS:
            raise ValueError(f"Unknown video kind '{kind}'")
        orientation = orientation or ("landscape" if kind == "video" else "portrait")
        if orientation not in RESOLUTIONS:
            raise ValueError(f"Unknown orientation '{orientation}'")
        template = template or settings.video_template
        load_template(template)  # fail fast on unknown templates
        count = question_count or KIND_DEFAULT_COUNT[kind]
        questions = self.sources.load(
            source_file, topic=topic, count=count, offset=offset, shuffle_seed=shuffle_seed
        )

        width, height = RESOLUTIONS[orientation]
        if kind == "video":
            title = f"{category} Quiz — {len(questions)} Questions"
        else:
            title = questions[0].question[:140]
        video = self.repo.add(
            Video(
                title=title,
                kind=kind,
                orientation=orientation,
                width=width,
                height=height,
                fps=settings.video_fps,
                category=category,
                source_file=source_file,
                topic=topic or "",
                question_count=len(questions),
                question_ids=json.dumps([q.id for q in questions]),
                template=template,
                tts_provider=tts_provider or settings.tts_provider,
                tts_voice=tts_voice or settings.tts_voice,
                status="queued",
                created_by=user_id,
            )
        )
        payload = json.dumps(
            {
                "video_id": video.id,
                "offset": offset,
                "shuffle_seed": shuffle_seed,
            }
        )
        job = AcquisitionJob(
            source="video",
            job_type="video_render",
            status="queued",
            stage="Queued",
            payload=payload,
            created_by=user_id,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        acquisition_worker.submit_job(job.id)
        return video, job

    def queue_batch(self, *, batch_count: int, question_count: int | None = None, **kwargs) -> list[Video]:
        """Queue N videos over sequential question windows of the source file."""
        kind = kwargs.get("kind", "video")
        per = question_count or KIND_DEFAULT_COUNT[kind]
        usable = len(
            self.sources.load(
                kwargs["source_file"],
                topic=kwargs.get("topic"),
                count=10**9,
                offset=0,
            )
        )
        videos = []
        for i in range(batch_count):
            offset = (i * per) % max(usable - per + 1, 1) if usable > per else 0
            video, _ = self.queue(
                question_count=per, offset=offset, **kwargs
            )
            videos.append(video)
        return videos

    # ---------------- preview
    def preview(
        self,
        *,
        source_file: str,
        kind: str = "video",
        category: str = "General Knowledge",
        topic: str | None = None,
        question_count: int | None = None,
        offset: int = 0,
        shuffle_seed: int | None = None,
    ) -> dict:
        count = question_count or KIND_DEFAULT_COUNT.get(kind, 25)
        questions = self.sources.load(
            source_file, topic=topic, count=count, offset=offset, shuffle_seed=shuffle_seed
        )
        timeline = self.timeline_service.estimate(questions, kind, category)
        return timeline.preview()

    # ---------------- worker entry point
    def run_render(self, job: AcquisitionJob) -> None:
        payload = json.loads(job.payload or "{}")
        video = self.repo.get(int(payload.get("video_id", 0)))
        if not video:
            job.status = "failed"
            job.error = "Video row not found"
            self.db.commit()
            return
        try:
            with _render_gate:
                self._render(job, video, payload)
            job.status = "completed"
            job.stage = "Completed"
            job.progress = 100
            self.db.commit()
            notification_service.push(
                self.db, "success", "Video ready", video.title, "video"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video %s render failed", video.id)
            self.db.rollback()
            video = self.repo.get(video.id)
            if video:
                video.status = "failed"
                video.error = str(exc)[:2000]
                self.db.commit()
            raise

    def _render(self, job: AcquisitionJob, video: Video, payload: dict) -> None:
        def progress(pct: int, stage: str) -> None:
            job.status = "processing"
            job.progress = min(pct, 99)
            job.stage = stage
            video.status = "rendering"
            self.db.commit()

        progress(2, "Loading questions")
        questions = self.sources.load(
            video.source_file,
            topic=video.topic or None,
            count=video.question_count,
            offset=int(payload.get("offset") or 0),
            shuffle_seed=payload.get("shuffle_seed"),
        )

        template = load_template(video.template)
        timeline = self.timeline_service.build(
            questions,
            video.kind,
            video.category,
            provider_name=video.tts_provider,
            voice=video.tts_voice or None,
            progress=progress,
        )

        work_dir = settings.output_dir / ".work" / f"video_{video.id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        out_dir = settings.output_dir / KIND_DIRS[video.kind]
        base = f"qv_{video.id:05d}_{_slug(video.topic or video.category)}"
        out_path = out_dir / f"{base}.mp4"
        srt_path = out_dir / f"{base}.srt"
        thumb_path = out_dir / f"{base}.jpg"

        progress(48, "Mixing audio")
        audio_path = VideoAudioService().assemble(timeline, template, work_dir / "audio.wav")

        progress(50, "Rendering frames")
        renderer = VideoRenderService(timeline, template, video.orientation, fps=video.fps)
        renderer.render(audio_path, out_path, thumbnail_path=thumb_path, progress=progress)

        from app.services.video_subtitle_service import write_srt

        write_srt(timeline, srt_path)

        video.duration = timeline.duration
        video.file_path = str(out_path)
        video.file_size = out_path.stat().st_size
        video.srt_path = str(srt_path)
        video.thumbnail_path = str(thumb_path) if thumb_path.exists() else ""
        video.status = "completed"
        video.error = ""
        self.db.commit()

        try:
            audio_path.unlink(missing_ok=True)
            work_dir.rmdir()
        except OSError:
            pass

    # ---------------- housekeeping
    def delete(self, video: Video) -> None:
        for path in (video.file_path, video.srt_path, video.thumbnail_path):
            if path:
                Path(path).unlink(missing_ok=True)
        self.repo.delete(video)

    @staticmethod
    def templates() -> list[dict]:
        return list_templates()
