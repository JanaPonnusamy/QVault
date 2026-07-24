import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.config.settings import settings
from app.database.session import Base
from app.models.mixins import DEFAULT_TENANT_ID, TenantAuditMixin, _now

SYSTEM_SCHEMA = None if settings.is_sqlite else "system"


class DatabaseVersion(Base):
    """Migration execution ledger. One row per migration attempt (not per
    startup) — the migration runner treats a migration as applied only once a
    row with status="success" exists for its name, so a prior failure is
    retried on the next startup rather than silently skipped."""

    __tablename__ = "database_version"
    __table_args__ = {"schema": SYSTEM_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    migration_name: Mapped[str] = mapped_column(String(200), index=True)
    applied_on: Mapped[datetime] = mapped_column(DateTime, default=_now)
    execution_time: Mapped[int] = mapped_column(Integer, default=0)  # milliseconds
    status: Mapped[str] = mapped_column(String(20), default="success")  # success|failed
    error: Mapped[str] = mapped_column(Text, default="")


class Tenant(Base):
    """Tenant registry for future SaaS deployment. QVault runs single-tenant
    today (see mixins.DEFAULT_TENANT_ID); this table just makes that tenant
    a real row instead of a bare constant, so multi-tenancy is additive later."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": SYSTEM_SCHEMA}

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    tenant_name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_on: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ApplicationSetting(Base):
    """Generic key/value application settings, distinct from `.env`
    (deploy-time config) — for runtime-editable settings future modules add."""

    __tablename__ = "application_settings"
    __table_args__ = {"schema": SYSTEM_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    updated_on: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AuditLog(Base):
    """Generic audit trail. Not wired to any module yet — future services call
    into it via a shared repository once the first module needs auditing."""

    __tablename__ = "audit_log"
    __table_args__ = {"schema": SYSTEM_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=lambda: DEFAULT_TENANT_ID, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), default="")
    entity_id: Mapped[str] = mapped_column(String(100), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_on: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


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
