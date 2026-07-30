from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.config.settings import settings
from app.database.session import Base

# New-pattern (schema-qualified) tables in this file use their own reserved
# schema, like catalog.py/question_bank.py -- AcquisitionJob/NcertBook/
# Notification below predate that convention and deliberately stay unqualified
# (see Project_Master_Document.md's Database Summary notes).
ACQUISITION_SCHEMA = None if settings.is_sqlite else "acquisition"

ACQUISITION_ITEM_STATUSES = {
    "discovered", "downloading", "downloaded", "parsed", "failed", "retry", "completed",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AcquisitionJob(Base):
    """Generic source-acquisition job (scan / download).

    Shared across acquisition sources (NCERT now; PDF/Images later) so the
    worker, progress and notification plumbing is reused. The YouTube extractor
    keeps its own ExtractionJob and is untouched.
    """

    __tablename__ = "acquisition_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(Unicode(40), default="ncert", index=True)
    job_type: Mapped[str] = mapped_column(Unicode(40), default="download")
    status: Mapped[str] = mapped_column(Unicode(30), default="queued", index=True)
    stage: Mapped[str] = mapped_column(Unicode(80), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(UnicodeText, default="")
    payload: Mapped[str] = mapped_column(UnicodeText, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class NcertBook(Base):
    __tablename__ = "ncert_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_code: Mapped[str] = mapped_column(Unicode(40), unique=True, index=True)
    class_level: Mapped[str] = mapped_column(Unicode(10), index=True)
    class_label: Mapped[str] = mapped_column(Unicode(40), default="")
    subject: Mapped[str] = mapped_column(Unicode(120), index=True)
    title: Mapped[str] = mapped_column(Unicode(300))
    part: Mapped[str] = mapped_column(Unicode(20), default="")
    language: Mapped[str] = mapped_column(Unicode(40), default="", index=True)
    url: Mapped[str] = mapped_column(Unicode(500))
    edition: Mapped[str] = mapped_column(Unicode(60), default="")
    cover_url: Mapped[str] = mapped_column(Unicode(500), default="")

    status: Mapped[str] = mapped_column(Unicode(30), default="available", index=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloaded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version_hash: Mapped[str] = mapped_column(Unicode(80), default="")
    checksum: Mapped[str] = mapped_column(Unicode(80), default="")
    file_path: Mapped[str] = mapped_column(Unicode(500), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AcquisitionItem(Base):
    """Generic, provider-agnostic acquisition queue item — the durable state
    machine behind the acquisition provider framework (Phase 2A):
    discovered -> downloading -> downloaded -> parsed -> completed, with
    failed/retry for error recovery. One row per (provider, source_id);
    re-running a provider's discover() is idempotent (see
    AcquisitionQueueService.enqueue_discovered).

    Distinct from `AcquisitionJob` (an orchestration run: "scan", "download
    all") and from `NcertBook` (NCERT's own item registry, kept as-is) — this
    is the generalized version every future provider shares.
    """

    __tablename__ = "acquisition_items"
    __table_args__ = (
        UniqueConstraint("provider", "source_id", name="uq_acquisition_item_provider_source"),
        {"schema": ACQUISITION_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("acquisition_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(Unicode(60), index=True)
    source_id: Mapped[str] = mapped_column(Unicode(300), index=True)
    source_url: Mapped[str] = mapped_column(Unicode(1000), default="")
    document_type: Mapped[str] = mapped_column(Unicode(20), default="")
    language: Mapped[str] = mapped_column(Unicode(20), default="")
    checksum: Mapped[str] = mapped_column(Unicode(64), default="")
    metadata_json: Mapped[str] = mapped_column(UnicodeText, default="")
    local_file: Mapped[str] = mapped_column(Unicode(600), default="")
    status: Mapped[str] = mapped_column(Unicode(20), default="discovered", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str] = mapped_column(UnicodeText, default="")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(Unicode(20), default="info")
    title: Mapped[str] = mapped_column(Unicode(160))
    message: Mapped[str] = mapped_column(UnicodeText, default="")
    source: Mapped[str] = mapped_column(Unicode(40), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
