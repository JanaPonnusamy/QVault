from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.repositories.user_repository import UserRepository
from app.shared.security import decode_access_token
from app.api.schemas import (
    AnalyzeSummary,
    EstimateRequest,
    EstimateResponse,
    FrameOut,
    JobCreate,
    JobOut,
    OcrRequest,
    QuestionOut,
    QuestionUpdate,
)
from app.models.rbac import User
from app.services.analysis_service import AnalysisService
from app.services.extraction_service import ExtractionService
from app.services.frame_extraction_service import ExtractionOptions

router = APIRouter(prefix="/api/extractor", tags=["youtube_extractor"])

MODULE = "youtube_extractor"


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return ExtractionService(db).list_jobs("youtube")


@router.post("/jobs", response_model=JobOut)
def create_job(
    payload: JobCreate,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    options = ExtractionOptions.from_payload(payload)
    return ExtractionService(db).create_job(payload.url, user.id, extraction_options=options)


@router.post("/estimate", response_model=EstimateResponse)
def estimate(
    payload: EstimateRequest,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    return ExtractionService(db).estimate_frames(payload.url, "youtube", payload.sampling_fps)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    job = ExtractionService(db).get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    service = ExtractionService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    service.delete_job(job)
    return {"status": "deleted"}


@router.get("/jobs/{job_id}/frames", response_model=list[FrameOut])
def list_frames(
    job_id: int,
    probable_only: bool = Query(False),
    include_duplicates: bool = Query(True),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    frames = ExtractionService(db).list_frames(job_id)
    if probable_only:
        frames = [f for f in frames if f.is_question]
    if not include_duplicates:
        frames = [f for f in frames if not f.is_duplicate]
    return frames


@router.post("/jobs/{job_id}/analyze", response_model=AnalyzeSummary)
def analyze_job(
    job_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    service = ExtractionService(db)
    if not service.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return AnalyzeSummary(**AnalysisService(db).analyze_job(job_id))


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


@router.post("/jobs/{job_id}/ocr", response_model=list[QuestionOut])
def run_ocr(
    job_id: int,
    payload: OcrRequest,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    service = ExtractionService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
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


def _set_status(db: Session, question_id: int, status: str) -> QuestionOut:
    service = ExtractionService(db)
    question = service.repo.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return service.update_question(question, status=status)


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
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    base = f"questions_job_{job_id}"
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
        content=service.export(job),
        headers={"Content-Disposition": f"attachment; filename={base}.json"},
    )
