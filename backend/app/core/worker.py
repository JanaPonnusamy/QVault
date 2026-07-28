import json
from concurrent.futures import ThreadPoolExecutor

from app.config.settings import settings
from app.database.session import SessionLocal
from app.integrations.ffmpeg import FFmpeg
from app.integrations.video_providers import get_provider
from app.models.extraction import ExtractionJob, Frame
from app.services.frame_extraction_service import ExtractionOptions, FrameExtractionService
from app.shared.logging import get_logger

logger = get_logger("worker")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="extractor")


def submit_job(job_id: int) -> None:
    _executor.submit(_run_job, job_id)


def _set(db, job: ExtractionJob, **fields) -> None:
    for key, value in fields.items():
        setattr(job, key, value)
    db.commit()


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(ExtractionJob, job_id)
        if not job:
            return

        job_dir = settings.jobs_dir / str(job_id)
        frames_dir = job_dir / "frames"

        provider = get_provider(job.source)

        if job.url.startswith("upload://"):
            # Locally uploaded video (drag & drop) — the file is already in the
            # job dir; skip the download stage and probe the local file directly.
            _set(db, job, status="downloading", stage="Preparing uploaded video", progress=10)
            matches = sorted(job_dir.glob("video.*"))
            if not matches:
                raise FileNotFoundError("Uploaded video file not found for this job")
            video_path = matches[0]
            info = {
                "title": job.title or job.url[len("upload://"):],
                "video_id": "",
                "duration": int(FFmpeg.probe_duration(str(video_path)) or 0),
                "path": str(video_path),
                "caption": "", "author": "", "upload_date": "", "thumbnail": "", "meta": {},
            }
        else:
            _set(db, job, status="downloading", stage="Downloading video", progress=10)
            info = provider.fetch(job.url, job_dir)
        _set(
            db, job,
            title=info["title"],
            video_id=info["video_id"],
            duration=info["duration"],
            caption=info.get("caption", ""),
            author=info.get("author", ""),
            upload_date=info.get("upload_date", ""),
            thumbnail_url=info.get("thumbnail", ""),
            source_meta=json.dumps(info.get("meta") or {}),
            status="extracting",
            stage="Extracting frames",
            progress=55,
        )

        duration = info["duration"] or FFmpeg.probe_duration(info["path"])
        options = ExtractionOptions.from_job(job)
        extracted = FrameExtractionService().extract(info["path"], frames_dir, options, duration)
        frames = [
            Frame(job_id=job.id, index=i, timestamp=ts, filename=name)
            for i, (name, ts) in enumerate(extracted)
        ]
        db.add_all(frames)
        _set(db, job, frame_count=len(frames), status="analyzing", stage="Detecting & reading frames (OCR)", progress=70)

        try:
            from app.services.analysis_service import AnalysisService

            summary = AnalysisService(db).analyze_job(job_id)
            logger.info("Job %s analysis: %s", job_id, summary)
        except Exception:  # noqa: BLE001
            logger.exception("Job %s analysis failed (frames still available)", job_id)
            db.rollback()

        if provider.classify_frames:
            _set(db, job, stage="Classifying content", progress=90)
            try:
                from app.services.classification_service import ClassificationService

                summary = ClassificationService(db).process_job(job_id)
                logger.info("Job %s classification: %s", job_id, summary)
            except Exception:  # noqa: BLE001
                logger.exception("Job %s classification failed (frames still available)", job_id)
                db.rollback()

        _set(db, job, status="ready", stage="Ready", progress=100)
        logger.info("Job %s ready with %s frames", job_id, len(frames))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        db.rollback()
        job = db.get(ExtractionJob, job_id)
        if job:
            job.status = "failed"
            job.stage = "Failed"
            job.error = str(exc)
            db.commit()
    finally:
        db.close()
