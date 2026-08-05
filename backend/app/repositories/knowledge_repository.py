from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge import KnowledgeNode


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def clear_for_document(self, document_id: int) -> None:
        self.db.query(KnowledgeNode).filter(KnowledgeNode.document_id == document_id).delete()
        self.db.commit()

    def add(self, node: KnowledgeNode) -> KnowledgeNode:
        self.db.add(node)
        self.db.flush()
        return node

    def commit(self) -> None:
        self.db.commit()

    def get(self, node_id: int) -> KnowledgeNode | None:
        return self.db.get(KnowledgeNode, node_id)

    def get_many(self, ids: list[int]) -> list[KnowledgeNode]:
        if not ids:
            return []
        return list(self.db.scalars(select(KnowledgeNode).where(KnowledgeNode.id.in_(ids))))

    def for_document(self, document_id: int) -> list[KnowledgeNode]:
        return list(
            self.db.scalars(
                select(KnowledgeNode)
                .where(KnowledgeNode.document_id == document_id)
                .order_by(KnowledgeNode.order_index)
            )
        )

    def children(self, document_id: int, parent_id: int | None) -> list[KnowledgeNode]:
        stmt = select(KnowledgeNode).where(KnowledgeNode.document_id == document_id)
        stmt = stmt.where(KnowledgeNode.parent_id.is_(None) if parent_id is None else KnowledgeNode.parent_id == parent_id)
        return list(self.db.scalars(stmt.order_by(KnowledgeNode.order_index)))

    def count_for_document(self, document_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(KnowledgeNode).where(KnowledgeNode.document_id == document_id)
            )
            or 0
        )

    def child_counts(self, document_id: int) -> dict[int, int]:
        rows = self.db.execute(
            select(KnowledgeNode.parent_id, func.count())
            .where(KnowledgeNode.document_id == document_id, KnowledgeNode.parent_id.is_not(None))
            .group_by(KnowledgeNode.parent_id)
        ).all()
        return {parent_id: count for parent_id, count in rows}

    def search(
        self, query: str, document_id: int | None = None, limit: int = 50
    ) -> list[KnowledgeNode]:
        like = f"%{query.lower()}%"
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.node_type != "root",
            func.lower(KnowledgeNode.title).like(like) | func.lower(KnowledgeNode.content).like(like),
        )
        if document_id is not None:
            stmt = stmt.where(KnowledgeNode.document_id == document_id)
        return list(self.db.scalars(stmt.order_by(KnowledgeNode.document_id, KnowledgeNode.order_index).limit(limit)))

    def mapped_documents(self) -> list[tuple[Document, int]]:
        node_counts = (
            select(
                KnowledgeNode.document_id.label("document_id"),
                func.count(KnowledgeNode.id).label("node_count"),
            )
            .group_by(KnowledgeNode.document_id)
            .subquery()
        )
        rows = self.db.execute(
            select(Document, node_counts.c.node_count)
            .join(node_counts, node_counts.c.document_id == Document.id)
            .order_by(Document.id.desc())
        ).all()
        return [(doc, count) for doc, count in rows]

    def stats(self) -> dict:
        rows = self.db.execute(
            select(KnowledgeNode.node_type, func.count()).group_by(KnowledgeNode.node_type)
        ).all()
        by_type = {node_type: count for node_type, count in rows}
        mapped_docs = self.db.scalar(
            select(func.count(func.distinct(KnowledgeNode.document_id)))
        ) or 0
        return {
            "mapped_documents": int(mapped_docs),
            "nodes": sum(by_type.values()),
            "sections": by_type.get("section", 0),
            "paragraphs": by_type.get("paragraph", 0),
            "tables": by_type.get("table", 0),
            "figures": by_type.get("figure", 0),
        }
