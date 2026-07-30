"""Common DTOs for the acquisition provider framework (Phase 2A).

Every provider — NTA, NCERT, generic PDF, website, GitHub, YouTube,
Archive.org, ... — outputs exactly this shape. No provider-specific
representation is allowed to leak past `discover()`/`fetch()`: the queue,
parser and storage layers only ever see an `AcquisitionDocument`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AcquisitionDocument:
    """One candidate document discovered (and, once fetched, downloaded) by a
    provider. Providers never write this to a database — see
    `services/acquisition_queue_service.py` for the only place that persists it."""

    provider: str
    source_id: str
    source_url: str
    document_type: str  # pdf | html | image | video | ...
    language: str = ""
    checksum: str = ""
    metadata: dict = field(default_factory=dict)
    local_file: str | None = None
    discovered_at: datetime = field(default_factory=_now)

    def validate(self) -> list[str]:
        """Required-field validation. Returns a list of errors (empty = valid)
        rather than raising, since a caller enumerating many documents wants to
        skip/report bad ones without aborting the whole discover() run."""
        errors: list[str] = []
        if not self.provider:
            errors.append("provider is required")
        if not self.source_id:
            errors.append("source_id is required")
        if not self.source_url:
            errors.append("source_url is required")
        if not self.document_type:
            errors.append("document_type is required")
        return errors

    @property
    def is_valid(self) -> bool:
        return not self.validate()


@dataclass
class JobSpec:
    """What a provider wants enqueued, described as plain data — never an ORM
    object. Keeps `integrations/` free of a database dependency; the queue
    service is what turns this into a persisted `AcquisitionJob` row."""

    job_type: str
    source: str
    payload: dict = field(default_factory=dict)
