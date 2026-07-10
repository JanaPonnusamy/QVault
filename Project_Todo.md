# QVault — Project Todo

Three sections only. Tasks move **BACKLOG → IN PROGRESS → COMPLETED** as each
sprint finishes. Keep this file accurate after every sprint (see CLAUDE.md rule 20).

---

## BACKLOG

- PDF acquisition source (reuse `acquisition_jobs` + acquisition worker)
- Image acquisition source (reuse `acquisition_jobs` + acquisition worker)
- OCR fallback for documents flagged `needs_ocr` (image-only PDFs)
- Question extraction from extracted document structure (structured text → questions)
- Question Bank module
- Question Validation module
- Question Classification module
- Syllabus Management module
- Knowledge Graph module
- Search & Answering (embeddings + vector store; evaluate Postgres + pgvector)
- NCERT enhancements: cover thumbnails, per-chapter download, job cancellation
- Hardening: durable job queue, JWT refresh tokens, audit logs, system metrics
- User Portal (student modules)
- Knowledge Research refactor onto house architecture: port raw-sqlite3 repository to SQLAlchemy (SQL Server support), route background work through the acquisition worker, merge duplicate yt-dlp/OCR wrappers into `integrations/`, PDF/audio/image/website extractors, more LLM providers

## IN PROGRESS

- _(none)_

## COMPLETED

### Knowledge Research Engine (v0.9.0)
- New `research` module: AI research from a single YouTube URL (Mode A) or topic → top-N videos (Mode B) — extraction (Whisper transcript + subtitles + frame OCR) → LLM analysis (structured JSON: facts/entities/timeline/recommendations/warnings) → cross-source consensus → JSON + Markdown report
- **Copied verbatim from the NexusYTSync implementation and wired into QVault per explicit instruction (copy + wire, no redesign)** — wiring-only changes: router prefix `/api/research` (existing knowledge module owns `/api/knowledge`), `require_permission` guards + `research` RBAC module seeded, `database_manager.py` shim → `qvault.db`, frontend api client → QVault's authenticated axios, module registered in `modules.ts` + routes in `App.tsx`, Tailwind v3 utilities-only (preflight off, module-scoped content globs) so Bootstrap pages are untouched
- Provider-abstracted LLM layer (`llm_service.py` registry; OpenAI-compatible provider serving OpenRouter, retry + JSON mode + token/cost/latency metadata) and source-search layer (YouTube `ytsearchN:`); versioned prompts; every LLM call recorded in `knowledge_ai_runs`
- 6 new tables (`knowledge_sessions/documents/facts/entities/consensus/ai_runs`); large text on disk under `storage/knowledge/<session>/`, DB stores paths only; media deleted after extraction
- Verified live inside QVault: RBAC login → Mode A session on a real YouTube URL → COMPLETED 100% with facts/entities/ai-run rows + report.json/report.md; frontend builds clean; vite proxy → :8004 verified
- Known deviations (accepted, backlogged): raw-sqlite3 repository (SQLite only), own thread-pool executor, duplicate yt-dlp/OCR wrappers alongside `integrations/`

### Maintenance — Frame Extraction Engine: Strategy Pattern + Frame Sampling Mode (v0.8.0)
- Replaced the old fixed-~2s-interval-only frame extraction (missed brief slides/questions/flash content) with a configurable engine: `Video → Frame Sampling → Strategy → shared quality filters → OCR → Classification → Question Extraction` — **zero changes downstream of extraction** (OCR/analysis/classification/questions all reuse the same `Frame` rows unchanged)
- `services/frame_extraction_service.py`: `FrameExtractionService` facade (single call site in `core/worker.py`, replacing direct `FFmpeg.extract_frames`) + Strategy Pattern — `FixedIntervalStrategy` (0.25/0.5/1/2/5s, user-selectable), `SceneDetectionStrategy` (ffmpeg scene-select filter, opening frame always prepended), `OCRTextChangeStrategy` (Save/Skip via OCR text-diff against the last kept frame), `HybridStrategy` (**default**: scene detection + OCR text-diff + shared filters; fixed to never collapse two textless frames as "duplicates," so scene-detected camera cuts/diagram swaps with no OCR text survive)
- Shared quality filters (apply to every strategy): remove duplicate frames + keep-highest-quality (pixel-signature MAD grouping + Laplacian-variance sharpness), ignore blank frames (pixel-stddev), ignore blurred frames, Maximum Frames (Auto/25/50/100/200/Unlimited)
- **Frame Sampling Mode** (Advanced): every decoded frame / 30 / 15 / 10 (default) / 5 / 2 / 1 FPS — controls how many candidates are *examined*; the strategy decides which are *kept*. Wired into Scene Detection, OCR Text Change and Hybrid (Fixed Interval keeps its own dedicated interval control)
- Fixed a latent ffmpeg bug found via testing: the image2 muxer errors on zero selected frames ("received no packets") — now treated as a valid empty result instead of crashing (affects any video with no scene changes, or a very short/static clip)
- Pre-processing frame-count estimate: `ExtractionService.estimate_frames`, `POST /api/extractor/estimate` + `POST /api/sources/instagram/estimate` (metadata-only probe, no download); shown live (debounced) in the Advanced UI
- `extraction_strategy`/`extraction_options` (JSON) columns on `extraction_jobs` (additive SQLite migration; `create_all` on SQL Server); `JobCreate`/`JobOut` extended
- `components/ExtractionStrategySelector.tsx` (strategy radios, Frame Sampling Mode + estimate + Maximum Frames + 4 quality checkboxes under Advanced) wired into both `YouTubeExtractor.tsx` and `InstagramAcquisition.tsx`
- Tests: 66 new (103 total) using real synthetic ffmpeg-generated local MP4s (not mocked) — reproduces the original bug exactly (10s video → 5 frames at the old interval) and its fix; scene-boundary detection; OCR Save/Skip matches the spec's worked example; a full worker end-to-end test drives a real local MP4 through the actual `core.worker._run_job` against the real DB for all 4 strategies; flash-frame detection reproduces the exact 33ms-flash scenario (10 FPS misses it, every-decoded-frame catches it)
- Live-verified end-to-end against a real 213s YouTube video (download → Hybrid @ 10 FPS → 33 frames → ready) through the actual running app + Vite proxy; estimate endpoints verified live against real YouTube metadata
- **Not yet committed** — implementation complete and verified; awaiting the user's manual sign-off before commit (per explicit instruction)

### Phase 3 — Instagram Acquisition Module (v0.7.0)
- Reused the existing video pipeline (`extraction_jobs`/`frames`/`questions`, extraction worker, `ExtractionService`/`AnalysisService`, FFmpeg frame extraction, RapidOCR) — **no new tables, no duplicated pipeline**
- Added a `source` discriminator + Instagram metadata columns (`caption`, `author`, `upload_date`, `thumbnail_url`, `source_meta`) to `extraction_jobs`; `classification` to `frames` (additive SQLite migration; `create_all` on SQL Server)
- Generic `yt-dlp` downloader now returns caption/author/upload_date/thumbnail/meta (Instagram Reels & Posts supported natively); worker persists them and runs a classification stage for Instagram jobs
- Deterministic content classifier (`ClassificationService`, no AI): OCRs every unique frame and tags Heading/Paragraph/Question/Options/Answer/Diagram/Table
- Thin `instagram` router (`/api/sources/instagram/*`) delegating to shared services + source isolation; `instagram` RBAC module seeded
- Instagram Acquisition page (stats, URL submit, progress stages, frame+classification gallery, auto/manual OCR, inline question review, JSON/CSV/SQLite export) reusing `JobProgress`/`ConfidenceBadge`/`StatusBadge`
- YouTube job list filtered to its own source (no cross-leak); existing YouTube module behaviour unchanged
- Tests: classifier + source-isolation + classification-service + routing/RBAC wiring (16 passing)

### Platform Phase 1 — SQL Server + Content Assembly + Knowledge Reader (v0.6.0)
- Analyzed Nexora reference backend; **no platform code copied** (raw pyodbc/no-JWT/tenant-coupled — below QVault's stack); reused only SQL Server connection + schema conventions
- SQL Server migration: dialect-aware settings/engine/init_db, `db_backend`/`mssql_*` config, `scripts/init_sqlserver.py`; **live-verified** on SQL Server 2014 (DB created, 16 tables, auth/RBAC + stats working); SQLite default kept (non-breaking)
- Dialect fixes: knowledge_nodes self-FK no-cascade; boolean filters `== True/False`
- Existing Auth/Users/Roles/Permissions reused unchanged on SQL Server (no downgrade)
- Content Assembly Engine: `content_sections`/`content_blocks`, deterministic reconstruction (merge paragraphs, drop headers/footers/page numbers, captions↔figures, examples/exercises, reading order, sections); **raw extraction preserved**; auto-runs after extraction; `/api/content/*`
- Knowledge Reader: DocumentViewer Reader (assembled, default) vs Developer (raw nodes) toggle; `content` RBAC module
- Docs/config updated (`config/.env.example` SQL Server keys)

### Maintenance — Release Automation adapted for QVault (v0.5.0)
- Reused the bundled `automation/` (NDF) framework — not recreated
- Root `ndf.config.toml` override: name=QVault, URL=github.com/JanaPonnusamy/QVault, version 0.5.0, commit groups, module registry
- Comprehensive root `.gitignore` (ignores generated/media/runtime; tracks all source types)
- One command `python -m automation ship`: version → docs → add → commit → push → verify → display hash/version/URL
- Fixed latent `git status --porcelain` parse bug in the git provider; genericized NEXORA branding in committed artifacts
- Git initialized (`main`); remote `origin` = QVault; pushed `main` (verified) + tag `v0.5.0`

### Sprint 6 — Knowledge Mapping Engine (v0.5.0)
- Generic hierarchical `knowledge_nodes` table (parent-child, depth, order, materialized path, element provenance)
- Deterministic tree mapping (no AI): headings → sections, paragraphs/tables/figures → leaves; bookmark + flat fallback strategies
- Parent-child relationships preserved; auto-maps after document extraction (reuses extraction pipeline)
- Reusable navigation APIs (tree, node detail + breadcrumb, children) + content/title search
- Knowledge Explorer in Admin Portal (document selector, expandable tree, node detail, search, remap)
- `knowledge` module + RBAC permissions (`knowledge:view/execute`)

### Sprint 4 — Knowledge Extraction Engine (v0.4.0)
- Generic document tables (`documents`, `document_elements`, `document_bookmarks`) reusable by every source
- Deterministic PyMuPDF extractor (no AI): PDF text-layer detection before OCR consideration
- Extract & store document structure: headings (font-size levels), paragraphs, tables (cells), figures, bookmarks
- Ingestion: PDF upload + import-from-NCERT (unzip acquired book → per-PDF documents)
- Reused `acquisition_jobs` + acquisition worker (`document_extract`) + notifications
- Document structure viewer in Admin Portal (bookmarks outline + typed element rendering, filters)
- Documents module + RBAC permissions (`documents:view/execute/delete`)

### Sprint 1 — Foundation & YouTube Extractor (v0.1.0)
- Admin Portal shell (sidebar, top nav, breadcrumb, search, module registry)
- Authentication (JWT, bcrypt)
- RBAC (module-based permissions, Users & Roles management, seeding)
- YouTube acquisition (yt-dlp) + FFmpeg frame extraction + frame gallery
- Manual OCR workflow (RapidOCR) → questions
- JSON export

### Sprint 2 — Automatic Question Extraction (v0.2.0)
- Question frame detection engine (image analysis: MSER + background uniformity + saturation)
- Frame deduplication (MAD signature)
- Automatic OCR pipeline (auto-OCR detected question frames)
- Question merge engine (consecutive related frames → one question)
- Question confidence (OCR / Frame / Merge / Overall)
- Review queue UI (edit, options, approve, reject, delete)
- Export improvements (JSON, CSV, SQLite)

### Sprint 3 — NCERT Acquisition Agent (v0.3.0)
- Generic Acquisition Jobs table + acquisition worker (scan/download/refresh)
- NCERT website scanner (textbook.php parser, ~835 books)
- NCERT book registry/catalog
- Download selected / Download all (skip existing, no duplicates)
- Version check / update detection (no auto-overwrite)
- Checksum + storage layout (`storage/ncert/class<N>/<code>.zip`)
- Notification system (bell, unread badge; scan/download/update events)
- NCERT REST API + frontend page (filters, search, pagination, queue)
- Sidebar "Sources" group (YouTube, NCERT live; PDF/Images coming soon)
