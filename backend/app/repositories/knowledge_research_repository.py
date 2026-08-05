from __future__ import annotations

from sqlalchemy import delete, func, select

from app.database.session import SessionLocal
from app.models.knowledge_research import (
    KnowledgeAiRun,
    KnowledgeConsensus,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeFact,
    KnowledgeSession,
)


def _session_to_dict(row: KnowledgeSession) -> dict:
    return {
        "id": row.id,
        "mode": row.mode,
        "input_value": row.input_value,
        "source_count_requested": row.source_count_requested,
        "source_type": row.source_type,
        "ai_provider": row.ai_provider,
        "ai_model": row.ai_model,
        "status": row.status,
        "current_stage": row.current_stage,
        "progress": row.progress,
        "storage_directory": row.storage_directory,
        "pipeline_version": row.pipeline_version,
        "report_path": row.report_path,
        "report_markdown_path": row.report_markdown_path,
        "error_message": row.error_message,
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _document_to_dict(row: KnowledgeDocument) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "document_type": row.document_type,
        "source_reference": row.source_reference,
        "title": row.title,
        "url": row.url,
        "language": row.language,
        "duration": row.duration,
        "word_count": row.word_count,
        "character_count": row.character_count,
        "file_size": row.file_size,
        "checksum": row.checksum,
        "processing_version": row.processing_version,
        "transcript_path": row.transcript_path,
        "subtitle_path": row.subtitle_path,
        "ocr_path": row.ocr_path,
        "merged_text_path": row.merged_text_path,
        "summary_path": row.summary_path,
        "status": row.status,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _fact_to_dict(row: KnowledgeFact) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "document_id": row.document_id,
        "category": row.category,
        "subcategory": row.subcategory,
        "value": row.value,
        "confidence": row.confidence,
        "evidence": row.evidence,
        "stage": row.stage,
        "source_document": row.source_document,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _entity_to_dict(row: KnowledgeEntity) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "document_id": row.document_id,
        "entity_name": row.entity_name,
        "entity_type": row.entity_type,
        "category": row.category,
        "confidence": row.confidence,
        "evidence": row.evidence,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _consensus_to_dict(row: KnowledgeConsensus) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "common_practices_json": row.common_practices_json,
        "differences_json": row.differences_json,
        "conflicting_advice_json": row.conflicting_advice_json,
        "recommendation_json": row.recommendation_json,
        "confidence": row.confidence,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _ai_run_to_dict(row: KnowledgeAiRun) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "document_id": row.document_id,
        "stage": row.stage,
        "provider": row.provider,
        "model": row.model,
        "prompt_name": row.prompt_name,
        "prompt_version": row.prompt_version,
        "system_prompt_hash": row.system_prompt_hash,
        "user_prompt_hash": row.user_prompt_hash,
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "estimated_cost": row.estimated_cost,
        "latency_ms": row.latency_ms,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class KnowledgeRepository:
    def create_session(
        self,
        mode,
        input_value,
        source_count_requested,
        source_type,
        ai_provider,
        ai_model,
        storage_directory,
        pipeline_version,
        temperature=0.2,
        max_tokens=4000,
    ):
        with SessionLocal() as db:
            row = KnowledgeSession(
                mode=mode,
                input_value=input_value,
                source_count_requested=source_count_requested,
                source_type=source_type,
                ai_provider=ai_provider,
                ai_model=ai_model,
                status="QUEUED",
                current_stage="QUEUED",
                progress=0,
                storage_directory=storage_directory,
                pipeline_version=pipeline_version,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id

    def get_session(self, session_id):
        with SessionLocal() as db:
            row = db.get(KnowledgeSession, session_id)
            return _session_to_dict(row) if row else None

    def set_session_storage_directory(self, session_id, storage_directory):
        with SessionLocal() as db:
            row = db.get(KnowledgeSession, session_id)
            if not row:
                return
            row.storage_directory = storage_directory
            db.commit()

    def update_session_progress(self, session_id, status, current_stage, progress):
        with SessionLocal() as db:
            row = db.get(KnowledgeSession, session_id)
            if not row:
                return
            row.status = status
            row.current_stage = current_stage
            row.progress = progress
            db.commit()

    def set_session_report(self, session_id, report_path, report_markdown_path):
        with SessionLocal() as db:
            row = db.get(KnowledgeSession, session_id)
            if not row:
                return
            row.report_path = report_path
            row.report_markdown_path = report_markdown_path
            db.commit()

    def set_session_error(self, session_id, error_message):
        with SessionLocal() as db:
            row = db.get(KnowledgeSession, session_id)
            if not row:
                return
            row.status = "FAILED"
            row.error_message = error_message
            db.commit()

    def list_sessions(
        self,
        status=None,
        topic=None,
        date_from=None,
        date_to=None,
        provider=None,
        source_type=None,
    ):
        with SessionLocal() as db:
            totals = (
                select(
                    KnowledgeAiRun.session_id.label("session_id"),
                    func.coalesce(func.sum(KnowledgeAiRun.estimated_cost), 0).label("total_cost"),
                    func.coalesce(
                        func.sum(KnowledgeAiRun.input_tokens + KnowledgeAiRun.output_tokens),
                        0,
                    ).label("total_tokens"),
                )
                .group_by(KnowledgeAiRun.session_id)
                .subquery()
            )

            stmt = (
                select(KnowledgeSession, totals.c.total_cost, totals.c.total_tokens)
                .outerjoin(totals, totals.c.session_id == KnowledgeSession.id)
                .order_by(KnowledgeSession.id.desc())
            )

            if status:
                stmt = stmt.where(KnowledgeSession.status == status)
            if topic:
                stmt = stmt.where(KnowledgeSession.input_value.ilike(f"%{topic}%"))
            if date_from:
                stmt = stmt.where(KnowledgeSession.created_at >= date_from)
            if date_to:
                stmt = stmt.where(KnowledgeSession.created_at <= date_to)
            if provider:
                stmt = stmt.where(KnowledgeSession.ai_provider == provider)
            if source_type:
                stmt = stmt.where(KnowledgeSession.source_type == source_type)

            rows = db.execute(stmt).all()
            sessions = []
            for row, total_cost, total_tokens in rows:
                item = _session_to_dict(row)
                item["total_cost"] = float(total_cost or 0)
                item["total_tokens"] = int(total_tokens or 0)
                sessions.append(item)
            return sessions

    def delete_session(self, session_id):
        with SessionLocal() as db:
            db.execute(delete(KnowledgeAiRun).where(KnowledgeAiRun.session_id == session_id))
            db.execute(delete(KnowledgeConsensus).where(KnowledgeConsensus.session_id == session_id))
            db.execute(delete(KnowledgeEntity).where(KnowledgeEntity.session_id == session_id))
            db.execute(delete(KnowledgeFact).where(KnowledgeFact.session_id == session_id))
            db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.session_id == session_id))
            db.execute(delete(KnowledgeSession).where(KnowledgeSession.id == session_id))
            db.commit()

    def create_document(self, session_id, document_type, source_reference, title, url):
        with SessionLocal() as db:
            row = KnowledgeDocument(
                session_id=session_id,
                document_type=document_type,
                source_reference=source_reference,
                title=title,
                url=url,
                status="QUEUED",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row.id

    def update_document_extraction(
        self,
        document_id,
        language,
        duration,
        word_count,
        character_count,
        file_size,
        checksum,
        processing_version,
        transcript_path,
        subtitle_path,
        ocr_path,
        merged_text_path,
    ):
        with SessionLocal() as db:
            row = db.get(KnowledgeDocument, document_id)
            if not row:
                return
            row.language = language
            row.duration = duration
            row.word_count = word_count
            row.character_count = character_count
            row.file_size = file_size
            row.checksum = checksum
            row.processing_version = processing_version
            row.transcript_path = transcript_path
            row.subtitle_path = subtitle_path
            row.ocr_path = ocr_path
            row.merged_text_path = merged_text_path
            db.commit()

    def update_document_summary(self, document_id, summary_path):
        with SessionLocal() as db:
            row = db.get(KnowledgeDocument, document_id)
            if not row:
                return
            row.summary_path = summary_path
            db.commit()

    def update_document_status(self, document_id, status, error_message=None):
        with SessionLocal() as db:
            row = db.get(KnowledgeDocument, document_id)
            if not row:
                return
            row.status = status
            row.error_message = error_message or ""
            db.commit()

    def get_document(self, document_id):
        with SessionLocal() as db:
            row = db.get(KnowledgeDocument, document_id)
            return _document_to_dict(row) if row else None

    def list_documents_by_session(self, session_id):
        with SessionLocal() as db:
            rows = db.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.session_id == session_id)
                .order_by(KnowledgeDocument.id)
            ).all()
            return [_document_to_dict(row) for row in rows]

    def create_fact(
        self,
        session_id,
        document_id,
        category,
        subcategory,
        value,
        confidence,
        evidence,
        stage,
        source_document,
    ):
        with SessionLocal() as db:
            db.add(
                KnowledgeFact(
                    session_id=session_id,
                    document_id=document_id,
                    category=category,
                    subcategory=subcategory,
                    value=value,
                    confidence=confidence,
                    evidence=evidence,
                    stage=stage,
                    source_document=source_document,
                )
            )
            db.commit()

    def list_facts_by_session(self, session_id):
        with SessionLocal() as db:
            rows = db.scalars(
                select(KnowledgeFact)
                .where(KnowledgeFact.session_id == session_id)
                .order_by(KnowledgeFact.id)
            ).all()
            return [_fact_to_dict(row) for row in rows]

    def create_entity(
        self,
        session_id,
        document_id,
        entity_name,
        entity_type,
        category,
        confidence,
        evidence,
    ):
        with SessionLocal() as db:
            db.add(
                KnowledgeEntity(
                    session_id=session_id,
                    document_id=document_id,
                    entity_name=entity_name,
                    entity_type=entity_type,
                    category=category,
                    confidence=confidence,
                    evidence=evidence,
                )
            )
            db.commit()

    def list_entities_by_session(self, session_id):
        with SessionLocal() as db:
            rows = db.scalars(
                select(KnowledgeEntity)
                .where(KnowledgeEntity.session_id == session_id)
                .order_by(KnowledgeEntity.id)
            ).all()
            return [_entity_to_dict(row) for row in rows]

    def create_consensus(
        self,
        session_id,
        common_practices_json,
        differences_json,
        conflicting_advice_json,
        recommendation_json,
        confidence,
    ):
        with SessionLocal() as db:
            db.add(
                KnowledgeConsensus(
                    session_id=session_id,
                    common_practices_json=common_practices_json,
                    differences_json=differences_json,
                    conflicting_advice_json=conflicting_advice_json,
                    recommendation_json=recommendation_json,
                    confidence=confidence,
                )
            )
            db.commit()

    def get_consensus_by_session(self, session_id):
        with SessionLocal() as db:
            row = db.scalars(
                select(KnowledgeConsensus)
                .where(KnowledgeConsensus.session_id == session_id)
                .order_by(KnowledgeConsensus.id.desc())
                .limit(1)
            ).first()
            return _consensus_to_dict(row) if row else None

    def create_ai_run(
        self,
        session_id,
        document_id,
        stage,
        provider,
        model,
        prompt_name,
        prompt_version,
        system_prompt_hash,
        user_prompt_hash,
        temperature,
        max_tokens,
        input_tokens,
        output_tokens,
        estimated_cost,
        latency_ms,
        status,
    ):
        with SessionLocal() as db:
            db.add(
                KnowledgeAiRun(
                    session_id=session_id,
                    document_id=document_id,
                    stage=stage,
                    provider=provider,
                    model=model,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    system_prompt_hash=system_prompt_hash,
                    user_prompt_hash=user_prompt_hash,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    latency_ms=latency_ms,
                    status=status,
                )
            )
            db.commit()

    def list_ai_runs_by_session(self, session_id):
        with SessionLocal() as db:
            rows = db.scalars(
                select(KnowledgeAiRun)
                .where(KnowledgeAiRun.session_id == session_id)
                .order_by(KnowledgeAiRun.id)
            ).all()
            return [_ai_run_to_dict(row) for row in rows]
