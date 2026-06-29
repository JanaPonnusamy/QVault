from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    KnowledgeNodeDetail,
    KnowledgeSearchResult,
    KnowledgeStats,
    KnowledgeTreeNode,
    MappedDocumentOut,
)
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.knowledge_map_service import KnowledgeMapService
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

MODULE = "knowledge"


@router.get("/stats", response_model=KnowledgeStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return KnowledgeStats(**KnowledgeRepository(db).stats())


@router.get("/documents", response_model=list[MappedDocumentOut])
def mapped_documents(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return [
        MappedDocumentOut(
            id=doc.id, title=doc.title, source=doc.source, status=doc.status,
            page_count=doc.page_count, node_count=count,
        )
        for doc, count in KnowledgeRepository(db).mapped_documents()
    ]


@router.get("/documents/{document_id}/tree", response_model=KnowledgeTreeNode)
def document_tree(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    tree = KnowledgeMapService(db).tree(document_id)
    if not tree:
        raise HTTPException(status_code=404, detail="No knowledge map for this document")
    return tree


@router.get("/nodes/{node_id}", response_model=KnowledgeNodeDetail)
def node_detail(
    node_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    service = KnowledgeMapService(db)
    node = service.repo.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return service.node_detail(node)


@router.get("/search", response_model=list[KnowledgeSearchResult])
def search(
    q: str = Query(..., min_length=1),
    document_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return KnowledgeMapService(db).search(q, document_id=document_id, limit=limit)


@router.post("/documents/{document_id}/remap", response_model=KnowledgeStats)
def remap(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    service = KnowledgeService(db)
    document = service.docs.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "processed":
        raise HTTPException(status_code=400, detail="Document must be processed before mapping")
    KnowledgeMapService(db).map_document(document)
    return KnowledgeStats(**KnowledgeRepository(db).stats())
