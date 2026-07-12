import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    CatalogStats,
    ChapterOut,
    ExamOut,
    ExamTreeOut,
    SubjectOut,
    SyllabusImportLogOut,
    TopicOut,
    UnitOut,
)
from app.models.rbac import User
from app.repositories.catalog_repository import CatalogRepository
from app.services.syllabus_import_service import SyllabusImportService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

MODULE = "catalog"


@router.get("/stats", response_model=CatalogStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return CatalogStats(**CatalogRepository(db).stats())


@router.get("/exams", response_model=list[ExamOut])
def list_exams(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return CatalogRepository(db).list_exams()


@router.get("/exams/{exam_id}/tree", response_model=ExamTreeOut)
def exam_tree(
    exam_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    exam = CatalogRepository(db).exam_tree(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.get("/exams/{exam_id}/subjects", response_model=list[SubjectOut])
def list_subjects(
    exam_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = CatalogRepository(db)
    if not repo.get_exam(exam_id):
        raise HTTPException(status_code=404, detail="Exam not found")
    return repo.list_subjects(exam_id)


@router.get("/subjects/{subject_id}/units", response_model=list[UnitOut])
def list_units(
    subject_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = CatalogRepository(db)
    if not repo.get_subject(subject_id):
        raise HTTPException(status_code=404, detail="Subject not found")
    return repo.list_units(subject_id)


@router.get("/units/{unit_id}/chapters", response_model=list[ChapterOut])
def list_chapters(
    unit_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = CatalogRepository(db)
    if not repo.get_unit(unit_id):
        raise HTTPException(status_code=404, detail="Unit not found")
    return repo.list_chapters(unit_id)


@router.get("/chapters/{chapter_id}/topics", response_model=list[TopicOut])
def list_topics(
    chapter_id: uuid.UUID,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = CatalogRepository(db)
    if not repo.get_chapter(chapter_id):
        raise HTTPException(status_code=404, detail="Chapter not found")
    return repo.list_topics(chapter_id)


@router.get("/import/logs", response_model=list[SyllabusImportLogOut])
def import_logs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return SyllabusImportService(db).list_logs()


@router.post("/import", response_model=SyllabusImportLogOut)
async def import_syllabus(
    exam_code: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    name = (file.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        log = SyllabusImportService(db).import_pdf(
            file.filename or "syllabus.pdf", data, exam_code, user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if log.status == "failed":
        raise HTTPException(status_code=422, detail=log.error or "Import failed")
    return log
