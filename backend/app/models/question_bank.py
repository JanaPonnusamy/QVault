import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.settings import settings
from app.database.session import Base
from app.models.catalog import CATALOG_SCHEMA
from app.models.mixins import TenantAuditMixin, _now

# Question Acquisition & Extraction Engine, Phase 1: the question repository.
# Lives in its own reserved schema (see database/mssql_bootstrap.py
# RESERVED_SCHEMAS), separate from `catalog` (the syllabus hierarchy) and from
# `questions`/`extraction_jobs` (models/extraction.py — frame-derived questions
# scoped to a single video job; a different concept, not duplicated here).
QUESTION_SCHEMA = None if settings.is_sqlite else "question"


def _fk(table: str) -> str:
    return f"{QUESTION_SCHEMA}.{table}.id" if QUESTION_SCHEMA else f"{table}.id"


def _catalog_fk(table: str) -> str:
    return f"{CATALOG_SCHEMA}.{table}.id" if CATALOG_SCHEMA else f"{table}.id"


class BankSource(TenantAuditMixin, Base):
    """One acquired source document (a PDF, a web page, a video...).

    Never overwritten on re-crawl: first_seen/last_seen/crawl_count carry
    acquisition history, and `checksum` detects when the same URL's content
    has actually changed since the last visit.
    """

    __tablename__ = "bank_sources"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(Unicode(60), default="manual", index=True)
    website: Mapped[str] = mapped_column(Unicode(200), default="")
    url: Mapped[str] = mapped_column(Unicode(1000), default="", index=True)
    exam: Mapped[str] = mapped_column(Unicode(60), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shift: Mapped[str] = mapped_column(Unicode(20), default="")
    language: Mapped[str] = mapped_column(Unicode(20), default="")
    license: Mapped[str] = mapped_column(Unicode(60), default="")
    checksum: Mapped[str] = mapped_column(Unicode(64), default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=_now)
    crawl_count: Mapped[int] = mapped_column(Integer, default=1)
    last_status: Mapped[str] = mapped_column(Unicode(20), default="ok")

    questions: Mapped[list["BankQuestion"]] = relationship(back_populates="source")


class BankQuestion(TenantAuditMixin, Base):
    """Topic-wise exam question repository.

    Topic mapping is many-to-many via `BankQuestionTopic` (a question commonly
    belongs to more than one topic) — never a single topic_id column. Solutions
    are one-to-many via `BankQuestionSolution` (official/coaching/ai_generated/
    community solutions coexist). Distinct from `Question`
    (models/extraction.py), which stores frame-derived questions scoped to a
    single video extraction job.
    """

    __tablename__ = "bank_questions"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # `exam` is a free-text fallback (always set); `exam_id` links to the
    # Syllabus Catalog's canonical Exam registry once/if it's known there —
    # optional so acquisition never blocks on the catalog having caught up.
    exam: Mapped[str] = mapped_column(Unicode(60), default="", index=True)
    exam_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_catalog_fk("exam")), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    session: Mapped[str] = mapped_column(Unicode(40), default="")
    shift: Mapped[str] = mapped_column(Unicode(20), default="")

    difficulty: Mapped[str] = mapped_column(Unicode(20), default="", index=True)
    question_type: Mapped[str] = mapped_column(Unicode(30), default="mcq", index=True)
    question_text: Mapped[str] = mapped_column(UnicodeText, default="")
    # Search-index groundwork: precomputed now (it's free — already needed for
    # the dedup hash), keywords populated once a Phase-2+ extractor exists.
    normalized_text: Mapped[str] = mapped_column(UnicodeText, default="")
    keywords: Mapped[str] = mapped_column(UnicodeText, default="")  # JSON array, not yet populated
    language: Mapped[str] = mapped_column(Unicode(20), default="en")

    # NAT/numerical/free-text answers. MCQ/MSQ correctness lives on options.
    correct_answer_text: Mapped[str] = mapped_column(UnicodeText, default="")
    # Structured answers for match-the-following / matrix-match (JSON).
    answer_data: Mapped[str] = mapped_column(UnicodeText, default="")

    image_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    image_path: Mapped[str] = mapped_column(Unicode(600), default="")

    status: Mapped[str] = mapped_column(Unicode(20), default="draft", index=True)
    # Mirrors the latest BankQuestionLineage row for quick filtering without a
    # join (e.g. acquired -> ocr -> parsed -> human_corrected -> published).
    current_stage: Mapped[str] = mapped_column(Unicode(40), default="draft_entry", index=True)
    review_reason: Mapped[str] = mapped_column(Unicode(40), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_score: Mapped[float] = mapped_column(Float, default=0.0)
    question_hash: Mapped[str] = mapped_column(Unicode(64), default="", index=True)

    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_fk("bank_sources")), nullable=True, index=True)

    source: Mapped["BankSource | None"] = relationship(back_populates="questions")
    topics: Mapped[list["BankQuestionTopic"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionTopic.id"
    )
    options: Mapped[list["BankQuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionOption.order_index"
    )
    solutions: Mapped[list["BankQuestionSolution"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionSolution.id"
    )
    images: Mapped[list["BankQuestionImage"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionImage.id"
    )
    lineage: Mapped[list["BankQuestionLineage"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionLineage.id"
    )


class BankQuestionTopic(Base):
    """Many-to-many topic mapping (a question commonly belongs to more than one
    topic — this replaces a single topic_id column). Each row can be as coarse
    as subject-level or as fine as topic-level, depending on how precisely the
    (deterministic-first) topic matcher could place it; at most one row per
    question should be `is_primary`.
    """

    __tablename__ = "bank_question_topics"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("bank_questions"), ondelete="CASCADE"), index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_catalog_fk("subject")), nullable=True, index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_catalog_fk("unit")), nullable=True, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_catalog_fk("chapter")), nullable=True, index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_catalog_fk("topic")), nullable=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question: Mapped[BankQuestion] = relationship(back_populates="topics")


class BankQuestionOption(Base):
    __tablename__ = "bank_question_options"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("bank_questions"), ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(Unicode(10), default="")
    text: Mapped[str] = mapped_column(UnicodeText, default="")
    image_path: Mapped[str] = mapped_column(Unicode(600), default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[BankQuestion] = relationship(back_populates="options")


class BankQuestionSolution(Base):
    """Solutions are additive, never overwritten — official/coaching/
    ai_generated/community/video solutions for the same question coexist as
    separate rows, distinguished by `source_type`."""

    __tablename__ = "bank_question_solutions"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("bank_questions"), ondelete="CASCADE"), index=True)
    solution_text: Mapped[str] = mapped_column(UnicodeText, default="")
    explanation: Mapped[str] = mapped_column(UnicodeText, default="")
    source_type: Mapped[str] = mapped_column(Unicode(30), default="manual")
    source_url: Mapped[str] = mapped_column(Unicode(1000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question: Mapped[BankQuestion] = relationship(back_populates="solutions")


class BankQuestionImage(Base):
    __tablename__ = "bank_question_images"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("bank_questions"), ondelete="CASCADE"), index=True)
    image_path: Mapped[str] = mapped_column(Unicode(600), default="")
    image_type: Mapped[str] = mapped_column(Unicode(20), default="question")
    caption: Mapped[str] = mapped_column(Unicode(300), default="")
    sha256_hash: Mapped[str] = mapped_column(Unicode(64), default="", index=True)
    # Perceptual hash for near-duplicate figures/diagrams; populated once a
    # media downloader exists (Phase 2+) — column is ready ahead of that.
    phash: Mapped[str] = mapped_column(Unicode(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question: Mapped[BankQuestion] = relationship(back_populates="images")


class BankQuestionLineage(Base):
    """Append-only processing history for a question: acquired -> ocr ->
    parsed -> human_corrected -> published (stage names are pipeline-defined,
    not enum-locked). `BankQuestion.current_stage` mirrors the latest row here
    for quick filtering without a join."""

    __tablename__ = "bank_question_lineage"
    __table_args__ = {"schema": QUESTION_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_fk("bank_questions"), ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(Unicode(40), index=True)
    detail: Mapped[str] = mapped_column(UnicodeText, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    question: Mapped[BankQuestion] = relationship(back_populates="lineage")
