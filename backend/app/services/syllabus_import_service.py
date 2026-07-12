import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.syllabus_pdf_parser import NEET_CONFIG, SyllabusParseConfig, SyllabusPdfParser
from app.models.system import SyllabusImportLog
from app.repositories.catalog_repository import CatalogRepository
from app.services import notification_service
from app.shared.logging import get_logger

logger = get_logger("syllabus_import")

# Registry of known parse configs, keyed by exam code. The importer itself is
# generic (see SyllabusPdfParser) — adding a new exam is a new
# SyllabusParseConfig entry here, never a parser code change.
PARSE_CONFIGS: dict[str, SyllabusParseConfig] = {
    "NEET": NEET_CONFIG,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SyllabusImportService:
    """Reusable official-syllabus PDF importer: PDF -> parsed hierarchy ->
    catalog upsert, with a logged, notified status for every attempt."""

    def __init__(self, db: Session):
        self.db = db
        self.catalog = CatalogRepository(db)

    def import_pdf(
        self,
        original_name: str,
        data: bytes,
        exam_code: str,
        user_id: int | None,
        config: SyllabusParseConfig | None = None,
    ) -> SyllabusImportLog:
        parse_config = config or PARSE_CONFIGS.get(exam_code.upper())
        if parse_config is None:
            raise ValueError(f"No syllabus parse config registered for exam code '{exam_code}'")

        exam_dir = settings.catalog_dir / "syllabus" / exam_code.upper()
        exam_dir.mkdir(parents=True, exist_ok=True)
        path = exam_dir / f"{uuid.uuid4().hex}_{Path(original_name).name}"
        path.write_bytes(data)

        log = SyllabusImportLog(
            exam_code=parse_config.exam_code,
            source_file=str(path),
            status="running",
            created_by=user_id,
            modified_by=user_id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        try:
            parsed_subjects = SyllabusPdfParser.parse(path, parse_config)
            counts = self.catalog.upsert_syllabus(
                parse_config.exam_code, parse_config.exam_name, parsed_subjects, user_id,
            )
            log.status = "success"
            log.subjects_count = counts["subjects"]
            log.units_count = counts["units"]
            log.chapters_count = counts["chapters"]
            log.topics_count = counts["topics"]
            log.created_count = counts["created"]
            log.updated_count = counts["updated"]
            log.finished_at = _now()
            self.db.commit()
            notification_service.push(
                self.db,
                "success",
                f"{parse_config.exam_name} syllabus imported",
                f"{counts['subjects']} subjects, {counts['units']} units, "
                f"{counts['chapters']} chapters, {counts['topics']} topics "
                f"({counts['created']} created, {counts['updated']} updated).",
                source="catalog",
            )
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            log.status = "failed"
            log.error = str(exc)[:2000]
            log.finished_at = _now()
            self.db.commit()
            notification_service.push(
                self.db,
                "error",
                f"{parse_config.exam_name} syllabus import failed",
                str(exc)[:500],
                source="catalog",
            )
            logger.exception("Syllabus import failed for %s", exam_code)
        return log

    def list_logs(self) -> list[SyllabusImportLog]:
        stmt = select(SyllabusImportLog).order_by(SyllabusImportLog.started_at.desc())
        return list(self.db.scalars(stmt))
