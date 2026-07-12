import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.config.settings import settings
from app.database.session import Base
from app.models.mixins import TenantAuditMixin, _now

SYSTEM_SCHEMA = None if settings.is_sqlite else "system"


class SyllabusImportLog(TenantAuditMixin, Base):
    """Status/error log for one run of the reusable syllabus PDF importer.

    Not tied to any single exam type — the importer (services/syllabus_import_service.py)
    writes one row per import attempt regardless of which exam's syllabus is being loaded.
    """

    __tablename__ = "syllabus_import_log"
    __table_args__ = {"schema": SYSTEM_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_code: Mapped[str] = mapped_column(String(40), index=True)
    source_file: Mapped[str] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)  # running|success|failed
    subjects_count: Mapped[int] = mapped_column(Integer, default=0)
    units_count: Mapped[int] = mapped_column(Integer, default=0)
    chapters_count: Mapped[int] = mapped_column(Integer, default=0)
    topics_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
