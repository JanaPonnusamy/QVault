from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import (
    AssembledDocumentOut,
    AssembleSummary,
    ContentBlockOut,
    ContentSectionOut,
    ContentStats,
)
from app.repositories.content_repository import ContentRepository
from app.services.content_assembly_service import ContentAssemblyService
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/content", tags=["content"])

MODULE = "content"


@router.get("/stats", response_model=ContentStats)
def stats(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    return ContentStats(**ContentRepository(db).stats())


@router.get("/documents/{document_id}", response_model=AssembledDocumentOut)
def assembled_document(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:view")),
):
    service = KnowledgeService(db)
    document = service.docs.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    repo = ContentRepository(db)
    sections = repo.sections_for_document(document_id)
    blocks = repo.blocks_for_document(document_id)
    by_section: dict[int | None, list] = {}
    for block in blocks:
        by_section.setdefault(block.section_id, []).append(block)

    section_payload = []
    for section in sections:
        out = ContentSectionOut.model_validate(section)
        out.blocks = [ContentBlockOut.model_validate(b) for b in by_section.get(section.id, [])]
        section_payload.append(out)

    return AssembledDocumentOut(
        document_id=document.id,
        title=document.title,
        section_count=len(sections),
        block_count=len(blocks),
        sections=section_payload,
    )


@router.post("/documents/{document_id}/assemble", response_model=AssembleSummary)
def assemble(
    document_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission(f"{MODULE}:execute")),
):
    service = KnowledgeService(db)
    document = service.docs.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "processed":
        raise HTTPException(status_code=400, detail="Document must be processed before assembly")
    return AssembleSummary(**ContentAssemblyService(db).assemble(document))
