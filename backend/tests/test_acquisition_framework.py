"""Tests for the acquisition provider framework (Phase 2A).

Deterministic and fully offline: mock providers simulate discover()/fetch()
with canned in-memory data — no network access, no real crawler. The queue
tests run against an isolated in-memory SQLite engine (never the real dev DB).
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.integrations.acquisition.dto import AcquisitionDocument, JobSpec
from app.integrations.acquisition.parser import DocumentParser, ParsedDocument
from app.integrations.acquisition.provider import AcquisitionProvider, get_provider, list_providers, register
from app.integrations.acquisition.provider import _PROVIDERS
from app.integrations.acquisition.storage import AcquisitionStorage
from app.models.acquisition import AcquisitionItem
from app.services.acquisition_queue_service import AcquisitionQueueService


# ---------- fixtures ----------

@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    db = Session()
    try:
        yield db
    finally:
        db.close()


class MockProvider(AcquisitionProvider):
    """A provider that never touches the network — canned discover()/fetch()."""

    name = "mock_provider"

    def __init__(self, doc_count: int = 2):
        self._docs = [
            AcquisitionDocument(
                provider=self.name,
                source_id=f"doc-{i}",
                source_url=f"https://example.org/doc-{i}.pdf",
                document_type="pdf",
                metadata={"exam": "NEET", "year": 2024},
            )
            for i in range(doc_count)
        ]

    def discover(self):
        return list(self._docs)

    def fetch(self, document: AcquisitionDocument) -> AcquisitionDocument:
        data = f"mock content for {document.source_id}".encode()
        checksum = hashlib.sha256(data).hexdigest()
        return replace(document, local_file=f"<mock:{document.source_id}>", checksum=checksum)

    def validate(self, document: AcquisitionDocument) -> bool:
        return document.document_type == "pdf"

    def extract_metadata(self, document: AcquisitionDocument) -> dict:
        return {"pages": 1}

    def create_job(self, **kwargs) -> JobSpec:
        return JobSpec(job_type="acquire", source=self.name, payload=kwargs)

    def health(self) -> dict:
        return {"status": "ok"}


@pytest.fixture()
def mock_provider():
    provider = MockProvider()
    register(provider)
    try:
        yield provider
    finally:
        _PROVIDERS.pop(provider.name, None)


# ---------- DTO validation ----------

def test_valid_document_has_no_errors():
    doc = AcquisitionDocument(provider="mock", source_id="1", source_url="https://x", document_type="pdf")
    assert doc.validate() == []
    assert doc.is_valid


@pytest.mark.parametrize(
    "field_name",
    ["provider", "source_id", "source_url", "document_type"],
)
def test_missing_required_field_is_invalid(field_name):
    kwargs = {
        "provider": "mock", "source_id": "1", "source_url": "https://x", "document_type": "pdf",
    }
    kwargs[field_name] = ""
    doc = AcquisitionDocument(**kwargs)
    assert not doc.is_valid
    assert any(field_name in e for e in doc.validate())


def test_discovered_at_defaults_to_now():
    before = datetime.now(timezone.utc)
    doc = AcquisitionDocument(provider="mock", source_id="1", source_url="https://x", document_type="pdf")
    assert before <= doc.discovered_at <= datetime.now(timezone.utc)


# ---------- provider protocol + registry ----------

def test_provider_conforms_to_abstract_interface(mock_provider):
    assert isinstance(mock_provider, AcquisitionProvider)
    for method in ("discover", "fetch", "validate", "extract_metadata", "create_job", "health"):
        assert hasattr(mock_provider, method)


def test_provider_registration_and_lookup(mock_provider):
    assert get_provider("mock_provider") is mock_provider
    assert "mock_provider" in list_providers()


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider("does-not-exist")


def test_adding_a_provider_requires_only_class_and_registration():
    """Dependency injection: a brand-new provider needs no other file changes."""

    class AnotherProvider(AcquisitionProvider):
        name = "another_provider"

        def discover(self):
            return []

        def fetch(self, document):
            return document

        def validate(self, document):
            return True

        def extract_metadata(self, document):
            return {}

        def create_job(self, **kwargs):
            return JobSpec(job_type="acquire", source=self.name, payload=kwargs)

        def health(self):
            return {"status": "ok"}

    provider = AnotherProvider()
    try:
        register(provider)
        assert get_provider("another_provider") is provider
    finally:
        _PROVIDERS.pop("another_provider", None)


def test_health_check_never_raises(mock_provider):
    result = mock_provider.health()
    assert result["status"] == "ok"


def test_create_job_returns_plain_data_not_orm(mock_provider):
    spec = mock_provider.create_job(foo="bar")
    assert isinstance(spec, JobSpec)
    assert spec.job_type == "acquire"
    assert spec.source == "mock_provider"
    assert spec.payload == {"foo": "bar"}


# ---------- checksum generation ----------

def test_fetch_computes_checksum_deterministically(mock_provider):
    doc = next(iter(mock_provider.discover()))
    fetched_once = mock_provider.fetch(doc)
    fetched_twice = mock_provider.fetch(doc)
    assert fetched_once.checksum == fetched_twice.checksum
    assert len(fetched_once.checksum) == 64  # sha256 hex digest


def test_different_documents_get_different_checksums(mock_provider):
    docs = list(mock_provider.discover())
    fetched = [mock_provider.fetch(d) for d in docs]
    assert len({f.checksum for f in fetched}) == len(fetched)


# ---------- parser contract ----------

def test_parsed_document_carries_its_source():
    doc = AcquisitionDocument(provider="mock", source_id="1", source_url="https://x", document_type="pdf")
    parsed = ParsedDocument(source=doc, text="hello")
    assert parsed.source is doc
    assert parsed.text == "hello"
    assert parsed.elements == []
    assert parsed.warnings == []


def test_parser_protocol_is_structural():
    class PassthroughParser:
        def parse(self, document: AcquisitionDocument) -> ParsedDocument:
            return ParsedDocument(source=document)

    assert isinstance(PassthroughParser(), DocumentParser)


# ---------- storage paths ----------

def test_storage_path_is_deterministic():
    path = AcquisitionStorage.path_for("ncert", "NEET", 2024, "book-42")
    parts = path.parts[-4:]
    assert parts == ("ncert", "NEET", "2024", "book-42")


def test_storage_path_handles_missing_exam_year():
    path = AcquisitionStorage.path_for("website", "", "", "abc")
    parts = path.parts[-4:]
    assert parts == ("website", "unspecified", "unspecified", "abc")


def test_storage_save_writes_original_file_and_metadata(tmp_path, monkeypatch):
    from app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "storage_dir", tmp_path)
    doc = AcquisitionDocument(
        provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf",
        metadata={"exam": "NEET"},
    )
    saved_path = AcquisitionStorage.save(doc, b"%PDF-1.4 test", "original.pdf", exam="NEET", year=2024)

    assert saved_path.exists()
    assert saved_path.read_bytes() == b"%PDF-1.4 test"
    metadata_path = saved_path.parent / "metadata.json"
    assert metadata_path.exists()
    assert "NEET" in metadata_path.read_text(encoding="utf-8")


# ---------- queue lifecycle ----------

def test_enqueue_discovered_creates_item(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    assert item.status == "discovered"
    assert item.provider == "mock"
    assert item.source_id == "doc-1"


def test_enqueue_discovered_rejects_invalid_document(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="", source_id="", source_url="", document_type="")
    with pytest.raises(ValueError):
        queue.enqueue_discovered(doc)


def test_enqueue_discovered_is_idempotent(session):
    """Re-running discover() must not create duplicate rows."""
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    first = queue.enqueue_discovered(doc)
    second = queue.enqueue_discovered(doc)
    assert first.id == second.id
    assert session.query(AcquisitionItem).count() == 1


def test_full_lifecycle_transitions(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)

    item = queue.mark_downloading(item)
    assert item.status == "downloading"

    item = queue.mark_downloaded(item, local_file="/tmp/doc-1.pdf", checksum="abc123")
    assert item.status == "downloaded"
    assert item.local_file == "/tmp/doc-1.pdf"
    assert item.checksum == "abc123"

    item = queue.mark_parsed(item)
    assert item.status == "parsed"

    item = queue.mark_completed(item)
    assert item.status == "completed"


def test_stats_counts_by_status(session):
    queue = AcquisitionQueueService(session)
    for i in range(3):
        doc = AcquisitionDocument(provider="mock", source_id=f"doc-{i}", source_url="https://x", document_type="pdf")
        queue.enqueue_discovered(doc)
    stats = queue.stats()
    assert stats["discovered"] == 3
    assert stats["completed"] == 0


# ---------- retry logic ----------

def test_mark_failed_queues_retry_while_retries_remain(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    item.max_retries = 3

    item = queue.mark_failed(item, "connection reset")
    assert item.status == "retry"
    assert item.retry_count == 1
    assert item.error == "connection reset"


def test_mark_failed_becomes_permanent_after_max_retries(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    item.max_retries = 2

    item = queue.mark_failed(item, "err")  # retry_count 0 -> 1, status retry
    item = queue.mark_failed(item, "err")  # retry_count 1 -> 2, status retry
    item = queue.mark_failed(item, "err")  # retry_count == max_retries -> failed permanently
    assert item.status == "failed"
    assert item.retry_count == 2


def test_retried_items_appear_in_pending(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    queue.mark_downloading(item)
    queue.mark_failed(item, "timeout")

    pending = queue.pending(provider="mock")
    assert len(pending) == 1
    assert pending[0].status == "retry"


# ---------- checkpoint recovery ----------

def test_recover_stuck_requeues_items_left_mid_flight(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    item = queue.mark_downloading(item)

    # Simulate a worker crash: the item has been "downloading" for a long time.
    item.updated_at = datetime.now(timezone.utc) - timedelta(minutes=60)
    session.commit()

    recovered = queue.recover_stuck(older_than_minutes=30)
    assert len(recovered) == 1
    assert recovered[0].status == "retry"
    assert "stuck" in recovered[0].error.lower()


def test_recover_stuck_ignores_recent_items(session):
    queue = AcquisitionQueueService(session)
    doc = AcquisitionDocument(provider="mock", source_id="doc-1", source_url="https://x", document_type="pdf")
    item = queue.enqueue_discovered(doc)
    queue.mark_downloading(item)

    recovered = queue.recover_stuck(older_than_minutes=30)
    assert recovered == []
