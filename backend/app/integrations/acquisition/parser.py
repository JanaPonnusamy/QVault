"""Parser contract (Phase 2A ships the contract only — no concrete parser).

A parser never knows which provider produced a document — it only sees an
`AcquisitionDocument` (with `local_file` populated by `fetch()`) and returns a
`ParsedDocument`. This is the seam later phases build on: the Question
Splitter, Answer Parser and Solution Parser are all `DocumentParser`
implementations (or consumers of one), never provider-aware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.integrations.acquisition.dto import AcquisitionDocument


@dataclass
class ParsedDocument:
    source: AcquisitionDocument
    text: str = ""
    elements: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class DocumentParser(Protocol):
    def parse(self, document: AcquisitionDocument) -> ParsedDocument: ...
