from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """Generic processed-document registry, reusable by every document source
    (NCERT PDFs, uploads, future PDF/Image sources)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(Unicode(40), default="upload", index=True)
    source_ref: Mapped[str] = mapped_column(Unicode(120), default="")
    title: Mapped[str] = mapped_column(Unicode(400))
    file_path: Mapped[str] = mapped_column(Unicode(600))
    file_type: Mapped[str] = mapped_column(Unicode(20), default="pdf")
    checksum: Mapped[str] = mapped_column(Unicode(80), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(Unicode(30), default="pending", index=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    elements: Mapped[list["DocumentElement"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentElement.order_index"
    )
    bookmarks: Mapped[list["DocumentBookmark"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentBookmark.order_index"
    )


class DocumentElement(Base):
    """One structural element: heading | paragraph | table | figure.
    Generic across sources; type-specific data lives in `extra` (JSON)."""

    __tablename__ = "document_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer, default=1, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    element_type: Mapped[str] = mapped_column(Unicode(20), index=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(UnicodeText, default="")
    bbox: Mapped[str] = mapped_column(UnicodeText, default="")
    extra: Mapped[str] = mapped_column(UnicodeText, default="")

    document: Mapped[Document] = relationship(back_populates="elements")


class DocumentBookmark(Base):
    __tablename__ = "document_bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(Unicode(500))
    page: Mapped[int] = mapped_column(Integer, default=1)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship(back_populates="bookmarks")
