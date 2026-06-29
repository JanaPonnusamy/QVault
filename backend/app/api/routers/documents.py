from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AcquisitionJobOut,
    DocumentDetail,
    DocumentElementOut,
    DocumentList,
    DocumentOut,
    DocumentStats,
    DownloadedBookOut,
    ImportNcertRequest,
)
from app.models.rbac import User
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ncert_repository import NcertRepository
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/documents", tags=["documents"])

MODULE = "documents"


@router.get("/stats", response_model=DocumentStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return DocumentStats(**DocumentRepository(db).stats())


@router.get("", response_model=DocumentList)
def list_documents(
    search: str | None = None,
    source: str | None = None,
    status: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = DocumentRepository(db).query(
        search=search, source=source, status=status, limit=limit, offset=offset
    )
    return DocumentList(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs", response_model=list[AcquisitionJobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return AcquisitionJobRepository(db).list("document")


@router.get("/ncert-books", response_model=list[DownloadedBookOut])
def downloaded_ncert_books(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return NcertRepository(db).downloaded_books()


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
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
    return KnowledgeService(db).register_upload(file.filename or "document.pdf", data, user.id)


@router.post("/import/ncert", response_model=list[DocumentOut])
def import_ncert(
    payload: ImportNcertRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    documents = KnowledgeService(db).import_from_ncert(payload.book_id, user.id)
    if not documents:
        raise HTTPException(status_code=400, detail="Book not found or not downloaded")
    return documents


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    document = DocumentRepository(db).get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetail.model_validate(document)


@router.get("/{document_id}/elements", response_model=list[DocumentElementOut])
def get_elements(
    document_id: int,
    page: int | None = None,
    element_type: str | None = None,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = DocumentRepository(db)
    if not repo.get(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return repo.elements(document_id, page=page, element_type=element_type)


@router.post("/{document_id}/reprocess", response_model=DocumentOut)
def reprocess(
    document_id: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    document = KnowledgeService(db).reprocess(document_id, user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    service = KnowledgeService(db)
    document = service.docs.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    service.delete(document)
    return {"status": "deleted"}
