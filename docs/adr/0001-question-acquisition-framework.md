# ADR 0001: Question Acquisition Framework — Provider Interface, DTO, Queue, Parser Contract

- **Status:** Accepted
- **Date:** 2026-07-28
- **Sprint:** Question Engine Phase 2A (Acquisition Framework — no crawlers yet)
- **Supersedes:** —
- **Related:** [#21 Question Repository](../../Project_Master_Document.md) (Phase 1), [#22 Syllabus Catalog](../../Project_Master_Document.md)

## Context

Phase 1 built the Question Repository (`question.bank_questions` and friends) —
the schema every future question source writes into. Phase 2 needs to actually
*acquire* questions from many heterogeneous sources: NTA official PDFs, NCERT,
generic PDFs, arbitrary websites, GitHub question banks, YouTube, Archive.org.

Before writing a single crawler, we needed to settle four contracts that
become expensive to change once multiple providers and a parser depend on
them:

1. What every acquisition provider looks like from the outside.
2. What shape a "discovered document" has, regardless of source.
3. How a discovered document's lifecycle (download → parse → done) is
   tracked, including failure/retry/recovery.
4. What a parser receives and returns, independent of where the document
   came from.

This ADR documents the contracts implemented in Phase 2A
(`backend/app/integrations/acquisition/`, `models/acquisition.py`'s
`AcquisitionItem`, `services/acquisition_queue_service.py`). Per the phase's
explicit scope, **no concrete provider talks to a real website yet** — only
the framework and mock providers (see `tests/test_acquisition_framework.py`).

## Decision

### 1. Provider Interface

Every acquisition source implements `AcquisitionProvider`
(`integrations/acquisition/provider.py`), an ABC with six methods:

```python
class AcquisitionProvider(ABC):
    name: str

    def discover(self) -> Iterable[AcquisitionDocument]: ...
    def fetch(self, document: AcquisitionDocument) -> AcquisitionDocument: ...
    def validate(self, document: AcquisitionDocument) -> bool: ...
    def extract_metadata(self, document: AcquisitionDocument) -> dict: ...
    def create_job(self, **kwargs) -> JobSpec: ...
    def health(self) -> dict: ...
```

- `discover()` enumerates candidates **without downloading** them.
- `fetch()` downloads one document and returns a copy with `local_file`/
  `checksum` populated. Providers are pure with respect to the database —
  **no provider method writes to a database.** Persistence is the queue
  service's job (see §3).
- `validate()` is the provider's own acceptance check (e.g. "is this actually
  a PDF"), layered on top of the DTO's own required-field validation.
- `extract_metadata()` returns provider-specific facts (exam/year/shift/...);
  the caller merges these into `document.metadata`, never writing directly.
- `create_job()` returns a `JobSpec` (plain data — job_type/source/payload),
  never an ORM object. This keeps `integrations/` free of a database
  dependency, matching the existing `integrations/video_providers.py`
  precedent.
- `health()` must never raise; it returns `{"status": "ok"}` or
  `{"status": "error", "detail": "..."}`.

**Registration is dependency injection via a module-level registry**
(`register(provider)` / `get_provider(name)` / `list_providers()`), mirroring
`integrations/video_providers.py` exactly. Adding a provider is:

1. Write a class implementing `AcquisitionProvider`.
2. Call `register(MyProvider())` once, anywhere imported at startup.

No other file changes. Nothing outside a provider's own module is allowed to
branch on a provider name — the same rule the video pipeline already enforces
(`tests/test_video_providers.py::test_worker_has_no_source_string_branching`).

### 2. Common DTO

Every provider outputs exactly `AcquisitionDocument`
(`integrations/acquisition/dto.py`):

| Field | Type | Notes |
|---|---|---|
| `provider` | `str` | required |
| `source_id` | `str` | required; provider's own stable id for this document |
| `source_url` | `str` | required |
| `document_type` | `str` | required; `pdf`\|`html`\|`image`\|`video`\|... |
| `language` | `str` | optional |
| `checksum` | `str` | empty until `fetch()` |
| `metadata` | `dict` | provider-specific, opaque to the queue |
| `local_file` | `str \| None` | set by `fetch()` |
| `discovered_at` | `datetime` | defaults to now |

`validate() -> list[str]` returns errors instead of raising, because a caller
enumerating many documents wants to skip/report bad ones without aborting the
whole `discover()` run. `is_valid` is a convenience `bool` property.

No provider-specific subclassing, no per-provider extra fields — anything
provider-specific goes in `metadata` (opaque dict), so the queue, parser and
storage layers only ever depend on this one shape.

### 3. Acquisition Queue (state machine)

**Providers never write to the database.** The only thing that persists an
`AcquisitionDocument` is `AcquisitionQueueService`
(`services/acquisition_queue_service.py`), backed by a new generic,
provider-agnostic table: `AcquisitionItem` (`models/acquisition.py`,
`question`-sibling reserved schema `acquisition` on SQL Server).

States (`AcquisitionItem.status`):

```
discovered → downloading → downloaded → parsed → completed
                  \-> failed <-> retry -/
```

- **Idempotent discovery:** `enqueue_discovered()` upserts by the unique pair
  `(provider, source_id)` — re-running `discover()` (a scheduled re-crawl, a
  recovery pass) never duplicates rows, only refreshes metadata.
- **Retry:** `mark_failed(item, error)` increments `retry_count` and sets
  `status="retry"` while `retry_count < max_retries`; once exhausted, it
  becomes permanently `"failed"`. `pending()` returns `discovered` and
  `retry` items — the read path a worker loop calls instead of re-discovering
  everything.
- **Checkpoint recovery:** `recover_stuck(older_than_minutes=30)` finds items
  stuck in `"downloading"` past a threshold (a worker crashed mid-fetch) and
  requeues them as retries instead of losing them silently.
- **Why a new table instead of reusing `acquisition_jobs`:** `acquisition_jobs`
  is a *job-level* orchestration record (one row per "scan" or "download all"
  run — see NCERT). It has no concept of per-document lifecycle. The existing
  precedent for per-document state is `NcertBook` (NCERT's own item registry:
  `status`/`downloaded`/`checksum`/`error`). `AcquisitionItem` is the
  generalization of that pattern, shared by every provider instead of being
  reinvented per-source — consistent with the project's "reuse before
  building" rule, applied to the *pattern*, not a single NCERT-specific table.
- **Job orchestration is still reused, not duplicated:** `AcquisitionItem.job_id`
  optionally links an item back to an `AcquisitionJob` row. Phase 2B wires a
  new `job_type="acquire"` into the existing `core/acquisition_worker.py`
  dispatch table (today: `scan`/`download`/`refresh`/`document_extract`/
  `video_render`) — no new worker.

### 4. Parser Contract

`DocumentParser` (`integrations/acquisition/parser.py`) is a `Protocol`:

```python
class DocumentParser(Protocol):
    def parse(self, document: AcquisitionDocument) -> ParsedDocument: ...
```

`ParsedDocument` carries `source: AcquisitionDocument` plus `text`,
`elements`, `tables`, `images`, `warnings` — deliberately shaped close to the
existing `PdfExtractor`/`DocumentElement` output (Knowledge Extraction Engine,
#12) so a future concrete parser can reuse that deterministic extractor
instead of reinventing PDF structure parsing.

**A parser never knows which provider produced a document.** It receives an
`AcquisitionDocument` (with `local_file` populated) and returns a
`ParsedDocument` — nothing else. This is the seam Phase 3's Question
Splitter, Answer Parser and Solution Parser build on. **No concrete parser
ships in Phase 2A** — the contract only, exercised in tests by a trivial
`PassthroughParser`.

### 5. Storage Layer

`AcquisitionStorage` (`integrations/acquisition/storage.py`) writes exactly:

```
storage/acquisition/<provider>/<exam>/<year>/<source_id>/
    original_file
    metadata.json
```

`exam`/`year` fall back to `"unspecified"` when a provider doesn't know them
yet (e.g. discovery-time metadata is incomplete). Providers **only download
files** here — no OCR, no parsing, no question extraction happens in this
layer.

## Consequences

- **Positive:** a new provider (NTA, NCERT, GitHub, ...) is a single class +
  one `register()` call. The queue, parser and storage layers never change
  when a provider is added. Retry/recovery is handled once, centrally,
  instead of per-provider.
- **Positive:** providers stay unit-testable without a database or network —
  `discover()`/`fetch()`/`validate()` are pure functions over dataclasses.
- **Trade-off:** `AcquisitionItem` is a new table rather than extending
  `NcertBook` or `acquisition_jobs` — accepted because neither fits (see §3);
  NCERT keeps its own richer registry (cover thumbnails, class/subject facets)
  unchanged.
- **Trade-off:** `create_job()` returning a `JobSpec` (not a persisted
  `AcquisitionJob`) means every provider integration will eventually need a
  thin adapter in the queue service to turn a `JobSpec` into a real job row.
  Accepted to keep `integrations/` free of an ORM/DB dependency, matching the
  existing `video_providers.py` convention (`fetch() -> dict`, not an ORM
  object).
- **Deferred to Phase 2B/2C (explicitly out of scope here):** web crawler, OCR,
  question splitter, topic matcher, AI extraction, answer/solution extraction,
  duplicate detection beyond Phase 1's existing hash check, and wiring
  `job_type="acquire"` into `core/acquisition_worker.py`.

## Verification

29 new tests (`backend/tests/test_acquisition_framework.py`), fully offline,
run against an isolated in-memory SQLite engine (never the real dev DB):
DTO validation, provider registration/lookup/unknown-provider, dependency
injection (a locally-defined provider needs no other file change), checksum
determinism, the parser contract's structural typing, deterministic storage
paths (including the `unspecified` fallback), the full queue lifecycle
(`discovered → downloading → downloaded → parsed → completed`), idempotent
re-discovery, retry accumulation to permanent failure, and checkpoint
recovery of items stuck mid-download. Full backend suite: 133/134 passing
(the one failure is pre-existing, unrelated to this ADR — a video
frame-extraction strategy test out of sync with concurrent work already in
this working tree).
