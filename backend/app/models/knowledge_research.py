from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column

from app.config.settings import settings
from app.database.session import Base

KNOWLEDGE_SCHEMA = None if settings.is_sqlite else "knowledge"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeSession(Base):
    __tablename__ = "knowledge_sessions"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(Unicode(20))
    input_value: Mapped[str] = mapped_column(UnicodeText)
    source_count_requested: Mapped[int] = mapped_column(Integer, default=1)
    source_type: Mapped[str] = mapped_column(Unicode(50), default="youtube")
    ai_provider: Mapped[str] = mapped_column(Unicode(50), default="")
    ai_model: Mapped[str] = mapped_column(Unicode(200), default="")
    status: Mapped[str] = mapped_column(Unicode(20), default="QUEUED", index=True)
    current_stage: Mapped[str] = mapped_column(Unicode(30), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    storage_directory: Mapped[str] = mapped_column(Unicode(1000), default="")
    pipeline_version: Mapped[str] = mapped_column(Unicode(50), default="")
    report_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    report_markdown_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    error_message: Mapped[str] = mapped_column(UnicodeText, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_sessions.id"), index=True)
    document_type: Mapped[str] = mapped_column(Unicode(50))
    source_reference: Mapped[str] = mapped_column(UnicodeText, default="")
    title: Mapped[str] = mapped_column(Unicode(500), default="")
    url: Mapped[str] = mapped_column(Unicode(1000), default="")
    language: Mapped[str] = mapped_column(Unicode(50), default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(Unicode(128), default="")
    processing_version: Mapped[str] = mapped_column(Unicode(50), default="")
    transcript_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    subtitle_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    ocr_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    merged_text_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    summary_path: Mapped[str] = mapped_column(Unicode(1000), default="")
    status: Mapped[str] = mapped_column(Unicode(20), default="QUEUED", index=True)
    error_message: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class KnowledgeFact(Base):
    __tablename__ = "knowledge_facts"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_sessions.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_documents.id"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(Unicode(100), default="")
    subcategory: Mapped[str] = mapped_column(Unicode(100), default="")
    value: Mapped[str] = mapped_column(UnicodeText, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(UnicodeText, default="")
    stage: Mapped[str] = mapped_column(Unicode(50), default="")
    source_document: Mapped[str] = mapped_column(Unicode(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_sessions.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_documents.id"),
        nullable=True,
        index=True,
    )
    entity_name: Mapped[str] = mapped_column(Unicode(300), default="")
    entity_type: Mapped[str] = mapped_column(Unicode(100), default="")
    category: Mapped[str] = mapped_column(Unicode(100), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class KnowledgeConsensus(Base):
    __tablename__ = "knowledge_consensus"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_sessions.id"), index=True)
    common_practices_json: Mapped[str] = mapped_column(UnicodeText, default="")
    differences_json: Mapped[str] = mapped_column(UnicodeText, default="")
    conflicting_advice_json: Mapped[str] = mapped_column(UnicodeText, default="")
    recommendation_json: Mapped[str] = mapped_column(UnicodeText, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class KnowledgeAiRun(Base):
    __tablename__ = "knowledge_ai_runs"
    __table_args__ = {"schema": KNOWLEDGE_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_sessions.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{KNOWLEDGE_SCHEMA + '.' if KNOWLEDGE_SCHEMA else ''}knowledge_documents.id"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(Unicode(50), default="")
    provider: Mapped[str] = mapped_column(Unicode(50), default="")
    model: Mapped[str] = mapped_column(Unicode(200), default="")
    prompt_name: Mapped[str] = mapped_column(Unicode(100), default="")
    prompt_version: Mapped[str] = mapped_column(Unicode(50), default="")
    system_prompt_hash: Mapped[str] = mapped_column(Unicode(128), default="")
    user_prompt_hash: Mapped[str] = mapped_column(Unicode(128), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4000)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Unicode(20), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
