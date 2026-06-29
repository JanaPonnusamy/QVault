from concurrent.futures import ThreadPoolExecutor

from app.config.settings import settings
from app.database.session import SessionLocal
from app.models.acquisition import AcquisitionJob
from app.services import notification_service
from app.shared.logging import get_logger

logger = get_logger("acquisition_worker")
_executor = ThreadPoolExecutor(
    max_workers=max(2, settings.ncert_concurrent_downloads + 1),
    thread_name_prefix="acquisition",
)


def submit_job(job_id: int) -> None:
    _executor.submit(_run_job, job_id)


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(AcquisitionJob, job_id)
        if not job:
            return

        if job.job_type in ("scan", "download", "refresh"):
            from app.services.ncert_service import NcertService

            service = NcertService(db)
            {"scan": service.run_scan, "download": service.run_download, "refresh": service.run_refresh}[
                job.job_type
            ](job)
        elif job.job_type == "document_extract":
            from app.services.knowledge_service import KnowledgeService

            KnowledgeService(db).run_extraction(job)
        else:
            job.status = "failed"
            job.error = f"Unknown job type: {job.job_type}"
            db.commit()
        logger.info("Acquisition job %s (%s) -> %s", job_id, job.job_type, job.status)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Acquisition job %s failed", job_id)
        db.rollback()
        job = db.get(AcquisitionJob, job_id)
        if job:
            job.status = "failed"
            job.stage = "Failed"
            job.error = str(exc)
            db.commit()
            notification_service.push(db, "error", "Acquisition failed", str(exc), job.source)
    finally:
        db.close()
