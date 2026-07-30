import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Unicode, UnicodeText, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.settings import settings
from app.database.session import Base
from app.models.mixins import TenantAuditMixin

# Generic exam syllabus catalog: Exam -> Subject -> Unit -> Chapter -> Topic.
# Schema-qualified on SQL Server (catalog.exam, catalog.subject, ...); SQLite
# has no multi-schema support, so tables fall back to unqualified names there
# (dev-only default backend — see config/settings.py Settings.is_sqlite).
CATALOG_SCHEMA = None if settings.is_sqlite else "catalog"


def _fk(table: str) -> str:
    return f"{CATALOG_SCHEMA}.{table}.id" if CATALOG_SCHEMA else f"{table}.id"


class Exam(TenantAuditMixin, Base):
    """A single examination (NEET, JEE Main, UPSC, ...). Generic — no
    exam-specific logic lives here; the hierarchy underneath works for any exam."""

    __tablename__ = "exam"
    __table_args__ = (
        UniqueConstraint("code", name="uq_exam_code"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Unicode(40), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    description: Mapped[str] = mapped_column(UnicodeText, default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    subjects: Mapped[list["Subject"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="Subject.display_order"
    )


class Subject(TenantAuditMixin, Base):
    __tablename__ = "subject"
    __table_args__ = (
        UniqueConstraint("exam_id", "code", name="uq_subject_exam_code"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("exam"), ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Unicode(40), index=True)
    name: Mapped[str] = mapped_column(Unicode(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped["Exam"] = relationship(back_populates="subjects")
    units: Mapped[list["Unit"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Unit.display_order"
    )


class Unit(TenantAuditMixin, Base):
    __tablename__ = "unit"
    __table_args__ = (
        UniqueConstraint("subject_id", "code", name="uq_unit_subject_code"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("subject"), ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Unicode(40), index=True)
    name: Mapped[str] = mapped_column(Unicode(300))
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped["Subject"] = relationship(back_populates="units")
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan", order_by="Chapter.display_order"
    )


class Chapter(TenantAuditMixin, Base):
    __tablename__ = "chapter"
    __table_args__ = (
        UniqueConstraint("unit_id", "code", name="uq_chapter_unit_code"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("unit"), ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Unicode(40), index=True)
    name: Mapped[str] = mapped_column(Unicode(300))
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    unit: Mapped["Unit"] = relationship(back_populates="chapters")
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", order_by="Topic.display_order"
    )


class Topic(TenantAuditMixin, Base):
    __tablename__ = "topic"
    __table_args__ = (
        UniqueConstraint("chapter_id", "code", name="uq_topic_chapter_code"),
        {"schema": CATALOG_SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("chapter"), ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Unicode(40), index=True)
    name: Mapped[str] = mapped_column(Unicode(400))
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    chapter: Mapped["Chapter"] = relationship(back_populates="topics")
