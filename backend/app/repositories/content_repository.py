from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.content import ContentBlock, ContentSection


class ContentRepository:
    def __init__(self, db: Session):
        self.db = db

    def clear_for_document(self, document_id: int) -> None:
        # Blocks reference sections (no cascade), so delete blocks first.
        self.db.query(ContentBlock).filter(ContentBlock.document_id == document_id).delete()
        self.db.query(ContentSection).filter(ContentSection.document_id == document_id).delete()
        self.db.commit()

    def add_section(self, section: ContentSection) -> ContentSection:
        self.db.add(section)
        self.db.flush()
        return section

    def add_blocks(self, blocks: list[ContentBlock]) -> None:
        self.db.add_all(blocks)

    def commit(self) -> None:
        self.db.commit()

    def sections_for_document(self, document_id: int) -> list[ContentSection]:
        return list(
            self.db.scalars(
                select(ContentSection)
                .where(ContentSection.document_id == document_id)
                .order_by(ContentSection.order_index)
            )
        )

    def blocks_for_document(self, document_id: int) -> list[ContentBlock]:
        return list(
            self.db.scalars(
                select(ContentBlock)
                .where(ContentBlock.document_id == document_id)
                .order_by(ContentBlock.order_index)
            )
        )

    def block_count(self, document_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(ContentBlock).where(ContentBlock.document_id == document_id)
            )
            or 0
        )

    def stats(self) -> dict:
        rows = self.db.execute(
            select(ContentBlock.block_type, func.count()).group_by(ContentBlock.block_type)
        ).all()
        by_type = {block_type: count for block_type, count in rows}
        assembled_docs = self.db.scalar(
            select(func.count(func.distinct(ContentBlock.document_id)))
        ) or 0
        sections = self.db.scalar(select(func.count()).select_from(ContentSection)) or 0
        return {
            "assembled_documents": int(assembled_docs),
            "sections": int(sections),
            "blocks": sum(by_type.values()),
            "paragraphs": by_type.get("paragraph", 0),
            "figures": by_type.get("figure", 0),
            "tables": by_type.get("table", 0),
            "examples": by_type.get("example", 0),
            "exercises": by_type.get("exercise", 0),
        }
