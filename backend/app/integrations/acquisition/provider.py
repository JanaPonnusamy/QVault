"""Provider interface every acquisition source must implement (NTA, NCERT,
generic PDF, website, GitHub, YouTube, Archive.org, ...).

No provider-specific code is allowed to leak past this boundary — the queue,
parser and storage layers only ever deal with `AcquisitionDocument`/`JobSpec`,
never a provider's internal representation. Mirrors the existing
`integrations/video_providers.py` registry pattern (`register()`/`get_provider()`)
for a source-agnostic pipeline.

Phase 2A ships the interface, registry and mock providers (for tests) only —
no concrete provider talks to a real website yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.integrations.acquisition.dto import AcquisitionDocument, JobSpec


class AcquisitionProvider(ABC):
    """One acquisition source. `name` is the discriminator persisted on
    `AcquisitionItem.provider`."""

    name: str

    @abstractmethod
    def discover(self) -> Iterable[AcquisitionDocument]:
        """Enumerate candidate documents without downloading them."""

    @abstractmethod
    def fetch(self, document: AcquisitionDocument) -> AcquisitionDocument:
        """Download `document`, returning a copy with `local_file`/`checksum` filled in."""

    @abstractmethod
    def validate(self, document: AcquisitionDocument) -> bool:
        """Provider-specific acceptance check (e.g. correct file type, non-empty
        payload), beyond the DTO's own required-field validation."""

    @abstractmethod
    def extract_metadata(self, document: AcquisitionDocument) -> dict:
        """Provider-specific metadata (exam/year/shift/...). The caller merges
        this into `document.metadata` — never written directly to a database here."""

    @abstractmethod
    def create_job(self, **kwargs) -> JobSpec:
        """Describe an acquisition run for this provider as plain data; the
        queue service is responsible for actually persisting an AcquisitionJob."""

    @abstractmethod
    def health(self) -> dict:
        """Cheap reachability/auth check, e.g. `{"status": "ok"}` or
        `{"status": "error", "detail": "..."}`. Must never raise."""


_PROVIDERS: dict[str, AcquisitionProvider] = {}


def register(provider: AcquisitionProvider) -> AcquisitionProvider:
    """Register a provider instance. Adding a new source is exactly this one
    call — no other file changes (dependency injection via a module-level registry)."""
    _PROVIDERS[provider.name] = provider
    return provider


def get_provider(name: str) -> AcquisitionProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"No acquisition provider registered for '{name}'")
    return provider


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)
