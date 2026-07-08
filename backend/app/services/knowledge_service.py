import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.integrations.pdf_extractor import PdfExtractor
from app.models.acquisition import AcquisitionJob
from app.models.document import Document, DocumentBookmark, DocumentElement
from app.repositories.acquisition_repository import AcquisitionJobRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ncert_repository import NcertRepository
from app.services import notification_service
from app.shared.logging import get_logger

logger = get_logger("knowledge")
SOURCE = "document"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _checksum(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()[:32]


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.docs = DocumentRepository(db)
        self.jobs = AcquisitionJobRepository(db)

    # ---------- ingestion (API) ----------

    def register_upload(self, original_name: str, data: bytes, user_id: int | None) -> Document:
        upload_dir = settings.documents_dir / "upload"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{uuid.uuid4().hex}.pdf"
        path.write_bytes(data)
        title = Path(original_name).stem or path.stem
        document = self._create_document(source="upload", source_ref=original_name, title=title, path=path)
        self._enqueue([document.id], user_id)
        return document

    def import_from_ncert(self, book_id: int, user_id: int | None) -> list[Document]:
        book = NcertRepository(self.db).get(book_id)
        if not book or not book.downloaded or not book.file_path:
            return []
        extract_dir = settings.documents_dir / "ncert" / book.book_code
        extract_dir.mkdir(parents=True, exist_ok=True)

        pdf_paths: list[Path] = []
        zip_path = Path(book.file_path)
        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".pdf"):
                        target = extract_dir / Path(name).name
                        target.write_bytes(zf.read(name))
                        pdf_paths.append(target)
        elif zip_path.suffix.lower() == ".pdf":
            pdf_paths.append(zip_path)

        documents = []
        for path in sorted(pdf_paths):
            documents.append(
                self._create_document(
                    source="ncert",
                    source_ref=book.book_code,
                    title=f"{book.title} — {path.stem}",
                    path=path,
                )
            )
        if documents:
            self._enqueue([d.id for d in documents], user_id)
        return documents

    def reprocess(self, document_id: int, user_id: int | None) -> Document | None:
        document = self.docs.get(document_id)
        if not document:
            return None
        self.docs.clear_structure(document_id)
        document.status = "pending"
        document.element_count = 0
        document.error = ""
        self.docs.save()
        self._enqueue([document_id], user_id)
        return document

    def delete(self, document: Document) -> None:
        from app.services.content_assembly_service import ContentAssemblyService
        from app.services.knowledge_map_service import KnowledgeMapService

        ContentAssemblyService(self.db).clear(document.id)
        KnowledgeMapService(self.db).clear(document.id)
        if document.source == "upload" and document.file_path:
            path = Path(document.file_path)
            if path.exists():
                path.unlink(missing_ok=True)
        self.docs.delete(document)

    def _create_document(self, source: str, source_ref: str, title: str, path: Path) -> Document:
        return self.docs.add(
            Document(
                source=source,
                source_ref=source_ref,
                title=title[:400],
                file_path=str(path),
                file_type="pdf",
                checksum=_checksum(path),
                status="pending",
            )
        )

    def _enqueue(self, document_ids: list[int], user_id: int | None) -> AcquisitionJob:
        from app.core import acquisition_worker

        job = AcquisitionJob(
            source=SOURCE,
            job_type="document_extract",
            status="queued",
            stage="Queued",
            total=len(document_ids),
            payload=json.dumps(document_ids),
            created_by=user_id,
        )
        self.jobs.add(job)
        acquisition_worker.submit_job(job.id)
        return job

    # ---------- worker-run extraction ----------

    def run_extraction(self, job: AcquisitionJob) -> None:
        job.status = "processing"
        job.stage = "Extracting document structure"
        self.jobs.save()

        document_ids: list[int] = json.loads(job.payload or "[]")
        done = 0
        failures = 0
        for document_id in document_ids:
            document = self.docs.get(document_id)
            if not document:
                continue
            try:
                self._extract_one(document)
                notification_service.push(
                    self.db, "success", "Document processed",
                    f"{document.title} ({document.element_count} elements)", SOURCE,
                )
            except Exception as exc:  # noqa: BLE001
                failures += 1
                document.status = "failed"
                document.error = str(exc)
                self.docs.save()
                notification_service.push(
                    self.db, "error", "Document processing failed", f"{document.title}: {exc}", SOURCE
                )
            done += 1
            job.processed = done
            job.progress = int(100 * done / max(1, len(document_ids)))
            self.jobs.save()

        job.status = "completed" if failures < len(document_ids) or not document_ids else "failed"
        job.stage = "Completed" if failures == 0 else f"Completed with {failures} failure(s)"
        job.progress = 100
        self.jobs.save()

    def _extract_one(self, document: Document) -> None:
        document.status = "processing"
        self.docs.save()
        self.docs.clear_structure(document.id)

        result = PdfExtractor.extract(document.file_path)

        elements = [
            DocumentElement(
                document_id=document.id,
                page=el.page,
                order_index=el.order_index,
                element_type=el.element_type,
                level=el.level,
                text=el.text,
                bbox=json.dumps(el.bbox),
                extra=json.dumps(el.extra) if el.extra else "",
            )
            for el in result.elements
        ]
        bookmarks = [
            DocumentBookmark(
                document_id=document.id,
                level=bm["level"],
                title=bm["title"],
                page=bm["page"],
                order_index=bm["order_index"],
            )
            for bm in result.bookmarks
        ]
        self.docs.add_elements(elements + bookmarks)

        document.page_count = result.page_count
        document.has_text_layer = result.has_text_layer
        document.needs_ocr = result.needs_ocr
        document.element_count = len(elements)
        document.status = "processed"
        document.processed_at = _now()
        document.error = ""
        self.docs.save()

        # Knowledge Mapping Engine: build the hierarchical knowledge tree.
        from app.services.knowledge_map_service import KnowledgeMapService

        KnowledgeMapService(self.db).map_document(document)

        # Content Assembly Engine: reconstruct readable content (raw kept intact).
        from app.services.content_assembly_service import ContentAssemblyService

        ContentAssemblyService(self.db).assemble(document)
