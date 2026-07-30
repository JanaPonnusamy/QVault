from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeNode(Base):
    """Generic hierarchical knowledge node.

    A document's extracted structure (headings, paragraphs, tables, figures,
    bookmarks) is mapped into a tree of these nodes with parent-child links.
    Generic by design so any future source can feed the same hierarchy.
    """

    __tablename__ = "knowledge_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # No ON DELETE CASCADE on this self-referential FK: SQL Server forbids the
    # resulting multiple cascade paths (document_id already cascades). Nodes are
    # always removed in bulk by document_id (KnowledgeRepository.clear_for_document).
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_nodes.id"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(Unicode(20), index=True)  # root|section|paragraph|table|figure
    title: Mapped[str] = mapped_column(Unicode(500), default="")
    content: Mapped[str] = mapped_column(UnicodeText, default="")
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    page: Mapped[int] = mapped_column(Integer, default=0)
    element_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    path: Mapped[str] = mapped_column(Unicode(500), default="")
    extra: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
