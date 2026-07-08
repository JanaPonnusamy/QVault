from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentBookmark, DocumentElement


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, document_id: int) -> Document | None:
        return self.db.get(Document, document_id)

    def add(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def save(self) -> None:
        self.db.commit()

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()

    def query(
        self,
        search: str | None = None,
        source: str | None = None,
        status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        stmt = select(Document)
        if search:
            stmt = stmt.where(func.lower(Document.title).like(f"%{search.lower()}%"))
        if source:
            stmt = stmt.where(Document.source == source)
        if status:
            stmt = stmt.where(Document.status == status)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(Document.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)

    def clear_structure(self, document_id: int) -> None:
        self.db.query(DocumentElement).filter(DocumentElement.document_id == document_id).delete()
        self.db.query(DocumentBookmark).filter(DocumentBookmark.document_id == document_id).delete()
        self.db.commit()

    def add_elements(self, elements: list[DocumentElement]) -> None:
        self.db.add_all(elements)
        self.db.commit()

    def elements(
        self, document_id: int, page: int | None = None, element_type: str | None = None
    ) -> list[DocumentElement]:
        stmt = select(DocumentElement).where(DocumentElement.document_id == document_id)
        if page is not None:
            stmt = stmt.where(DocumentElement.page == page)
        if element_type:
            stmt = stmt.where(DocumentElement.element_type == element_type)
        return list(self.db.scalars(stmt.order_by(DocumentElement.order_index)))

    def bookmarks(self, document_id: int) -> list[DocumentBookmark]:
        return list(
            self.db.scalars(
                select(DocumentBookmark)
                .where(DocumentBookmark.document_id == document_id)
                .order_by(DocumentBookmark.order_index)
            )
        )

    def stats(self) -> dict:
        rows = self.db.execute(
            select(Document.status, func.count()).group_by(Document.status)
        ).all()
        by_status = {status: count for status, count in rows}
        total = sum(by_status.values())
        needs_ocr = self.db.scalar(
            select(func.count()).select_from(Document).where(Document.needs_ocr == True)  # noqa: E712
        ) or 0
        elements = self.db.scalar(select(func.count()).select_from(DocumentElement)) or 0
        return {
            "total": total,
            "processed": by_status.get("processed", 0),
            "pending": by_status.get("pending", 0) + by_status.get("processing", 0),
            "failed": by_status.get("failed", 0),
            "needs_ocr": int(needs_ocr),
            "elements": int(elements),
        }
