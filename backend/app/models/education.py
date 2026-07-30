from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.config.settings import settings
from app.database.session import Base

EDUCATION_SCHEMA = None if settings.is_sqlite else "education"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EducationSource(Base):
    __tablename__ = "education_sources"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_education_source_key"),
        {"schema": EDUCATION_SCHEMA},
    )

    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True, default=lambda: str(uuid4()))
    source_key: Mapped[str] = mapped_column(Unicode(180), index=True)
    institution_name: Mapped[str] = mapped_column(Unicode(300), default="", index=True)
    institution_type: Mapped[str] = mapped_column(Unicode(60), default="", index=True)
    board: Mapped[str] = mapped_column(Unicode(120), default="", index=True)
    state: Mapped[str] = mapped_column(Unicode(120), default="", index=True)
    district: Mapped[str] = mapped_column(Unicode(120), default="", index=True)
    website_url: Mapped[str] = mapped_column(Unicode(1000), default="")
    source_kind: Mapped[str] = mapped_column(Unicode(40), default="website", index=True)
    is_government: Mapped[str] = mapped_column(Unicode(5), default="false")
    metadata_json: Mapped[str] = mapped_column(UnicodeText, default="")
    last_discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class EducationDocument(Base):
    __tablename__ = "education_documents"
    __table_args__ = (
        UniqueConstraint("url", name="uq_education_document_url"),
        {"schema": EDUCATION_SCHEMA},
    )

    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{EDUCATION_SCHEMA + '.' if EDUCATION_SCHEMA else ''}education_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    acquisition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{'acquisition.' if not settings.is_sqlite else ''}acquisition_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    url: Mapped[str] = mapped_column(Unicode(1000), default="")
    title: Mapped[str] = mapped_column(Unicode(500), default="")
    document_type: Mapped[str] = mapped_column(Unicode(60), default="", index=True)
    classification: Mapped[str] = mapped_column(Unicode(80), default="", index=True)
    file_type: Mapped[str] = mapped_column(Unicode(30), default="", index=True)
    checksum: Mapped[str] = mapped_column(Unicode(64), default="")
    local_file: Mapped[str] = mapped_column(Unicode(600), default="")
    language: Mapped[str] = mapped_column(Unicode(20), default="")
    summary: Mapped[str] = mapped_column(UnicodeText, default="")
    metadata_json: Mapped[str] = mapped_column(UnicodeText, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, index=True)


class EducationField(Base):
    __tablename__ = "education_fields"
    __table_args__ = ({"schema": EDUCATION_SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey(f"{EDUCATION_SCHEMA + '.' if EDUCATION_SCHEMA else ''}education_documents.id", ondelete="CASCADE"),
        index=True,
    )
    canonical_key: Mapped[str] = mapped_column(Unicode(120), index=True)
    label: Mapped[str] = mapped_column(Unicode(240), default="")
    value: Mapped[str] = mapped_column(UnicodeText, default="")
    value_type: Mapped[str] = mapped_column(Unicode(40), default="text")
    source_kind: Mapped[str] = mapped_column(Unicode(40), default="metadata")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EducationTag(Base):
    __tablename__ = "education_tags"
    __table_args__ = (
        UniqueConstraint("document_id", "tag", name="uq_education_tag_document_tag"),
        {"schema": EDUCATION_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey(f"{EDUCATION_SCHEMA + '.' if EDUCATION_SCHEMA else ''}education_documents.id", ondelete="CASCADE"),
        index=True,
    )
    tag: Mapped[str] = mapped_column(Unicode(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
