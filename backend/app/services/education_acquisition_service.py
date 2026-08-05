from __future__ import annotations

import csv
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.acquisition.providers.education import build_discovery_providers, parse_education_document
from app.integrations.acquisition.providers.education.discovery import _is_relevant_search_target
from app.integrations.acquisition.providers.education.discovery import EducationDiscoveryConfig
from app.models.acquisition import AcquisitionItem, AcquisitionJob
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.education_repository import EducationRepository
from app.services import notification_service
from app.services.acquisition_queue_service import AcquisitionQueueService
from app.shared.logging import get_logger

logger = get_logger("education_acquisition")
SOURCE = "education_acquisition"
EXPORT_FIELDS = [
    "document_id", "institution_name", "institution_type", "board", "state", "district",
    "document_type", "classification", "title", "url", "tag", "field_name", "field_value",
]


class EducationAcquisitionService:
    def __init__(self, db: Session):
        self.db = db
        self.jobs = AcquisitionJobRepository(db)
        self.queue = AcquisitionQueueService(db)
        self.repo = EducationRepository(db)

    def start_scan(self, payload: dict, user_id: int | None) -> AcquisitionJob:
        from app.core import acquisition_worker

        job = AcquisitionJob(
            source=SOURCE,
            job_type="education_scrape",
            status="queued",
            stage="Queued",
            payload=json.dumps(payload),
            created_by=user_id,
        )
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    def run_scrape(self, job: AcquisitionJob) -> None:
        payload = json.loads(job.payload or "{}")
        config = EducationDiscoveryConfig(
            queries=_clean_list(payload.get("queries", [])),
            manual_urls=_clean_list(payload.get("manual_urls", [])),
            root_urls=_clean_list(payload.get("root_urls", [])),
            rss_urls=_clean_list(payload.get("rss_urls", [])),
            government_urls=_clean_list(payload.get("government_urls", [])),
            providers=_clean_list(payload.get("providers", [])) or [
                "manual_url", "sitemap", "website_crawl", "pdf_discovery", "document_discovery", "duckduckgo",
            ],
            max_pages_per_root=max(1, int(payload.get("max_pages_per_root", 50))),
            max_search_results=max(1, int(payload.get("max_search_results", 30))),
        )

        providers = build_discovery_providers(config)
        if not providers:
            raise ValueError("At least one provider with usable input is required")

        job.status = "scanning"
        job.stage = "Discovering public education URLs"
        self.jobs.save()

        discovered = 0
        provider_items: dict[str, list[AcquisitionItem]] = {}
        for provider in providers:
            items: list[AcquisitionItem] = []
            for document in provider.discover():
                items.append(self.queue.enqueue_discovered(document, job_id=job.id, commit=False))
                discovered += 1
                if discovered % 200 == 0:
                    self.db.commit()
                    job.stage = f"Discovering URLs ({discovered} found)"
                    self.jobs.save()
            provider_items[provider.name] = items
        self.db.commit()

        pending = 0
        for provider in providers:
            provider_items[provider.name] = self.queue.pending(provider=provider.name, limit=20000)
            pending += len(provider_items[provider.name])
        job.total = pending
        job.processed = 0
        job.progress = 5
        job.stage = f"{discovered} URLs discovered; processing {pending} pending item(s)"
        job.status = "downloading"
        self.jobs.save()

        processed_documents = 0
        for provider in providers:
            items = provider_items.get(provider.name, [])
            if not items:
                continue
            processed_documents += self._process_provider_items(job, provider, items)

        job.status = "completed"
        job.stage = "Completed"
        job.progress = 100
        job.processed = processed_documents
        self.jobs.save()

        self._write_exports()
        notification_service.push(
            self.db,
            "success",
            "Education scrape complete",
            f"{processed_documents} document(s) normalized into the education knowledge store.",
            SOURCE,
        )

    def _process_provider_items(self, job: AcquisitionJob, provider, items: list[AcquisitionItem]) -> int:
        done = 0
        workers = min(8, max(1, len(items)))

        def fetch_one(item: AcquisitionItem):
            document = self._to_document(item)
            fetched = provider.fetch(document)
            metadata = provider.extract_metadata(fetched)
            fetched.metadata.update(metadata)
            return item, fetched

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_item = {pool.submit(fetch_one, item): item for item in items}
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    self.queue.mark_downloading(item)
                    item, fetched = future.result()
                    self.queue.mark_downloaded(item, fetched.local_file or "", fetched.checksum)
                    parsed = parse_education_document(fetched)
                    if _should_skip_document(fetched.source_url, parsed.title, parsed.summary):
                        self.queue.mark_completed(item)
                        self.db.commit()
                        continue
                    if fetched.metadata.get("origin") == "search" and not _is_relevant_search_target(fetched.source_url):
                        self.queue.mark_completed(item)
                        self.db.commit()
                        continue
                    source = self.repo.upsert_source(
                        source_key=parsed.source_key,
                        institution_name=parsed.institution_name,
                        institution_type=parsed.institution_type,
                        board=parsed.board,
                        state=parsed.state,
                        district=parsed.district,
                        website_url=f"{url_scheme_host(fetched.source_url)}",
                        source_kind=fetched.metadata.get("source_kind", provider.source_kind),
                        is_government=parsed.is_government,
                        metadata=parsed.metadata,
                    )
                    self.db.flush()
                    self.repo.replace_document(
                        source=source,
                        acquisition_item_id=item.id,
                        url=fetched.source_url,
                        title=parsed.title,
                        document_type=fetched.document_type,
                        classification=parsed.classification,
                        file_type=fetched.document_type,
                        checksum=fetched.checksum,
                        local_file=fetched.local_file or "",
                        language=fetched.language,
                        summary=parsed.summary,
                        metadata=parsed.metadata,
                        fields=parsed.fields,
                        tags=parsed.tags,
                    )
                    self.queue.mark_parsed(item)
                    self.queue.mark_completed(item)
                    self.db.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Education item failed for %s: %s", item.source_url, exc)
                    self.db.rollback()
                    self.queue.mark_failed(item, str(exc))
                done += 1
                job.processed += 1
                job.progress = min(95, 5 + int(90 * job.processed / max(1, job.total)))
                job.stage = f"Processing {job.processed}/{job.total}"
                self.jobs.save()
        return done

    def list_jobs(self) -> list[AcquisitionJob]:
        return self.jobs.list(SOURCE)

    def stats(self) -> dict[str, int]:
        return self.repo.stats()

    def list_sources(self, **kwargs):
        return self.repo.list_sources(**kwargs)

    def list_documents(self, **kwargs):
        return self.repo.list_documents(**kwargs)

    def export_rows(self) -> list[dict]:
        documents, _ = self.repo.list_documents(limit=5000)
        rows: list[dict] = []
        for document in documents:
            source = self.repo.get_source(document.source_id) if document.source_id else None
            fields = self.repo.document_fields(document.id)
            tags = self.repo.document_tags(document.id) or [""]
            if not fields:
                rows.append({
                    "document_id": document.id,
                    "institution_name": source.institution_name if source else "",
                    "institution_type": source.institution_type if source else "",
                    "board": source.board if source else "",
                    "state": source.state if source else "",
                    "district": source.district if source else "",
                    "document_type": document.document_type,
                    "classification": document.classification,
                    "title": document.title,
                    "url": document.url,
                    "tag": tags[0],
                    "field_name": "",
                    "field_value": "",
                })
                continue
            for field in fields:
                rows.append({
                    "document_id": document.id,
                    "institution_name": source.institution_name if source else "",
                    "institution_type": source.institution_type if source else "",
                    "board": source.board if source else "",
                    "state": source.state if source else "",
                    "district": source.district if source else "",
                    "document_type": document.document_type,
                    "classification": document.classification,
                    "title": document.title,
                    "url": document.url,
                    "tag": ", ".join(tags),
                    "field_name": field.canonical_key,
                    "field_value": field.value,
                })
        return rows

    def export_json(self) -> dict:
        return {"generated_from": SOURCE, "rows": self.export_rows(), "stats": self.stats()}

    def export_csv(self) -> str:
        rows = self.export_rows()
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    def export_markdown(self) -> str:
        rows = self.export_rows()
        lines = [
            "# Education Knowledge Export",
            "",
            f"- Sources: {self.stats()['sources']}",
            f"- Documents: {self.stats()['documents']}",
            f"- Fields: {self.stats()['fields']}",
            "",
            "| Institution | Type | Board | State | Classification | Field | Value | URL |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in rows[:1000]:
            lines.append(
                f"| {safe_md(row['institution_name'])} | {safe_md(row['institution_type'])} | "
                f"{safe_md(row['board'])} | {safe_md(row['state'])} | {safe_md(row['classification'])} | "
                f"{safe_md(row['field_name'])} | {safe_md(row['field_value'])} | {safe_md(row['url'])} |"
            )
        return "\n".join(lines)

    def export_sqlite(self) -> Path:
        out = settings.education_dir / "exports" / "education_knowledge.sqlite"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        conn = sqlite3.connect(out)
        try:
            conn.execute(
                """
                CREATE TABLE education_export (
                    document_id TEXT,
                    institution_name TEXT,
                    institution_type TEXT,
                    board TEXT,
                    state TEXT,
                    district TEXT,
                    document_type TEXT,
                    classification TEXT,
                    title TEXT,
                    url TEXT,
                    tag TEXT,
                    field_name TEXT,
                    field_value TEXT
                )
                """
            )
            conn.executemany(
                "INSERT INTO education_export VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    tuple(row[field] for field in EXPORT_FIELDS)
                    for row in self.export_rows()
                ],
            )
            conn.commit()
        finally:
            conn.close()
        return out

    def _write_exports(self) -> None:
        export_dir = settings.education_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "education_knowledge.json").write_text(
            json.dumps(self.export_json(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (export_dir / "education_knowledge.csv").write_text(self.export_csv(), encoding="utf-8")
        (export_dir / "education_knowledge.md").write_text(self.export_markdown(), encoding="utf-8")
        self.export_sqlite()

    def _to_document(self, item: AcquisitionItem):
        from app.integrations.acquisition.dto import AcquisitionDocument

        metadata = json.loads(item.metadata_json or "{}")
        return AcquisitionDocument(
            provider=item.provider,
            source_id=item.source_id,
            source_url=item.source_url,
            document_type=item.document_type or "unknown",
            language=item.language,
            checksum=item.checksum,
            metadata=metadata,
            local_file=item.local_file or None,
        )


def _clean_list(value) -> list[str]:
    if isinstance(value, str):
        parts = [line.strip() for line in value.splitlines()]
        return [part for part in parts if part]
    return [str(item).strip() for item in value or [] if str(item).strip()]


def safe_md(value: str) -> str:
    return (value or "").replace("|", "/").replace("\n", " ").strip()


def url_scheme_host(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else url


def _should_skip_document(url: str, title: str, summary: str) -> bool:
    lowered_title = (title or "").strip().lower()
    lowered_summary = (summary or "").strip().lower()
    lowered_url = (url or "").strip().lower()
    if not lowered_url.startswith("http"):
        return True
    if "bing.com/ck/a" in lowered_url:
        return True
    if lowered_title in {"please", "loading...", "redirecting...", "just a moment..."}:
        return True
    if "click here if the page does not redirect automatically" in lowered_summary:
        return True
    return False
