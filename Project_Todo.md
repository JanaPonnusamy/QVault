# QVault — Project Todo

Three sections only. Tasks move **BACKLOG → IN PROGRESS → COMPLETED** as each
sprint finishes. Keep this file accurate after every sprint (see CLAUDE.md rule 20).

---

## BACKLOG

- Run the real official NEET syllabus import (`POST /api/catalog/import`) once
  the NTA syllabus PDF is supplied; tune `NEET_CONFIG` regex patterns against
  its actual wording if needed
- Syllabus Catalog admin UI (frontend page over `/api/catalog/*`)
- PDF acquisition source (reuse `acquisition_jobs` + acquisition worker)
- Image acquisition source (reuse `acquisition_jobs` + acquisition worker)
- OCR fallback for documents flagged `needs_ocr` (image-only PDFs)
- Question Acquisition & Extraction Engine — Phase 2B+, on top of the Phase-2A framework (v0.12.0), the GK Scraper website provider (v0.13.0) and Phase-1 Question Repository (v0.11.0):
  - GK Scraper: multi-site rotation (register several homepages) + a daily scheduler for incremental re-crawl (the `AcquisitionItem` idempotent-by-`(provider, source_id)` design already supports this — "re-run discover(), only new/changed items move" — no schema change needed, just a scheduler)
  - GK Scraper: more `KNOWN_PLUGINS` fingerprints as real GK sites are inspected (only GKToday's `wp-quiz-basic` has a deterministic parser today; others use the slower/costlier AI fallback)
  - GK Scraper: PDF-derived MCQ/essay generation (PDFs found during a scan are currently only queued into the Documents pipeline, not further mined into questions)
  - other providers on the same framework: NCERT (reusing `integrations/ncert_scraper.py`/`ncert_downloader.py`), NTA PDFs, generic PDF/GitHub/YouTube/Archive.org
  - a concrete `DocumentParser` for PDFs (likely reusing `integrations/pdf_extractor.py`'s deterministic extraction), then deterministic question splitter + answer-key importer (AI fallback only on parse failure)
  - solution/explanation extractor (official/coaching/ai_generated/community/video, kept separate per `bank_question_solutions.source_type`)
  - semantic topic-mapping fallback when deterministic matching fails (populates `bank_questions.keywords`)
  - image/figure downloader into `bank_question_images` (compute `sha256_hash`/`phash`)
  - richer duplicate detection (option similarity, image hash, cross-year) on top of the existing normalized-text hash
  - review & validation UI for low-confidence/duplicate/missing-answer questions (surface `bank_question_lineage`; GK Scraper already flags AI-assisted extractions as `pending_review`)
- Question Validation module
- Question Classification module
- Knowledge Graph module
- Search & Answering (embeddings + vector store; evaluate Postgres + pgvector)
- NCERT enhancements: cover thumbnails, per-chapter download, job cancellation
- Hardening: durable job queue, JWT refresh tokens, audit logs, system metrics
- User Portal (student modules)
- Knowledge Research refactor onto house architecture: port raw-sqlite3 repository to SQLAlchemy (SQL Server support), route background work through the acquisition worker, merge duplicate yt-dlp/OCR wrappers into `integrations/`, PDF/audio/image/website extractors, more LLM providers

## IN PROGRESS

- _(none)_

## COMPLETED (pending doc sync)

### Maintenance - Knowledge Research SQL unification + startup lock fix (v0.14.x)
- Replaced the Knowledge Research module's raw `sqlite3` repository with a SQLAlchemy repository on the shared main database, so research sessions/documents/facts/entities/consensus/ai-run rows now use the same configured backend as the rest of QVault instead of bypassing it through `database/qvault.db`
- Removed the startup-time SQLite schema write that was happening during router import: the Research router now lazy-creates its shared service singleton, so app boot no longer depends on side-effecting DB work before `init_db()` completes
- Updated the one-click launcher to stop forcing `QVAULT_DB_BACKEND=sqlite`; it now honors the configured backend from `config/.env`, and SQL Server connection settings now emit `Encrypt=no` by default unless encryption is explicitly enabled
- Verified on an isolated temporary database path: backend import succeeds, `tests/test_auth_login.py` passes (`7 passed`), and frontend `npm.cmd run build` passes; live SQL Server verification remains dependent on the configured server at `192.168.10.73` being reachable from this machine

### Maintenance - launcher stability follow-up (v0.14.x)
- Updated the one-click Windows launcher to `call` its generated helper `.cmd` files explicitly, and the frontend helper now `call`s `npm.cmd` instead of invoking it bare
- This keeps the frontend Vite dev server alive reliably in the spawned terminal window instead of intermittently dropping out and leaving the login screen stuck on network/500 errors after startup
- Re-verified the live local path after relaunch: frontend `http://127.0.0.1:5174/` returned `200`, backend `http://127.0.0.1:8005/api/system/branding` returned `200`, and the real `admin/admin123` form login against `/api/auth/login` returned `200`

### Maintenance - local launcher repair (v0.14.x)
- Rewrote `launch_qvault.bat` so the backend/frontend launch commands are emitted into temporary helper `.cmd` files first instead of relying on fragile nested `cmd /k` quoting
- Fixed the launcher's Python detection bug: absolute virtualenv paths are now validated correctly instead of being incorrectly passed through `where`
- Kept the proper local ports (`127.0.0.1:8005` backend, `127.0.0.1:5174` frontend) and kept the backend CORS override aligned with the frontend dev URL
- One-click launch now defaults to the SQLite dev database for reliable local startup even when `config/.env` is pointed at an unavailable SQL Server; verified live with `GET /api/system/branding` on `8005` and the Vite dev server on `5174` both returning `200`

### Maintenance - dev-console/runtime cleanup (v0.14.x)
- Fixed the Knowledge page's mapped-documents query to be SQL Server-safe by aggregating `knowledge_nodes` in a subquery before joining back to `documents`, eliminating the `GROUP BY` `500` on `/api/knowledge/documents`
- Opted `BrowserRouter` into the React Router v7 future flags (`v7_startTransition`, `v7_relativeSplatPath`) so the repeated dev-console warnings disappear during local development
- Added an inline SVG favicon in `frontend/index.html` so the browser stops requesting a missing `/favicon.ico`
- Re-verified the live dev app after restart: `/api/auth/login`, `/api/system/branding`, `/api/knowledge/stats`, and `/api/knowledge/documents` all returned successfully; frontend `npm.cmd run build` passes

### Maintenance - local launch ports + one-click launcher (v0.14.x)
- Moved QVault's local dev ports off the machine's already-occupied app ports: backend default changed from 8004 to 8005, frontend Vite dev server from 5173 to 5174, and backend CORS/dev proxy values were kept in sync
- Updated both the committed template (config/.env.example) and the local runtime override (config/.env) so the default launch path and the checked-in documentation agree
- Added root launch_qvault.bat to open separate backend/frontend terminal windows with one click (uvicorn on 127.0.0.1:8005, Vite on 127.0.0.1:5174)
- Updated AGENTS.md run instructions so future sessions pick up the new non-conflicting ports immediately

### Knowledge Intake â€” Education Knowledge Acquisition (v0.14.0)
- New `/education` admin module + `education_acquisition` RBAC, built on the shared acquisition framework (`acquisition_jobs` + `AcquisitionItem`) rather than a parallel scraper
- Configurable public-web discovery providers: Google/Bing/DuckDuckGo queries, manual URLs, sitemap, same-domain crawl, RSS, government portals, PDF discovery, and generic document discovery; no auth/CAPTCHA bypass
- Deterministic HTML/PDF/DOCX/image/XML/TXT parsing into normalized `education_sources` / `education_documents` / `education_fields` / `education_tags` data, with canonical field normalization for school/ERP-style forms
- Downloadable exports added: JSON, CSV, Markdown, and SQLite under `storage/education/exports/`; frontend dashboard page includes scan configuration, job polling, document inspection, and export actions
- Added a standard school-admission field blueprint split into Enquiry vs Application stages; document detail now shows required-field coverage, custom school-specific fields, and preserved metadata so later custom-field configuration can be layered on without losing extracted input
- Added tenant/business branding configuration foundation: public branding API + `config/branding.json` + frontend branding provider/CSS variables, so app name, logo, fonts, accent/sidebar colors, login background, and module colors are configurable per tenant/business instead of hardcoded
- Verified on the SQLite path: backend imports cleanly (`QVAULT_DB_BACKEND=sqlite`), frontend `npm.cmd run build` passes, focused backend tests (`tests/test_education_acquisition.py`) pass

### Maintenance — GK Scraper: full-site single-run scrape + solution-gap fix (v0.13.x)
- Removed the `gk_scraper_batch_size` (200-page) cap that forced repeated "Start Scan" clicks — one run now fetches/parses every discovered page in the pool (`gk_scraper_pool_size`, 5000); `AcquisitionItem`'s idempotent discovered/retry state still makes a re-run cheap (only new/failed pages)
- Root-caused why some scraped MCQs had no solution: `gk_http.post_form` (used to replay the `wp_basic_quiz` plugin's AJAX "reveal answer" call) sent no `Referer`/`X-Requested-With` header, so some quiz-plugin/WAF combinations silently returned no usable answer data; added those headers + a one-shot retry
- Any MCQ/fill-blank saved without both a correct answer and a solution is now flagged `pending_review` (previously silently saved as `draft`, hiding the gap) — surfaces in the existing Question Bank review queue instead of masquerading as complete; profile.md now reports a "saved without a full answer+solution" count per scan
- New `/api/sources/gk-scraper/profiles/{domain}/urls` (paginated, filterable by status) reusing the existing `AcquisitionItem` table as the scraped/visited-URL ledger — no new table (already had provider/source_url/status/document_type/error/timestamps, one row per (provider, source_id)); new "Scraped & Visited URLs" table on the GK Scraper admin page
- Backend imports cleanly (136 routes); frontend `tsc && vite build` clean

## COMPLETED

### Question Engine Phase 2A — GK Scraper, first concrete provider (v0.13.0)
- First real implementation of the Phase 2A framework (v0.12.0): given only a homepage URL, discovers pages (sitemap.xml/sitemap_index.xml first, robots.txt-respecting same-domain crawl fallback — `integrations/gk_site_analyzer.py`), classifies each deterministically as mcq/essay/fill_blank/pdf (`KNOWN_PLUGINS` fingerprint registry + generic heuristics), and extracts structured content (`integrations/gk_extractors.py`)
- Deterministic-first, AI-fallback-only: GKToday's live `wp-quiz-basic` plugin was reverse-engineered — it renders question/options in static HTML but hides the correct answer behind a hidden AJAX submit call, which the parser now simulates to recover the real answer/explanation. Any page that doesn't match a known plugin/pattern falls back to the existing provider-abstracted `LLMService` to structure the content — never to invent it. Two scope decisions taken with the user up front: Phase 1 is one homepage per run (no daily scheduler yet), and AI is a fallback only, never the default
- `integrations/acquisition/providers/gk_website.py` (`GkWebsiteProvider`) + `gk_website_parser.py` (`GkWebsiteParser`) are the first concrete classes against the Phase 2A `AcquisitionProvider`/`DocumentParser` contracts; `services/gk_scraper_service.py` orchestrates discover → `AcquisitionQueueService` (idempotent `AcquisitionItem` state) → fetch → parse → save
- Writes into the existing Question Bank (`exam="General Knowledge"`, **no schema change** — reused `BankSource`/`BankQuestion` exactly as designed for this in Phase 1) instead of a new "source master" table, since one already existed; PDFs found during a scan are routed into the existing Documents extraction pipeline via a new `KnowledgeService.ingest_external()` (no second PDF pipeline)
- New `job_type="gk_website_scrape"` on the existing acquisition worker (no new worker); `/api/sources/gk-scraper/*` API (`scan`/`jobs`/`profiles`) + `gk_scraper` RBAC module (view/execute); `GkScraper` admin page (homepage URL + Start Scan, job progress via the reused `JobProgress`, markdown site-profile viewer)
- New dependency: `beautifulsoup4` (generic HTML parsing/link discovery — the existing regex-only NCERT parser doesn't generalize to arbitrary unknown sites)
- Live-verified end-to-end via `TestClient` against the **real** gktoday.in (not mocked): sitemap discovery found 40 real pages; 10 MCQ pages correctly parsed via the deterministic plugin path with real recovered answers/explanations (spot-checked correct); 29 essay pages; 1 transient fetch error; 128 real questions written to the Question Bank; `profile.md` generated per site and served over the API; `AcquisitionItem` rows correctly tracked through the full `discovered→downloading→downloaded→parsed→completed` state machine
- Found and fixed a real bug during the live run: provider name (`gk:<domain>`) and raw-URL source_id both contained `:`/`/`, which are invalid in Windows file paths (`AcquisitionStorage` uses them as path segments) — fixed to `gk_<domain>` + a SHA-256 source_id
- Backend imports cleanly (139 routes); frontend `tsc && vite build` clean. All test data (questions, sources, acquisition items/jobs, notifications, storage files) removed from the dev DB/disk after verification — confirmed empty afterward

### Question Engine Phase 2A — Question Acquisition Framework (v0.12.0)
- Settled the provider interface, common DTO, queue state machine and parser contract before writing any crawler — see [docs/adr/0001-question-acquisition-framework.md](docs/adr/0001-question-acquisition-framework.md)
- `integrations/acquisition/dto.py`: `AcquisitionDocument` (provider/source_id/source_url/document_type/language/checksum/metadata/local_file/discovered_at, `validate()`/`is_valid`) and `JobSpec` (plain job_type/source/payload — never an ORM object, keeps `integrations/` DB-free)
- `integrations/acquisition/provider.py`: `AcquisitionProvider` ABC (`discover`/`fetch`/`validate`/`extract_metadata`/`create_job`/`health`) + `register`/`get_provider`/`list_providers` registry — mirrors the existing `video_providers.py` dependency-injection pattern; a new provider is one class + one `register()` call, no other file changes
- `integrations/acquisition/parser.py`: `DocumentParser` Protocol + `ParsedDocument` — contract only, **no concrete parser yet**
- `integrations/acquisition/storage.py`: `AcquisitionStorage` — deterministic `storage/acquisition/<provider>/<exam>/<year>/<source_id>/original_file`+`metadata.json`, download-only
- New generic `acquisition.acquisition_items` table (`AcquisitionItem`, schema-qualified like `catalog`/`question`): discovered→downloading→downloaded→parsed→completed state machine, unique `(provider, source_id)` for idempotent re-discovery, retry (`mark_failed` queues a retry until `max_retries`, then fails permanently), checkpoint recovery (`recover_stuck` requeues items left mid-download after a crash) — the generalized version of the existing `NcertBook` item-registry pattern, shared by every future provider instead of reinvented per-source
- `AcquisitionQueueService` is the **only** thing that writes an `AcquisitionItem` — providers never touch the database, matching the phase's "no database writes yet" scope for the provider layer
- Explicitly did **not** build (deferred to Phase 2B/2C): web crawler, OCR, question splitter, topic matcher, AI extraction, duplicate detection beyond Phase 1's existing hash check, answer extraction, solution extraction
- 29 new offline tests (`tests/test_acquisition_framework.py`) against mock providers + an isolated in-memory SQLite engine (never the real dev DB): DTO validation, registry/DI, checksum determinism, parser contract typing, deterministic storage paths (+ actual file/metadata.json write verified), full queue lifecycle, idempotent re-discovery, retry-to-permanent-failure, checkpoint recovery. Full backend suite 133/134 (1 pre-existing unrelated failure — a video frame-extraction test out of sync with concurrent work already in this working tree)
- No new router/UI/RBAC module — framework only, nothing user-facing yet

### Question Engine Phase 1 — Question Repository (v0.11.0)
- New `question.bank_sources` (never overwritten — `first_seen`/`last_seen`/`crawl_count`/`checksum` accumulate acquisition history across re-crawls), `question.bank_questions` (GUID-keyed exam question bank: exam/year/session/shift, normalized-text SHA-256 dedup, `current_stage`), `question.bank_question_topics` (**many-to-many** subject/unit/chapter/topic mapping + `is_primary` — never a single `topic_id` column), `question.bank_question_options`, `question.bank_question_solutions` (**one-to-many** — official/coaching/ai_generated/community/video solutions coexist), `question.bank_question_images` (`sha256_hash`+`phash` ready for Phase 2), `question.bank_question_lineage` (append-only acquired→ocr→parsed→human_corrected→published) — mapped directly onto the existing Syllabus Catalog (`catalog.exam/subject/unit/chapter/topic`, v0.10.0) instead of a parallel hierarchy; distinct from the frame-derived `questions` table (no collision)
- Deterministic normalized-text SHA-256 duplicate detection; no AI — later-phase layer on top. Every create/edit/status-change auto-logs a `bank_question_lineage` row and updates `current_stage`
- `/api/question-bank/*` full CRUD + stats + sources + lineage + approve/reject; `question_bank` RBAC module seeded
- `QuestionBank` admin page (stats, cascading Exam→Subject→Unit→Chapter→Topic filters + picker reading `/api/catalog/*`, paginated list, add/edit modal with dynamic MCQ/MSQ options + multi-topic-mapping UI with a primary marker, approve/reject, duplicate badge); flipped from placeholder to live in `modules.ts`
- Verified end-to-end over HTTP against seeded catalog rows: create with topic mapping + options + solution + source → dedup (punctuation/whitespace-only diff correctly flagged `duplicate_score=1.0`) → repeat-source crawl incremented `crawl_count` instead of duplicating the source → filter by `topic_id` (join through the junction table) → edit → `current_stage=human_corrected` → approve → `current_stage=published`; lineage `[acquired, human_corrected, published]` and stats all correct. Backend 136 routes; frontend `tsc && vite build` clean
- **Course correction mid-session:** first built on a stale `main` checkout, duplicating the syllabus hierarchy that already existed on `develop` (the actual working branch — see Known Issues in the master doc). Caught via `git log --all` before commit; discarded and rebuilt correctly against `develop`'s `catalog.*` tables
- **Not visually verified in a browser** — no browser automation tool was available in this environment; verified via HTTP API flow + clean TS build only. Click through `/question-bank` manually before relying on the UI.
- This is Phase 1 of the Question Acquisition & Extraction Engine (repository only) — no acquisition/extraction/review-queue yet; see BACKLOG for Phase 2+

### Phase 3 (Syllabus Catalog) — Official Exam Syllabus Catalog Foundation (v0.10.0)
- Generic multi-tenant `catalog.exam/subject/unit/chapter/topic` hierarchy (GUID PKs, `TenantAuditMixin`: tenant_id/created_on/created_by/modified_on/modified_by/is_deleted) — exam-agnostic by design, no NEET-specific logic in the schema
- Idempotent SQL-Server-only startup bootstrap (`database/mssql_bootstrap.py`): `IF DB_ID(...) IS NULL CREATE DATABASE`, `IF SCHEMA_ID(...) IS NULL CREATE SCHEMA` for 7 reserved schemas (catalog/question/knowledge/media/video/acquisition/system); gated off SQLite (dev default unaffected)
- Config-driven, reusable syllabus PDF importer: `integrations/syllabus_pdf_parser.py` (deterministic PyMuPDF line extraction + regex-based `SyllabusParseConfig`, `NEET_CONFIG` default) + `services/syllabus_import_service.py` (idempotent upsert-by-code, collision-safe slugging, import log + notification) — a new exam is a new config, never a parser code change
- `/api/catalog/*` REST API (exams/subjects/units/chapters/topics/tree/import/import-logs) + `catalog` RBAC module (view/execute/delete)
- Fixed a latent named-SQL-Server-instance connection bug (`HOST\SQLEXPRESS` style servers must not have `,port` appended — `settings.mssql_server_address`)
- Live-verified against the real SQL Server instance already used by the legacy UniNex project on this machine (`DESKTOP-53U6M3S\SQLEXPRESS`, same `sa` login as `settings.py`'s existing defaults), targeting its own independent `QVault` database (never UniNex's): DB/schema/table/FK/index creation confirmed via `sys.indexes` + reflection, idempotent re-run (zero duplicate objects), full import pipeline + re-import idempotency proven with a synthetic sample PDF (created, verified, then deleted from the real DB — the actual NTA NEET PDF has not been supplied), and the full HTTP API surface (auth → RBAC → import → tree/list → 404/401) via `TestClient`
- SQLite dev-default path re-verified with no regression (29 tables, catalog/system tables unqualified there)
- Not committed — awaiting manual sign-off per explicit instruction; catalog is empty in the real database pending the real NEET PDF

### Maintenance — Knowledge Research: multi-provider LLM + UI redesign (v0.9.x)
- `PROVIDER_SPECS` registry (`knowledge_config.py`): OpenRouter (new default), OpenAI, Anthropic, Google Gemini, Ollama (local, no key required) — every provider speaks the OpenAI chat-completions protocol natively or via a compatibility base URL, so adding one is config-only, no code change
- Legacy `LLM_PROVIDER=openai` + OpenRouter-shaped `OPENAI_BASE_URL` auto-detected and treated as `openrouter` (back-compat for existing `.env` files)
- `GET /api/research/providers` returns per-provider label/configured-flag/requires_key/key_env/default_model (never the API key itself); new `GET /api/research/providers/{provider}/models` lists live models (10-min in-memory cache)
- Session create accepts `temperature`/`max_tokens`; new `POST /sessions/{id}/cancel` and `DELETE /sessions/{id}`
- Frontend redesign: `ResearchForm` rewritten (provider/model/temperature/max_tokens controls), new `HistoryDrawer` (past sessions — reopen/duplicate/delete) and `SettingsDrawer` (per-provider configured status + key env var name) replacing the old inline layout; `KnowledgeResearchPage`/`KnowledgeResearchHistoryPage` restructured around the drawers
- Verified: backend imports cleanly, frontend `tsc && vite build` clean
- Committed as `e2c2e97` on `develop` (bundled with the TTS voice-modulation maintenance change below)

### Maintenance — TTS voice modulation + Tamil Nadu voice (v0.9.x)
- Per-segment prosody (`ROLE_MODULATION` in `video_timeline_service.py`) threaded through `TTSProvider.synthesize(rate=, pitch=)`; edge/azure/google/openai apply it, elevenlabs/kokoro/piper accept-and-ignore
- Default narration voice changed to `ta-IN-PallaviNeural` (Tamil Nadu accented English, young-female tone via per-voice `base_pitch` lift in the edge provider)
- Fixed edge-tts 7.x regression: `boundary="WordBoundary"` must be requested explicitly or subtitle word-highlighting silently degrades to estimated timings
- TTS cache key now includes per-role rate/pitch
- Committed as `e2c2e97` on `develop`

### Phase X — Automated Educational Video Generation Engine
- **Deterministic rendering engine** (no AI video generation): Question JSON (`storage/**/*.json`, existing schema reused unchanged) → finished quiz videos. YouTube landscape 1920×1080 (20–25 Q, ~10–12 min) and portrait 1080×1920 Shorts/Reels (1 Q, ~20–35 s) from **one shared timeline** — only the `Layout` differs (no duplicated layouts)
- Per-question timeline exactly per spec: question card in → narration → options pop in as spoken (2 per row, glass cards, letter chips) → thinking pause → animated 3-2-1 countdown (ring + ticks in the soundtrack) → correct option green glow + pulse + check icon, others dimmed → ✅ Correct Answer card slides in → 💡 Explanation card fades in → next question; animated gradient-blob background + drifting particles (never static), progress bar with glow head, intro/outro title cards
- **Provider-abstracted TTS** (`integrations/tts/`, `TTSProvider` protocol + registry): edge (default — free, `en-IN-NeerjaNeural` Indian-English female, native word-boundary events), openai, elevenlabs, azure, google, kokoro, piper; per-segment synthesis with on-disk cache; narration is a generated speaking script (rotating leads, spoken options, reveal phrasing, sentence-trimmed explanations) — never raw JSON
- Visual event times derived from **measured** narration durations; word-highlight subtitle bar + SRT export; numpy audio mixdown (narration at exact offsets + synthesized countdown ticks + optional `assets/music` bed)
- **Streaming render**: frames piped straight into ffmpeg stdin (rawvideo → libx264 + aac) — never a full video in memory; ~90 ms/frame @1080p after profiling; renders serialized via `video_concurrent_renders` semaphore
- 6 JSON theme templates (`assets/templates/`): Glass Dark (default), Glass Blue, Classic, Light, Minimal, Kids — future templates need **no code change**; Poppins (OFL) bundled in `assets/fonts/`
- Reuses house infrastructure: `acquisition_jobs` + acquisition worker (`job_type="video_render"`), notifications, RBAC (`videos:view/execute/delete/export` seeded), SQLAlchemy `videos` registry table
- APIs: stats/sources/templates/tts-providers/generate/batch(1–100)/preview/list/jobs/download/subtitles/thumbnail/delete under `/api/videos`
- Frontend **Video Generation** module (new Studio group, `/videos`): stats dashboard, JSON source + topic selection, output kind, orientation, theme + voice selection, single + batch generation, timeline-preview modal, live generation queue, completed table (thumbnail, download MP4/SRT, delete), filters + pagination
- Verified: backend imports (101 routes), frontend builds, live API E2E (single landscape + batch shorts), rendered frames visually checked against the spec
- Committed as `41f14bd` on the new **develop** branch (pushed to origin) — all future work happens on `develop`

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

