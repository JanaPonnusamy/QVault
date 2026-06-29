from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AcquisitionJobOut,
    DownloadRequest,
    NcertBookList,
    NcertFacets,
    NcertStats,
)
from app.models.acquisition import NcertBook
from app.models.rbac import User
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.ncert_repository import NcertRepository
from app.services.ncert_service import NcertService

router = APIRouter(prefix="/api/sources/ncert", tags=["ncert"])

MODULE = "ncert"


@router.get("/stats", response_model=NcertStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return NcertStats(**NcertRepository(db).stats())


@router.get("/facets", response_model=NcertFacets)
def facets(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    repo = NcertRepository(db)
    return NcertFacets(
        classes=repo.distinct(NcertBook.class_level),
        subjects=repo.distinct(NcertBook.subject),
        languages=repo.distinct(NcertBook.language),
        statuses=repo.distinct(NcertBook.status),
    )


@router.get("/books", response_model=NcertBookList)
def list_books(
    search: str | None = None,
    class_level: str | None = None,
    subject: str | None = None,
    language: str | None = None,
    status: str | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    items, total = NcertRepository(db).query(
        search=search,
        class_level=class_level,
        subject=subject,
        language=language,
        status=status,
        limit=limit,
        offset=offset,
    )
    return NcertBookList(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs", response_model=list[AcquisitionJobOut])
def list_jobs(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return AcquisitionJobRepository(db).list("ncert")


@router.post("/scan", response_model=AcquisitionJobOut)
def scan(
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    return NcertService(db).start_scan(user.id)


@router.post("/refresh", response_model=AcquisitionJobOut)
def refresh(
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    return NcertService(db).start_refresh(user.id)


@router.post("/download", response_model=AcquisitionJobOut)
def download_selected(
    payload: DownloadRequest,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    job = NcertService(db).queue_downloads(payload.book_ids, user.id)
    if not job:
        raise HTTPException(status_code=400, detail="No downloadable books selected (already downloaded or invalid)")
    return job


@router.post("/download-all", response_model=AcquisitionJobOut)
def download_all(
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    job = NcertService(db).download_all(user.id)
    if not job:
        raise HTTPException(status_code=400, detail="Nothing to download — all books are already downloaded")
    return job


@router.post("/books/{book_id}/retry", response_model=AcquisitionJobOut)
def retry(
    book_id: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_permission(f"{MODULE}:execute")),
):
    job = NcertService(db).retry(book_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Book not found")
    return job


@router.delete("/books/{book_id}/download")
def delete_download(
    book_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:delete")),
):
    service = NcertService(db)
    book = service.books.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    service.delete_download(book)
    return {"status": "deleted"}
