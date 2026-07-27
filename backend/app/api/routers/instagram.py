from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.config.settings import settings
from app.api.schemas import (
    AnalyzeSummary,
    EstimateRequest,
    EstimateResponse,
    FrameOut,
    InstagramStats,
    JobCreate,
    JobOut,
    OcrRequest,
    QuestionOut,
    QuestionUpdate,
)
from app.models.rbac import User
from app.repositories.user_repository import UserRepository
from app.services.analysis_service import AnalysisService
from app.services.classification_service import ClassificationService
from app.services.extraction_service import ExtractionService
from app.services.frame_extraction_service import ExtractionOptions
from app.shared.security import decode_access_token

router = APIRouter(prefix="/api/sources/instagram", tags=["instagram"])

MODULE = "instagram"
SOURCE = "instagram"

_ACTIVE = {"pending", "queued", "downloading", "extracting", "analyzing"}


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return ExtractionService(db).list_jobs(SOURCE)


@router.get("/stats", response_model=InstagramStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    jobs = ExtractionService(db).list_jobs(SOURCE)
    return InstagramStats(
        total=len(jobs),
        completed=sum(1 for j in jobs if j.status == "ready"),
        processing=sum(1 for j in jobs if j.status in _ACTIVE),
        failed=sum(1 for j in jobs if j.status == "failed"),
        frames=sum(j.frame_count for j in jobs),
    )


@router.post("/jobs", response_model=JobOut)
def create_job(
    payload: JobCreate,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    options = ExtractionOptions.from_payload(payload)
    return ExtractionService(db).create_job(payload.url, user.id, source=SOURCE, extraction_options=options)


_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".mpg", ".mpeg", ".ts", ".flv", ".gif"}


@router.post("/upload", response_model=JobOut)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    """Drag & drop a local video file → extract frames (reuses the full pipeline)."""
    name = file.filename or ""
    if Path(name).suffix.lower() not in _VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Please drop a video file (mp4, mov, webm, mkv, avi, m4v, ...).",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return ExtractionService(db).create_upload_job(name, data, user.id, source=SOURCE)


@router.post("/estimate", response_model=EstimateResponse)
def estimate(
    payload: EstimateRequest,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    return ExtractionService(db).estimate_frames(payload.url, SOURCE, payload.sampling_fps)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    job = _get(db, job_id)
    return job


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    service = ExtractionService(db)
    service.delete_job(_get(db, job_id))
    return {"status": "deleted"}


@router.get("/jobs/{job_id}/frames", response_model=list[FrameOut])
def list_frames(
    job_id: int,
    with_text_only: bool = Query(False),
    include_duplicates: bool = Query(False),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    _get(db, job_id)
    frames = ExtractionService(db).list_frames(job_id)
    if not include_duplicates:
        frames = [f for f in frames if not f.is_duplicate]
    if with_text_only:
        frames = [f for f in frames if f.ocr_text.strip()]
    return frames


@router.post("/jobs/{job_id}/analyze", response_model=AnalyzeSummary)
def analyze_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    _get(db, job_id)
    summary = AnalysisService(db).analyze_job(job_id)
    ClassificationService(db).process_job(job_id)
    return AnalyzeSummary(**summary)


@router.get("/frames/{frame_id}/image")
def frame_image(
    frame_id: int,
    token: str,
    db: Session = Depends(db_session),
):
    try:
        user_id = int(decode_access_token(token).get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = UserRepository(db).get(user_id)
    if not user or not user.has_permission(f"{MODULE}:view"):
        raise HTTPException(status_code=403, detail="Not permitted")

    service = ExtractionService(db)
    frame = service.repo.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    path = service.frame_path(frame)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Frame image missing")
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/jobs/{job_id}/video")
def job_video(
    job_id: int,
    token: str,
    db: Session = Depends(db_session),
):
    """Stream the acquired/uploaded video for in-panel playback (token in query
    because a <video> element cannot send an Authorization header)."""
    try:
        user_id = int(decode_access_token(token).get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = UserRepository(db).get(user_id)
    if not user or not user.has_permission(f"{MODULE}:view"):
        raise HTTPException(status_code=403, detail="Not permitted")

    _get(db, job_id)
    job_dir = settings.jobs_dir / str(job_id)
    matches = sorted(job_dir.glob("video.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Video not available for this job")
    return FileResponse(str(matches[0]), media_type="video/mp4")


@router.post("/jobs/{job_id}/ocr", response_model=list[QuestionOut])
def run_ocr(
    job_id: int,
    payload: OcrRequest,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    service = ExtractionService(db)
    _get(db, job_id)
    if not payload.frame_ids:
        raise HTTPException(status_code=400, detail="Select at least one frame")

    questions = []
    for frame_id in payload.frame_ids:
        frame = service.repo.get_frame(frame_id)
        if not frame or frame.job_id != job_id:
            continue
        questions.append(service.run_ocr(frame))
    return questions


@router.get("/jobs/{job_id}/questions", response_model=list[QuestionOut])
def list_questions(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    _get(db, job_id)
    return ExtractionService(db).list_questions(job_id)


@router.put("/questions/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    service = ExtractionService(db)
    question = service.repo.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return service.update_question(question, payload.text, payload.options, payload.status)


@router.post("/questions/{question_id}/approve", response_model=QuestionOut)
def approve_question(
    question_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    return _set_status(db, question_id, "approved")


@router.post("/questions/{question_id}/reject", response_model=QuestionOut)
def reject_question(
    question_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    return _set_status(db, question_id, "rejected")


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:update")),
):
    service = ExtractionService(db)
    question = service.repo.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    service.delete_question(question)
    return {"status": "deleted"}


@router.get("/jobs/{job_id}/export")
def export_job(
    job_id: int,
    format: str = Query("json", pattern="^(json|csv|sqlite)$"),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:export")),
):
    service = ExtractionService(db)
    job = _get(db, job_id)

    base = f"instagram_job_{job_id}"
    if format == "csv":
        return PlainTextResponse(
            service.export_csv(job),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={base}.csv"},
        )
    if format == "sqlite":
        return FileResponse(
            str(service.export_sqlite(job)),
            media_type="application/octet-stream",
            filename=f"{base}.sqlite",
        )
    return JSONResponse(
        content=service.export(job, include_frames=True),
        headers={"Content-Disposition": f"attachment; filename={base}.json"},
    )


def _get(db: Session, job_id: int):
    job = ExtractionService(db).get_job(job_id)
    if not job or job.source != SOURCE:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _set_status(db: Session, question_id: int, status: str) -> QuestionOut:
    service = ExtractionService(db)
    question = service.repo.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return service.update_question(question, status=status)
