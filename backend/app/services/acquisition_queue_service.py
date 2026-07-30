"""The Acquisition Queue (Phase 2A): the durable state machine behind every
acquisition provider.

Providers themselves never write to the database — `discover()`/`fetch()`/
`validate()`/`extract_metadata()` are pure functions over `AcquisitionDocument`.
This service is the only thing that persists an `AcquisitionItem` and drives
its state transitions:

    discovered -> downloading -> downloaded -> parsed -> completed
                       \\-> failed <-> retry -/

No crawler calls into this yet — Phase 2A ships the queue itself, exercised
by mock providers in tests.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.integrations.acquisition.dto import AcquisitionDocument
from app.models.acquisition import ACQUISITION_ITEM_STATUSES, AcquisitionItem
from app.repositories.acquisition_item_repository import AcquisitionItemRepository


class AcquisitionQueueService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AcquisitionItemRepository(db)

    def enqueue_discovered(
        self, document: AcquisitionDocument, job_id: int | None = None, commit: bool = True,
    ) -> AcquisitionItem:
        """Idempotent: re-discovering the same (provider, source_id) touches
        the existing row instead of creating a duplicate, so re-running
        discover() (checkpoint recovery, a scheduled re-crawl) is always safe.

        `commit=False` matters at real site scale: a full-site discovery pass
        can be tens of thousands of pages (see `gk_scraper_pool_size`), and
        committing once per page here made discovery itself the bottleneck —
        looked like the whole scan had hung. Callers doing a bulk discovery
        loop should pass `commit=False` and commit periodically instead."""
        errors = document.validate()
        if errors:
            raise ValueError(f"Invalid AcquisitionDocument: {'; '.join(errors)}")

        existing = self.repo.find(document.provider, document.source_id)
        if existing:
            existing.source_url = document.source_url
            existing.document_type = document.document_type
            existing.language = document.language
            existing.metadata_json = json.dumps(document.metadata)
            if job_id is not None:
                existing.job_id = job_id
            return self.repo.save(existing, commit=commit)

        item = AcquisitionItem(
            job_id=job_id,
            provider=document.provider,
            source_id=document.source_id,
            source_url=document.source_url,
            document_type=document.document_type,
            language=document.language,
            checksum=document.checksum,
            metadata_json=json.dumps(document.metadata),
            status="discovered",
        )
        return self.repo.save(item, commit=commit)

    def mark_downloading(self, item: AcquisitionItem) -> AcquisitionItem:
        item.status = "downloading"
        return self.repo.save(item)

    def mark_downloaded(self, item: AcquisitionItem, local_file: str, checksum: str) -> AcquisitionItem:
        item.status = "downloaded"
        item.local_file = local_file
        item.checksum = checksum
        item.error = ""
        return self.repo.save(item)

    def mark_parsed(self, item: AcquisitionItem) -> AcquisitionItem:
        item.status = "parsed"
        return self.repo.save(item)

    def mark_completed(self, item: AcquisitionItem) -> AcquisitionItem:
        item.status = "completed"
        return self.repo.save(item)

    def mark_failed(self, item: AcquisitionItem, error: str) -> AcquisitionItem:
        """Queues a retry while retries remain; fails permanently once
        `max_retries` is exhausted."""
        item.error = error[:2000]
        if item.retry_count < item.max_retries:
            item.retry_count += 1
            item.status = "retry"
        else:
            item.status = "failed"
        return self.repo.save(item)

    def recover_stuck(self, older_than_minutes: int = 30) -> list[AcquisitionItem]:
        """Checkpoint recovery: items left mid-flight (e.g. a worker crashed
        while downloading) are requeued as retries instead of being lost."""
        stuck = self.repo.stuck(["downloading"], older_than_minutes)
        return [self.mark_failed(item, "Recovered after being stuck in 'downloading'") for item in stuck]

    def pending(self, provider: str | None = None, limit: int = 100) -> list[AcquisitionItem]:
        return self.repo.pending(provider=provider, limit=limit)

    def stats(self) -> dict[str, int]:
        raw = self.repo.stats()
        return {status: raw.get(status, 0) for status in ACQUISITION_ITEM_STATUSES}
