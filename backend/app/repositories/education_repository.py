from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.education import EducationDocument, EducationField, EducationSource, EducationTag


class EducationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_document(self, document_id: str) -> EducationDocument | None:
        return self.db.get(EducationDocument, document_id)

    def get_source(self, source_id: str) -> EducationSource | None:
        return self.db.get(EducationSource, source_id)

    def get_document_by_url(self, url: str) -> EducationDocument | None:
        return self.db.scalar(select(EducationDocument).where(EducationDocument.url == url))

    def get_source_by_key(self, source_key: str) -> EducationSource | None:
        return self.db.scalar(select(EducationSource).where(EducationSource.source_key == source_key))

    def upsert_source(
        self,
        *,
        source_key: str,
        institution_name: str,
        institution_type: str,
        board: str,
        state: str,
        district: str,
        website_url: str,
        source_kind: str,
        is_government: bool,
        metadata: dict,
    ) -> EducationSource:
        source = self.get_source_by_key(source_key)
        if source is None:
            source = EducationSource(source_key=source_key)
            self.db.add(source)
        source.institution_name = institution_name[:300]
        source.institution_type = institution_type[:60]
        source.board = board[:120]
        source.state = state[:120]
        source.district = district[:120]
        source.website_url = website_url[:1000]
        source.source_kind = source_kind[:40]
        source.is_government = "true" if is_government else "false"
        source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        return source

    def replace_document(
        self,
        *,
        source: EducationSource | None,
        acquisition_item_id: int | None,
        url: str,
        title: str,
        document_type: str,
        classification: str,
        file_type: str,
        checksum: str,
        local_file: str,
        language: str,
        summary: str,
        metadata: dict,
        fields: list[dict],
        tags: Iterable[str],
    ) -> EducationDocument:
        document = self.get_document_by_url(url)
        if document is None:
            document = EducationDocument(url=url)
            self.db.add(document)
            self.db.flush()

        document.source_id = source.id if source else None
        document.acquisition_item_id = acquisition_item_id
        document.title = title[:500]
        document.document_type = document_type[:60]
        document.classification = classification[:80]
        document.file_type = file_type[:30]
        document.checksum = checksum[:64]
        document.local_file = local_file[:600]
        document.language = language[:20]
        document.summary = summary
        document.metadata_json = json.dumps(metadata, ensure_ascii=False)

        self.db.query(EducationField).filter(EducationField.document_id == document.id).delete()
        self.db.query(EducationTag).filter(EducationTag.document_id == document.id).delete()
        self.db.flush()

        for index, field in enumerate(fields):
            self.db.add(
                EducationField(
                    document_id=document.id,
                    canonical_key=(field.get("canonical_key") or "")[:120],
                    label=(field.get("label") or "")[:240],
                    value=field.get("value") or "",
                    value_type=(field.get("value_type") or "text")[:40],
                    source_kind=(field.get("source_kind") or "metadata")[:40],
                    confidence=float(field.get("confidence") or 0.0),
                    order_index=index,
                )
            )
        for tag in sorted({(tag or "").strip().lower() for tag in tags if (tag or "").strip()}):
            self.db.add(EducationTag(document_id=document.id, tag=tag[:80]))

        return document

    def stats(self) -> dict[str, int]:
        return {
            "sources": int(self.db.scalar(select(func.count()).select_from(EducationSource)) or 0),
            "documents": int(self.db.scalar(select(func.count()).select_from(EducationDocument)) or 0),
            "fields": int(self.db.scalar(select(func.count()).select_from(EducationField)) or 0),
            "forms": int(
                self.db.scalar(
                    select(func.count()).select_from(EducationDocument).where(
                        EducationDocument.classification.in_(
                            ["admission_form", "application_form", "medical_form", "transport_form", "hostel_form", "leave_form"]
                        )
                    )
                )
                or 0
            ),
        }

    def list_sources(
        self,
        *,
        q: str = "",
        institution_type: str = "",
        board: str = "",
        state: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EducationSource], int]:
        stmt = select(EducationSource)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    EducationSource.institution_name.ilike(like),
                    EducationSource.website_url.ilike(like),
                    EducationSource.district.ilike(like),
                )
            )
        if institution_type:
            stmt = stmt.where(EducationSource.institution_type == institution_type)
        if board:
            stmt = stmt.where(EducationSource.board == board)
        if state:
            stmt = stmt.where(EducationSource.state == state)
        total = int(self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(
            self.db.scalars(
                stmt.order_by(EducationSource.updated_at.desc()).offset(offset).limit(limit)
            )
        )
        return items, total

    def list_documents(
        self,
        *,
        q: str = "",
        institution: str = "",
        state: str = "",
        district: str = "",
        board: str = "",
        document_type: str = "",
        tag: str = "",
        field_name: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[EducationDocument], int]:
        stmt = select(EducationDocument).join(
            EducationSource,
            EducationSource.id == EducationDocument.source_id,
            isouter=True,
        )
        if tag:
            stmt = stmt.join(EducationTag, EducationTag.document_id == EducationDocument.id)
        if field_name:
            stmt = stmt.join(EducationField, EducationField.document_id == EducationDocument.id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    EducationDocument.title.ilike(like),
                    EducationDocument.url.ilike(like),
                    EducationDocument.summary.ilike(like),
                    EducationSource.institution_name.ilike(like),
                )
            )
        if institution:
            stmt = stmt.where(EducationSource.institution_name.ilike(f"%{institution}%"))
        if state:
            stmt = stmt.where(EducationSource.state == state)
        if district:
            stmt = stmt.where(EducationSource.district == district)
        if board:
            stmt = stmt.where(EducationSource.board == board)
        if document_type:
            stmt = stmt.where(EducationDocument.classification == document_type)
        if tag:
            stmt = stmt.where(EducationTag.tag == tag)
        if field_name:
            stmt = stmt.where(EducationField.canonical_key == field_name)
        stmt = stmt.distinct()
        total = int(self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(
            self.db.scalars(
                stmt.order_by(EducationDocument.updated_at.desc()).offset(offset).limit(limit)
            )
        )
        return items, total

    def document_fields(self, document_id: str) -> list[EducationField]:
        return list(
            self.db.scalars(
                select(EducationField)
                .where(EducationField.document_id == document_id)
                .order_by(EducationField.order_index.asc(), EducationField.id.asc())
            )
        )

    def document_tags(self, document_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(EducationTag.tag).where(EducationTag.document_id == document_id).order_by(EducationTag.tag.asc())
            )
        )
