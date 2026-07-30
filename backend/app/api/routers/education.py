from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AcquisitionJobOut,
    EducationDocumentDetail,
    EducationDocumentList,
    EducationDocumentOut,
    EducationScanRequest,
    EducationSourceList,
    EducationSourceOut,
    EducationStatsOut,
)
from app.models.rbac import User
from app.services.education_acquisition_service import EducationAcquisitionService

router = APIRouter(prefix="/api/sources/education", tags=["education_acquisition"])

MODULE = "education_acquisition"


@router.get("/jobs", response_model=list[AcquisitionJobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return EducationAcquisitionService(db).list_jobs()


@router.post("/scan", response_model=AcquisitionJobOut)
def scan(
    payload: EducationScanRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    if not payload.root_urls and not payload.manual_urls and not payload.queries and not payload.rss_urls and not payload.government_urls:
        raise HTTPException(status_code=400, detail="Provide at least one query, root URL, manual URL, RSS URL, or government URL")
    return EducationAcquisitionService(db).start_scan(payload.model_dump(), user.id)


@router.get("/stats", response_model=EducationStatsOut)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return EducationStatsOut(**EducationAcquisitionService(db).stats())


@router.get("/sources", response_model=EducationSourceList)
def list_sources(
    q: str = "",
    institution_type: str = "",
    board: str = "",
    state: str = "",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = EducationAcquisitionService(db).list_sources(
        q=q, institution_type=institution_type, board=board, state=state, limit=limit, offset=offset,
    )
    return EducationSourceList(items=[EducationSourceOut.model_validate(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/documents", response_model=EducationDocumentList)
def list_documents(
    q: str = "",
    institution: str = "",
    state: str = "",
    district: str = "",
    board: str = "",
    document_type: str = "",
    tag: str = "",
    field_name: str = "",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = EducationAcquisitionService(db).list_documents(
        q=q,
        institution=institution,
        state=state,
        district=district,
        board=board,
        document_type=document_type,
        tag=tag,
        field_name=field_name,
        limit=limit,
        offset=offset,
    )
    return EducationDocumentList(
        items=[EducationDocumentOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}", response_model=EducationDocumentDetail)
def get_document(
    document_id: str,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    service = EducationAcquisitionService(db)
    document = service.repo.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    source = service.repo.get_source(document.source_id) if document.source_id else None
    return EducationDocumentDetail(
        **EducationDocumentOut.model_validate(document).model_dump(),
        fields=service.repo.document_fields(document.id),
        tags=service.repo.document_tags(document.id),
        source=EducationSourceOut.model_validate(source) if source else None,
    )


@router.get("/export")
def export_data(
    format: str = Query("json", pattern="^(json|csv|markdown|sqlite)$"),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:export")),
):
    service = EducationAcquisitionService(db)
    if format == "csv":
        return PlainTextResponse(
            service.export_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=education_knowledge.csv"},
        )
    if format == "markdown":
        return PlainTextResponse(
            service.export_markdown(),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=education_knowledge.md"},
        )
    if format == "sqlite":
        return FileResponse(
            str(service.export_sqlite()),
            media_type="application/octet-stream",
            filename="education_knowledge.sqlite",
        )
    return JSONResponse(
        content=service.export_json(),
        headers={"Content-Disposition": "attachment; filename=education_knowledge.json"},
    )
