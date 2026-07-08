from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContentSection(Base):
    """Assembled, reader-friendly section (cleaned heading hierarchy).

    Produced by the Content Assembly Engine from raw `document_elements`. The raw
    extraction is never modified — this is a derived, regenerable representation.
    """

    __tablename__ = "content_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # Self-referential FK without cascade (SQL Server multiple-cascade-path rule);
    # sections are cleared in bulk by document_id on reassembly/delete.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_sections.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    page_start: Mapped[int] = mapped_column(Integer, default=0)
    page_end: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ContentBlock(Base):
    """A single assembled, readable content unit within a section.

    block_type: heading | paragraph | figure | table | example | exercise.
    `source_element_ids` (JSON) preserves provenance back to `document_elements`.
    """

    __tablename__ = "content_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_sections.id"), nullable=True, index=True
    )
    block_type: Mapped[str] = mapped_column(String(20), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    page: Mapped[int] = mapped_column(Integer, default=0)
    source_element_ids: Mapped[str] = mapped_column(Text, default="")
    extra: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
