import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.ncert_downloader import NcertDownloader
from app.integrations.ncert_scraper import NcertScraper
from app.models.acquisition import AcquisitionJob, NcertBook
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.ncert_repository import NcertRepository
from app.services import notification_service
from app.shared.logging import get_logger

logger = get_logger("ncert")
SOURCE = "ncert"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class NcertService:
    def __init__(self, db: Session):
        self.db = db
        self.books = NcertRepository(db)
        self.jobs = AcquisitionJobRepository(db)

    # ---------- job creation (called from API) ----------

    def start_scan(self, user_id: int | None) -> AcquisitionJob:
        from app.core import acquisition_worker

        job = AcquisitionJob(source=SOURCE, job_type="scan", status="queued", stage="Queued", created_by=user_id)
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    def start_refresh(self, user_id: int | None) -> AcquisitionJob:
        from app.core import acquisition_worker

        job = AcquisitionJob(source=SOURCE, job_type="refresh", status="queued", stage="Queued", created_by=user_id)
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    def queue_downloads(self, book_ids: list[int], user_id: int | None) -> AcquisitionJob | None:
        from app.core import acquisition_worker

        targets = [b for b in self.books.get_many(book_ids) if not b.downloaded]
        if not targets:
            return None
        for book in targets:
            book.status = "queued"
            book.error = ""
        job = AcquisitionJob(
            source=SOURCE,
            job_type="download",
            status="queued",
            stage="Queued",
            total=len(targets),
            payload=json.dumps([b.id for b in targets]),
            created_by=user_id,
        )
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    def download_all(self, user_id: int | None) -> AcquisitionJob | None:
        return self.queue_downloads([b.id for b in self.books.all_missing()], user_id)

    def retry(self, book_id: int, user_id: int | None) -> AcquisitionJob | None:
        book = self.books.get(book_id)
        if not book:
            return None
        book.status = "available"
        book.error = ""
        self.books.save()
        return self.queue_downloads([book_id], user_id)

    def delete_download(self, book: NcertBook) -> None:
        if book.file_path:
            path = Path(book.file_path)
            if path.exists():
                path.unlink()
        book.downloaded = False
        book.downloaded_at = None
        book.status = "available"
        book.file_path = ""
        book.file_size = 0
        book.checksum = ""
        book.version_hash = ""
        book.error = ""
        self.books.save()

    # ---------- worker-run logic ----------

    def run_scan(self, job: AcquisitionJob) -> None:
        job.status = "scanning"
        job.stage = "Scanning NCERT website"
        job.progress = 5
        self.jobs.save()

        scanned = NcertScraper.scan()
        job.total = len(scanned)
        self.jobs.save()

        new_count = 0
        for i, sb in enumerate(scanned):
            existing = self.books.get_by_code(sb.book_code)
            if existing is None:
                self.db.add(
                    NcertBook(
                        book_code=sb.book_code,
                        class_level=sb.class_level,
                        class_label=sb.class_label,
                        subject=sb.subject,
                        title=sb.title,
                        part=sb.part,
                        language=sb.language,
                        url=sb.url,
                        status="available",
                        last_checked=_now(),
                    )
                )
                new_count += 1
            else:
                existing.class_level = sb.class_level
                existing.class_label = sb.class_label
                existing.subject = sb.subject
                existing.title = sb.title
                existing.part = sb.part
                existing.language = sb.language
                existing.url = sb.url
                existing.last_checked = _now()
            if i % 25 == 0:
                job.processed = i
                job.progress = 5 + int(90 * (i + 1) / max(1, len(scanned)))
                self.jobs.save()

        job.processed = len(scanned)
        job.progress = 100
        job.status = "completed"
        job.stage = "Completed"
        self.jobs.save()
        notification_service.push(
            self.db, "success", "Scan complete",
            f"{len(scanned)} books found ({new_count} new).", SOURCE,
        )

    def run_download(self, job: AcquisitionJob) -> None:
        job.status = "downloading"
        job.stage = "Downloading books"
        self.jobs.save()

        book_ids: list[int] = json.loads(job.payload or "[]")
        books = [b for b in (self.books.get(bid) for bid in book_ids) if b]
        for book in books:
            book.status = "downloading"
        self.books.save()

        def fetch(book: NcertBook):
            dest = settings.ncert_dir / f"class{book.class_level}" / f"{book.book_code}.zip"
            return book, NcertDownloader.download(book.url, dest)

        done = 0
        failures = 0
        workers = max(1, settings.ncert_concurrent_downloads)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch, b): b for b in books}
            for future in as_completed(futures):
                book = futures[future]
                try:
                    _, result = future.result()
                    book.downloaded = True
                    book.downloaded_at = _now()
                    book.status = "downloaded"
                    book.file_path = result.file_path
                    book.file_size = result.file_size
                    book.checksum = result.checksum
                    book.version_hash = result.version_hash
                    book.last_checked = _now()
                    book.error = ""
                    notification_service.push(
                        self.db, "success", "Book downloaded", book.title, SOURCE
                    )
                except Exception as exc:  # noqa: BLE001
                    failures += 1
                    book.status = "failed"
                    book.error = str(exc)
                    notification_service.push(
                        self.db, "error", "Download failed", f"{book.title}: {exc}", SOURCE
                    )
                done += 1
                job.processed = done
                job.progress = int(100 * done / max(1, len(books)))
                self.books.save()
                self.jobs.save()

        job.status = "completed" if failures < len(books) else "failed"
        job.stage = "Completed" if failures == 0 else f"Completed with {failures} failures"
        job.progress = 100
        self.jobs.save()

    def run_refresh(self, job: AcquisitionJob) -> None:
        job.status = "scanning"
        job.stage = "Checking for updates"
        self.jobs.save()

        downloaded = self.books.downloaded_books()
        job.total = len(downloaded)
        updates = 0
        for i, book in enumerate(downloaded):
            signature = NcertDownloader.remote_signature(book.url)
            book.last_checked = _now()
            if signature and book.version_hash and signature != book.version_hash:
                book.status = "update_available"
                updates += 1
            job.processed = i + 1
            job.progress = int(100 * (i + 1) / max(1, len(downloaded)))
            self.books.save()
            self.jobs.save()

        job.status = "completed"
        job.stage = "Completed"
        job.progress = 100
        self.jobs.save()
        if updates:
            notification_service.push(
                self.db, "warning", "Updates available",
                f"{updates} downloaded book(s) changed on the website.", SOURCE,
            )
