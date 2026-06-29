from concurrent.futures import ThreadPoolExecutor

from app.config.settings import settings
from app.database.session import SessionLocal
from app.integrations.ffmpeg import FFmpeg
from app.integrations.ytdlp import YtDlp
from app.models.extraction import ExtractionJob, Frame
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

        _set(db, job, status="downloading", stage="Downloading video", progress=10)
        info = YtDlp.download_video(job.url, job_dir)
        _set(
            db, job,
            title=info["title"],
            video_id=info["video_id"],
            duration=info["duration"],
            status="extracting",
            stage="Extracting frames",
            progress=55,
        )

        duration = info["duration"] or FFmpeg.probe_duration(info["path"])
        if duration and duration > 0:
            interval = max(settings.frame_min_interval, duration / settings.frame_max_count)
        else:
            interval = settings.frame_min_interval

        extracted = FFmpeg.extract_frames(info["path"], frames_dir, interval)
        frames = [
            Frame(job_id=job.id, index=i, timestamp=ts, filename=name)
            for i, (name, ts) in enumerate(extracted)
        ]
        db.add_all(frames)
        _set(db, job, frame_count=len(frames), status="analyzing", stage="Detecting question frames", progress=70)

        try:
            from app.services.analysis_service import AnalysisService

            summary = AnalysisService(db).analyze_job(job_id)
            logger.info("Job %s analysis: %s", job_id, summary)
        except Exception:  # noqa: BLE001
            logger.exception("Job %s analysis failed (frames still available)", job_id)
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
