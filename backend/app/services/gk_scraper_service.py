"""Orchestrates a GK website scan end-to-end through the Phase 2A acquisition
framework: GkWebsiteProvider.discover() -> AcquisitionQueueService (durable
AcquisitionItem state, idempotent re-crawl) -> provider.fetch() ->
GkWebsiteParser.parse() -> Question Bank (MCQ/essay/fill-blank) or the
Documents module (PDFs). Writes a human-readable markdown profile of the site
to storage/gk_scraper/<domain>/profile.md.

Phase 1 scope: one homepage per run, triggered on demand. Multi-site rotation
and a daily scheduler are backlog (AcquisitionItem's idempotent
discovered/retry state machine is exactly what a later daily re-crawl needs;
nothing here has to change for that phase to build on top).
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.acquisition.dto import AcquisitionDocument
from app.integrations.acquisition.providers.gk_website import GkWebsiteProvider
from app.integrations.acquisition.providers.gk_website_parser import GkWebsiteParser
from app.models.acquisition import AcquisitionItem, AcquisitionJob
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.services import notification_service
from app.services.acquisition_queue_service import AcquisitionQueueService
from app.services.knowledge_service import KnowledgeService
from app.services.question_bank_service import QuestionBankService
from app.shared.logging import get_logger

logger = get_logger("gk_scraper")
SOURCE = "gk_scraper"
CATEGORY = "General Knowledge"


class GkScraperService:
    def __init__(self, db: Session):
        self.db = db
        self.jobs = AcquisitionJobRepository(db)
        self.queue = AcquisitionQueueService(db)

    # ---------- job creation (called from API) ----------

    def start_scan(self, homepage_url: str, user_id: int | None) -> AcquisitionJob:
        from app.core import acquisition_worker

        job = AcquisitionJob(
            source=SOURCE,
            job_type="gk_website_scrape",
            status="queued",
            stage="Queued",
            payload=json.dumps({"homepage_url": homepage_url}),
            created_by=user_id,
        )
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    # ---------- worker-run logic ----------

    def run_scrape(self, job: AcquisitionJob) -> None:
        payload = json.loads(job.payload or "{}")
        homepage_url = payload.get("homepage_url", "").strip()
        if not homepage_url:
            job.status = "failed"
            job.error = "homepage_url is required"
            self.jobs.save()
            return

        provider = GkWebsiteProvider(homepage_url)
        parser = GkWebsiteParser()
        qb = QuestionBankService(self.db)
        kb = KnowledgeService(self.db)

        job.status = "scanning"
        job.stage = "Discovering site structure"
        self.jobs.save()

        # Enqueue the FULL discovered pool (idempotent upsert by (provider,
        # source_id)) and process every one of it in this same run — a
        # single Start Scan click scrapes the entire site. pending() only
        # returns items still in discovered/retry, so a page already
        # completed by an earlier scan is naturally skipped on a re-run
        # (re-crawl) instead of being redone.
        #
        # A real site's full sitemap can be tens of thousands of pages
        # (gktoday.in alone is ~60k) — committing once per page here made
        # discovery itself take many minutes with zero visible progress
        # (looked exactly like a hang). Batch commits instead.
        discovered_count = 0
        _DISCOVER_BATCH = 500
        for document in provider.discover():
            self.queue.enqueue_discovered(document, job_id=job.id, commit=False)
            discovered_count += 1
            if discovered_count % _DISCOVER_BATCH == 0:
                self.db.commit()
                job.stage = f"Discovering site structure ({discovered_count} pages found so far)"
                self.jobs.save()
        self.db.commit()

        items: list[AcquisitionItem] = self.queue.pending(
            provider=provider.name, limit=settings.gk_scraper_pool_size
        )
        job.total = len(items)
        job.stage = f"{discovered_count} page(s) discovered; scraping all {len(items)} in this run"
        self.jobs.save()

        counts = {"mcq": 0, "essay": 0, "fill_blank": 0, "pdf": 0, "unsupported": 0, "error": 0}
        questions_created = 0
        pdf_docs = 0
        ai_pages = 0
        missing_solution = 0
        rows: list[dict] = []

        job.status = "downloading"
        self.jobs.save()

        # Only the network-bound fetch (provider.fetch — the HTTP GET + disk
        # write) runs concurrently across threads; everything that touches
        # self.db (queue state transitions, QuestionBankService,
        # KnowledgeService) stays on the main thread as each future completes
        # — SQLAlchemy Sessions aren't thread-safe, so this mirrors the
        # existing NcertService.run_download pattern (parallel download,
        # sequential DB writes) rather than giving each thread its own session.
        def fetch_one(item: AcquisitionItem):
            document = self._to_document(item)
            return document, provider.fetch(document)

        workers = max(1, settings.gk_scraper_concurrency)
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_item = {pool.submit(fetch_one, item): item for item in items}
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                done += 1
                job.processed = done
                job.stage = f"Processing {done}/{len(items)}"
                job.progress = int(90 * done / max(1, len(items)))

                try:
                    document, fetched = future.result()
                    self.queue.mark_downloading(item)
                    self.queue.mark_downloaded(item, fetched.local_file or "", fetched.checksum)

                    metadata = provider.extract_metadata(fetched)
                    fetched.metadata.update(metadata)
                    item.metadata_json = json.dumps(fetched.metadata)
                    item.document_type = fetched.document_type

                    page_type = metadata.get("page_type") or (
                        "pdf" if fetched.document_type == "pdf" else "unsupported"
                    )
                    counts[page_type] = counts.get(page_type, 0) + 1

                    if fetched.document_type == "pdf":
                        kb.ingest_external(
                            source=SOURCE,
                            source_ref=provider.domain,
                            title=Path(fetched.local_file).name,
                            path=Path(fetched.local_file),
                            user_id=job.created_by,
                        )
                        pdf_docs += 1
                        rows.append({"url": document.source_url, "type": "pdf", "notes": ""})
                    else:
                        parsed = parser.parse(fetched)
                        if parsed.warnings:
                            ai_pages += 1
                        created, no_solution = self._save_elements(qb, provider, fetched, parsed.elements, job.created_by)
                        questions_created += created
                        missing_solution += no_solution
                        rows.append({
                            "url": document.source_url,
                            "type": page_type,
                            "notes": f"{len(parsed.elements)} item(s), plugin={metadata.get('plugin') or 'generic'}"
                            + ("; " + "; ".join(parsed.warnings) if parsed.warnings else ""),
                        })

                    self.queue.mark_parsed(item)
                    self.queue.mark_completed(item)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("GK item failed for %s: %s", item.source_url, exc)
                    self.queue.mark_failed(item, str(exc))
                    counts["error"] += 1
                    rows.append({"url": item.source_url, "type": "error", "notes": str(exc)})

                self.jobs.save()

        profile_path = self._write_profile(
            provider, homepage_url, discovered_count, len(items), counts,
            questions_created, pdf_docs, ai_pages, missing_solution, rows,
        )

        job.processed = len(items)
        job.progress = 100
        job.status = "completed"
        job.stage = "Completed"
        job.payload = json.dumps({
            "homepage_url": homepage_url, "domain": provider.domain, "profile_path": str(profile_path),
        })
        self.jobs.save()
        notification_service.push(
            self.db, "success", "GK scrape complete",
            f"{provider.domain}: {questions_created} question(s), {pdf_docs} PDF(s) queued.", SOURCE,
        )

    # ---------- helpers ----------

    def _to_document(self, item: AcquisitionItem) -> AcquisitionDocument:
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

    def _save_elements(
        self, qb: QuestionBankService, provider: GkWebsiteProvider, document: AcquisitionDocument,
        elements: list[dict], user_id: int | None,
    ) -> tuple[int, int]:
        """Persists every element parsed off ONE page as a single DB
        transaction: `elements` is the parser's in-memory list for this page
        only (never accumulated across pages), each `qb.create()` below is
        `commit=False` (flush only, so FK ids/dup-hash checks still see
        earlier rows in this same page), and the one `self.db.commit()` at
        the end both writes the whole page's questions and frees the
        in-memory `elements` list for the next page — one DB round trip per
        page instead of one per question."""
        created = 0
        missing_solution = 0
        source_payload = {
            "provider": provider.name,
            "url": document.source_url,
            "website": provider.homepage_url,
            "exam": CATEGORY,
        }
        for el in elements:
            el_type = el.get("type")
            if el_type in ("mcq", "fill_blank"):
                # A page can be correctly classified/parsed yet still yield no
                # answer/explanation (AJAX-revealed answer failed, or the
                # source page itself has no "Notes:"/hint block) — that's a
                # real extraction gap, not a normal draft, so route it into
                # the existing review queue instead of silently saving it as
                # if it were complete.
                has_gap = not el.get("correct_answer_text") or not el.get("solution_text")
                if has_gap:
                    missing_solution += 1
                qb.create(
                    question_text=el["question_text"], exam=CATEGORY, question_type=el_type,
                    correct_answer_text=el.get("correct_answer_text", ""),
                    status="pending_review" if (el.get("ai_assisted") or has_gap) else "draft",
                    confidence=el.get("confidence", 0.6), options=el.get("options", []),
                    solution_text=el.get("solution_text", ""),
                    solution_source_type="ai_generated" if el.get("ai_assisted") else "scraped",
                    source=source_payload, created_by=user_id, commit=False,
                )
                created += 1
            elif el_type == "essay":
                qb.create(
                    question_text=el.get("title") or document.source_url, exam=CATEGORY, question_type="essay",
                    correct_answer_text=el.get("body", ""), status="draft", confidence=0.8,
                    source=source_payload, created_by=user_id, commit=False,
                )
                created += 1

        if created:
            self.db.commit()
        return created, missing_solution

    def _write_profile(
        self, provider: GkWebsiteProvider, homepage_url: str, pool_size: int, batch_processed: int,
        counts: dict, questions_created: int, pdf_docs: int, ai_pages: int, missing_solution: int,
        rows: list[dict],
    ) -> Path:
        site_dir = settings.gk_scraper_dir / provider.domain
        site_dir.mkdir(parents=True, exist_ok=True)
        path = site_dir / "profile.md"
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        status_counts = dict(
            self.db.query(AcquisitionItem.status, func.count())
            .filter(AcquisitionItem.provider == provider.name)
            .group_by(AcquisitionItem.status)
            .all()
        )
        completed_all_time = status_counts.get("completed", 0)
        remaining = max(0, pool_size - completed_all_time)

        lines = [
            f"# Site Profile: {provider.domain}", "",
            f"- Homepage: {homepage_url}",
            f"- Last scanned: {now}",
            f"- Discovery method: {provider.discovery_method}",
            f"- Known pages (pool): {pool_size}",
            f"- Processed this run: {batch_processed}",
            f"- Completed all-time: {completed_all_time} / {pool_size}"
            f" ({remaining} remaining — non-zero only if new pages appeared or some failed;"
            " click Start Scan again to pick those up)", "",
            "## Page type breakdown", "",
            f"- MCQ pages: {counts.get('mcq', 0)}",
            f"- Essay/article pages: {counts.get('essay', 0)}",
            f"- Fill-in-the-blank pages: {counts.get('fill_blank', 0)}",
            f"- PDF documents: {counts.get('pdf', 0)}",
            f"- Unsupported/unclassified: {counts.get('unsupported', 0)}",
            f"- Errors: {counts.get('error', 0)}", "",
            f"- Questions saved to Question Bank: {questions_created}",
            f"- PDFs queued into Documents module: {pdf_docs}",
            f"- Pages requiring AI-assisted extraction: {ai_pages}",
            f"- MCQ/fill-blank saved without a full answer+solution: {missing_solution}"
            " (flagged pending_review in Question Bank — either the source page has no"
            " explanation, or extraction failed; review/re-scan to close the gap)", "",
            "## Pages", "",
            "| URL | Type | Notes |",
            "|---|---|---|",
        ]
        for r in rows:
            notes = (r.get("notes") or "").replace("|", "/")
            lines.append(f"| {r['url']} | {r['type']} | {notes} |")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
