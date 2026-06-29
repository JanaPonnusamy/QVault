from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


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
    source: Mapped[str] = mapped_column(String(40), default="ncert", index=True)
    job_type: Mapped[str] = mapped_column(String(40), default="download")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(80), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class NcertBook(Base):
    __tablename__ = "ncert_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    class_level: Mapped[str] = mapped_column(String(10), index=True)
    class_label: Mapped[str] = mapped_column(String(40), default="")
    subject: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(300))
    part: Mapped[str] = mapped_column(String(20), default="")
    language: Mapped[str] = mapped_column(String(40), default="", index=True)
    url: Mapped[str] = mapped_column(String(500))
    edition: Mapped[str] = mapped_column(String(60), default="")
    cover_url: Mapped[str] = mapped_column(String(500), default="")

    status: Mapped[str] = mapped_column(String(30), default="available", index=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloaded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version_hash: Mapped[str] = mapped_column(String(80), default="")
    checksum: Mapped[str] = mapped_column(String(80), default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
