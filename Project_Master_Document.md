# QVault — Project Master Document

> Single source of truth for QVault. Maintained across every sprint.
> Read this **first**, then `Project_Todo.md`, before starting any work.

---

## Project Overview

QVault is an AI-powered **Exam Intelligence Platform** with an **Admin Portal**
(30+ modules planned) and a future **User Portal** (3–5 student modules). It
acquires content from multiple sources, extracts structured questions, and will
later make them searchable/classified/answerable. Built new; NexusYTSync
(`D:\VBDOTNET\NexusYTSync`) was a read-only reference only.

## Current Version

**v0.5.0** (Knowledge Mapping Engine complete).

## Current Sprint

Knowledge Mapping Engine — ✅ complete and verified.

## Overall Progress

| Sprint | Title | Status |
|--------|-------|--------|
| 1 | Admin Portal + Auth/RBAC + YouTube Question Extractor (manual) | ✅ Complete |
| 2 | Automatic Question Extraction (detection, dedup, OCR, merge, review, export) | ✅ Complete |
| 3 | NCERT Acquisition Agent + Notification System + generic Acquisition Jobs | ✅ Complete |
| 4 | Knowledge Extraction Engine (deterministic PDF structure extraction) | ✅ Complete |
| 6 | Knowledge Mapping Engine (hierarchical knowledge tree + Explorer) | ✅ Complete |

---

## Folder Structure

```
E:\QVault\
├── CLAUDE.md                     Permanent development rules
├── Project_Master_Document.md    This file (source of truth)
├── Project_Todo.md               Backlog / In Progress / Completed
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── app/
│       ├── main.py               Uvicorn entrypoint
│       ├── api/
│       │   ├── deps.py           Auth deps, require_permission()
│       │   ├── schemas.py        All Pydantic DTOs
│       │   └── routers/          auth, users, roles, extractor, ncert, notifications, documents, knowledge
│       ├── services/             auth, extraction, analysis, ncert, notification, knowledge, knowledge_map
│       ├── repositories/         user, rbac, extraction, ncert, acquisition, document, knowledge
│       ├── models/               rbac, extraction, acquisition, document, knowledge
│       ├── integrations/         ytdlp, ffmpeg, ocr, frame_analysis, ncert_scraper, ncert_downloader, pdf_extractor
│       ├── core/                 app (factory), seed, worker, acquisition_worker
│       ├── config/               settings
│       ├── database/             session (engine, init_db, migrations)
│       └── shared/               logging, security
├── frontend/                     React + TS + Vite + Bootstrap 5
│   └── src/
│       ├── api/client.ts         axios + auth interceptor
│       ├── auth/AuthContext.tsx  login/session/permissions
│       ├── components/           Layout, JobProgress, Modal, ConfidenceBadge
│       ├── pages/                Login, Dashboard, YouTubeExtractor, Review, Ncert, Documents, DocumentViewer, Knowledge, Users, Roles
│       ├── modules.ts            Module registry (sidebar + dashboard)
│       └── types.ts              Shared TS types
├── database/                     qvault.db (SQLite, runtime)
├── storage/
│   ├── jobs/<job_id>/            YouTube: video.mp4 + frames/
│   └── ncert/class<N>/           NCERT: <code>.zip
└── config/.env.example
```

## Technology Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2 +
  pydantic-settings, PyJWT, bcrypt.
- **Media/Processing:** yt-dlp, FFmpeg (system binary), RapidOCR
  (`rapidocr-onnxruntime`, ONNX — no Tesseract), OpenCV + NumPy (frame analysis),
  **PyMuPDF** (deterministic PDF structure extraction).
- **Acquisition:** `curl_cffi` (browser-TLS impersonation; required because
  NCERT's WAF resets plain Python TLS).
- **Frontend:** React 18, TypeScript, Vite, Bootstrap 5, Bootstrap Icons, axios,
  react-router-dom. State via React Context (auth) + local state; polling for jobs.
- **DB:** SQLite (dev). SQLAlchemy abstraction allows a future Postgres move.

## Database Summary

| Table | Purpose | Module |
|-------|---------|--------|
| `users` | Accounts | Auth/RBAC |
| `roles` | Roles | RBAC |
| `permissions` | `module:action` permissions | RBAC |
| `role_permissions` | Role↔Permission M2M | RBAC |
| `extraction_jobs` | YouTube extraction jobs (status/stage/progress) | YouTube |
| `frames` | Extracted frames + score/dedup/OCR fields | YouTube |
| `questions` | Extracted/merged questions + confidences + status | YouTube |
| `acquisition_jobs` | **Generic** source jobs (scan/download/refresh) | Acquisition (NCERT, future) |
| `ncert_books` | NCERT book registry/catalog | NCERT |
| `notifications` | App notifications | Notifications (shared) |
| `documents` | **Generic** processed-document registry | Knowledge Extraction (any source) |
| `document_elements` | **Generic** structural elements (heading/paragraph/table/figure) | Knowledge Extraction |
| `document_bookmarks` | Document outline / TOC | Knowledge Extraction |
| `knowledge_nodes` | **Generic** hierarchical knowledge tree (parent_id self-FK, materialized path) | Knowledge Mapping |

Schema is created via `Base.metadata.create_all`; additive column changes are
applied by a lightweight `ALTER TABLE` migration in `database/session.init_db`.

## Worker Architecture

Background work uses in-process `ThreadPoolExecutor` pools; jobs persist rows with
`status/stage/progress`, and the frontend polls.

| Worker | File | Handles |
|--------|------|---------|
| Extraction worker | `core/worker.py` | YouTube: download → frame extraction → auto analysis (`analyzing` stage) |
| Acquisition worker | `core/acquisition_worker.py` | Generic jobs: `scan` / `download` / `refresh` (NCERT) **and** `document_extract` (Knowledge Extraction), dispatched by `job_type` |

New sources/processing reuse the **acquisition worker** (and `acquisition_jobs`)
rather than adding a new one.

## Storage Structure

```
storage/
├── jobs/<job_id>/
│   ├── video.mp4
│   └── frames/frame_00001.jpg ...
├── ncert/class<N>/<book_code>.zip   (+ checksum/version stored in DB)
└── documents/
    ├── upload/<uuid>.pdf             uploaded PDFs
    └── ncert/<book_code>/<chapter>.pdf   PDFs unzipped from acquired NCERT books
```

## Acquisition Sources

| Source | Status | Notes |
|--------|--------|-------|
| YouTube | ✅ Live | Video → frames → questions |
| NCERT | ✅ Live | textbook.php scan → complete-book zip download |
| PDF | ⏳ Coming soon | Sidebar placeholder |
| Images | ⏳ Coming soon | Sidebar placeholder |

## Processing Pipeline

**YouTube:** URL → yt-dlp download → FFmpeg frame extraction → frame question
detection (image analysis) + dedup → auto-OCR of question frames → merge
consecutive frames into questions with confidence → review queue → export.

**NCERT:** scan textbook.php (parse embedded JS) → book registry → select/all →
download complete-book zip (checksum + version signature) → update detection.

**Knowledge Extraction:** PDF (uploaded, or unzipped from an acquired NCERT book)
→ `document_extract` job → PyMuPDF deterministic extraction → text-layer detection
(flag `needs_ocr` if none) → headings (font-size levels) / paragraphs / tables
(cells) / figures / bookmarks → stored in generic document tables → structure viewer.

**Knowledge Mapping:** processed document's elements + bookmarks → deterministic
tree builder → hierarchical `knowledge_nodes` (parent-child) — hierarchy from
headings (preferred) or bookmarks (fallback) or flat; paragraphs/tables/figures
become leaf nodes under their enclosing section. Runs automatically after
extraction. Navigation (tree / node + breadcrumb) and search APIs feed the
Knowledge Explorer.

---

## Completed Modules

### 1. Admin Portal (Shell)
- **Purpose:** Admin UI shell scalable to 30+ modules.
- **Status:** ✅ Complete · **Sprint:** 1
- **Backend Components:** `core/app.py` (FastAPI factory, CORS, router wiring), `/api/health`.
- **Frontend Components:** `components/Layout.tsx` (collapsible sidebar, top nav, breadcrumb, search, notifications bell), `pages/Dashboard.tsx` (module cards), `modules.ts` (registry driving sidebar + dashboard, grouped, scales to 30+).
- **Database Tables:** — (uses RBAC tables).
- **Workers:** —
- **APIs:** `GET /api/health`.
- **Storage:** —
- **Configuration:** `app_name`, `cors_origins`, `api_host/port`.
- **Dependencies:** FastAPI, React, Bootstrap 5.
- **Reusable Components:** `Layout`, `modules.ts`, `Modal`.
- **Verification Status:** ✅ Builds; navigation/permission-gated rendering verified.
- **Future Improvements:** Per-module breadcrumbs; saved sidebar collapse state.

### 2. Authentication
- **Purpose:** Login + session via JWT.
- **Status:** ✅ Complete · **Sprint:** 1
- **Backend Components:** `services/auth_service.py`, `shared/security.py` (bcrypt hash/verify, JWT encode/decode), `api/deps.py` (`get_current_user`), `routers/auth.py`.
- **Frontend Components:** `auth/AuthContext.tsx`, `pages/Login.tsx`, `api/client.ts` (Bearer interceptor, 401 redirect).
- **Database Tables:** `users`.
- **Workers:** —
- **APIs:** `POST /api/auth/login`, `GET /api/auth/me`.
- **Storage:** —
- **Configuration:** `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes`, seed `admin_*`.
- **Dependencies:** PyJWT, bcrypt.
- **Reusable Components:** `require_permission`, `get_current_user`, `AuthContext.can()`.
- **Verification Status:** ✅ Login + protected routes verified.
- **Future Improvements:** Refresh tokens; password reset.

### 3. RBAC (Roles & Permissions)
- **Purpose:** Module-based access control (`module:action`).
- **Status:** ✅ Complete · **Sprint:** 1
- **Backend Components:** `models/rbac.py` (User/Role/Permission/role_permissions, `has_permission`), `repositories/user_repository.py`, `repositories/rbac_repository.py`, `routers/users.py`, `routers/roles.py`, `core/seed.py` (seeds modules' permissions + Super Admin + admin user).
- **Frontend Components:** `pages/Users.tsx`, `pages/Roles.tsx` (permission matrix by module).
- **Database Tables:** `users`, `roles`, `permissions`, `role_permissions`.
- **Workers:** —
- **APIs:** `GET/POST/PUT/DELETE /api/users`, `GET /api/permissions`, `GET/POST/PUT/DELETE /api/roles`.
- **Storage:** —
- **Configuration:** Seed `MODULE_ACTIONS` in `core/seed.py`.
- **Dependencies:** SQLAlchemy.
- **Reusable Components:** `require_permission(code)`, permission seeding pattern.
- **Verification Status:** ✅ CRUD + permission enforcement verified.
- **Future Improvements:** Per-user direct permissions; audit logging.

### 4. YouTube Acquisition + Frame Extraction
- **Purpose:** Download a YouTube video and extract candidate frames.
- **Status:** ✅ Complete · **Sprint:** 1 (extended Sprint 2)
- **Backend Components:** `integrations/ytdlp.py`, `integrations/ffmpeg.py`, `services/extraction_service.py`, `core/worker.py`, `repositories/extraction_repository.py`, `routers/extractor.py`.
- **Frontend Components:** `pages/YouTubeExtractor.tsx` (URL submit, job progress, frame gallery), `components/JobProgress.tsx`.
- **Database Tables:** `extraction_jobs`, `frames`.
- **Workers:** Extraction worker (`core/worker.py`).
- **APIs:** `POST/GET /api/extractor/jobs`, `GET /api/extractor/jobs/{id}`, `DELETE`, `GET /api/extractor/jobs/{id}/frames`, `GET /api/extractor/frames/{id}/image`.
- **Storage:** `storage/jobs/<id>/video.mp4`, `frames/`.
- **Configuration:** `frame_max_count`, `frame_min_interval`, `ffmpeg_path`, `ffprobe_path`.
- **Dependencies:** yt-dlp, FFmpeg.
- **Reusable Components:** `JobProgress`, frame-image token-auth serving.
- **Verification Status:** ✅ Real download + frame extraction verified.
- **Future Improvements:** Scene-detection extraction option.

### 5. OCR Workflow (manual)
- **Purpose:** OCR user-selected frames into questions.
- **Status:** ✅ Complete · **Sprint:** 1
- **Backend Components:** `integrations/ocr.py` (RapidOCR; `read_image` + `read_image_detailed`), `services/extraction_service.run_ocr`.
- **Frontend Components:** frame multi-select + "OCR selected" + inline question editor in `YouTubeExtractor.tsx`.
- **Database Tables:** `questions`.
- **Workers:** — (synchronous on request).
- **APIs:** `POST /api/extractor/jobs/{id}/ocr`.
- **Storage:** —
- **Configuration:** —
- **Dependencies:** rapidocr-onnxruntime.
- **Reusable Components:** `OCR.read_image_detailed` (text + confidence).
- **Verification Status:** ✅ OCR reads question text/options.
- **Future Improvements:** Per-region OCR; language packs.

### 6. Automatic Question Extraction
- **Purpose:** Eliminate manual frame selection — detect, dedup, OCR, merge automatically.
- **Status:** ✅ Complete · **Sprint:** 2
- **Backend Components:** `integrations/frame_analysis.py` (`question_probability` via MSER text-density + background-uniformity + low-saturation; `signature`/`difference` MAD dedup), `services/analysis_service.py` (`analyze_job`: score+dedup → auto-OCR → merge with confidence), runs automatically in `core/worker.py` (`analyzing` stage).
- **Frontend Components:** `YouTubeExtractor.tsx` "Show all frames" toggle (default = probable only), per-frame probability/dup badges, "Re-run detection".
- **Database Tables:** `frames` (question_score, is_question, is_duplicate, phash, ocr_text, ocr_confidence, ocr_done), `questions` (options, source, status, ocr/frame/merge/overall confidence, frame_start/end).
- **Workers:** Extraction worker (extended).
- **APIs:** `POST /api/extractor/jobs/{id}/analyze`, frame filters (`probable_only`, `include_duplicates`).
- **Storage:** —
- **Configuration:** `question_threshold` (0.55), `dedup_mad` (0.012), `merge_threshold` (0.35).
- **Dependencies:** OpenCV, NumPy (via rapidocr stack).
- **Reusable Components:** `FrameAnalyzer`, `ConfidenceBadge`.
- **Verification Status:** ✅ Deterministic synthetic + real-video tests (slides 1.0 vs photos ≤0.49; dedup keeps meaningful changes; merge groups correctly).
- **Future Improvements:** Layout-aware option parsing; per-line OCR confidence weighting.

### 7. Review Queue
- **Purpose:** Curate extracted questions (edit/approve/reject/delete).
- **Status:** ✅ Complete · **Sprint:** 2
- **Backend Components:** `extraction_service.update_question` (text/options/status), approve/reject endpoints.
- **Frontend Components:** `pages/Review.tsx` (left list + status filters, right editable text/options, Save/Approve/Reject/Delete), `components/ConfidenceBadge.tsx`.
- **Database Tables:** `questions`.
- **Workers:** —
- **APIs:** `GET /api/extractor/jobs/{id}/questions`, `PUT /api/extractor/questions/{id}`, `POST .../approve`, `POST .../reject`, `DELETE`.
- **Storage:** —
- **Configuration:** —
- **Dependencies:** —
- **Reusable Components:** `ConfidenceBadge`, `QuestionStatusBadge`.
- **Verification Status:** ✅ Edit/approve/reject/delete verified.
- **Future Improvements:** Bulk approve; keyboard review shortcuts.

### 8. Export Engine
- **Purpose:** Export questions in multiple formats.
- **Status:** ✅ Complete · **Sprint:** 2
- **Backend Components:** `extraction_service.export` / `export_csv` / `export_sqlite`, `routers/extractor.export_job` (`format=json|csv|sqlite`).
- **Frontend Components:** Export dropdown in `YouTubeExtractor.tsx` (authenticated blob download).
- **Database Tables:** `questions` (read).
- **Workers:** —
- **APIs:** `GET /api/extractor/jobs/{id}/export?format=`.
- **Storage:** temp SQLite file for sqlite export.
- **Configuration:** —
- **Dependencies:** stdlib csv/sqlite3.
- **Reusable Components:** export row-builder.
- **Verification Status:** ✅ JSON/CSV/SQLite verified.
- **Future Improvements:** XLSX; per-status export filters.

### 9. NCERT Acquisition
- **Purpose:** Scan official NCERT site, catalog books, download complete-book PDFs, detect updates.
- **Status:** ✅ Complete · **Sprint:** 3
- **Backend Components:** `integrations/ncert_scraper.py` (parse textbook.php JS → ~835 books), `integrations/ncert_downloader.py` (curl_cffi stream, sha256 checksum, remote version signature, retries), `services/ncert_service.py` (scan/list/queue/download-all/retry/delete/refresh), `repositories/ncert_repository.py`, `repositories/acquisition_repository.py`, `routers/ncert.py`.
- **Frontend Components:** `pages/Ncert.tsx` (stats cards, Scan/Check Updates/Download All, Download Queue via reused `JobProgress`, filters + search + pagination, multi-select download, per-row retry/delete).
- **Database Tables:** `ncert_books`, `acquisition_jobs`.
- **Workers:** Acquisition worker (`core/acquisition_worker.py`).
- **APIs:** `/api/sources/ncert/`: `POST scan`, `POST refresh`, `POST download`, `POST download-all`, `GET books`, `GET stats`, `GET facets`, `GET jobs`, `POST books/{id}/retry`, `DELETE books/{id}/download`.
- **Storage:** `storage/ncert/class<N>/<code>.zip`.
- **Configuration:** `ncert_page_url`, `ncert_files_base`, `ncert_retry_count`, `ncert_concurrent_downloads`, `ncert_timeout`.
- **Dependencies:** curl_cffi (browser-TLS; NCERT WAF resets plain Python TLS).
- **Reusable Components:** `AcquisitionJob` table + acquisition worker (reuse for future sources), `JobProgress`.
- **Verification Status:** ✅ Live HTTP E2E: scan 835 books → download keac2.zip (4.6 MB + checksum) → version-check → delete → notifications.
- **Future Improvements:** Cover thumbnails; per-chapter download; parallel-download tuning.

### 10. Notification System
- **Purpose:** Surface async events (scan complete, book downloaded, download failed, updates available).
- **Status:** ✅ Complete · **Sprint:** 3
- **Backend Components:** `models/acquisition.Notification`, `services/notification_service.py`, `repositories/acquisition_repository.NotificationRepository`, `routers/notifications.py`.
- **Frontend Components:** Topbar bell in `Layout.tsx` (polls every 8s, unread badge, dropdown, mark-all-read).
- **Database Tables:** `notifications`.
- **Workers:** Produced by the acquisition worker.
- **APIs:** `GET /api/notifications`, `POST /api/notifications/read-all`, `POST /api/notifications/{id}/read`.
- **Storage:** —
- **Configuration:** —
- **Dependencies:** —
- **Reusable Components:** `notification_service.push(db, level, title, message, source)` — usable by any module.
- **Verification Status:** ✅ Notifications created on scan/download; unread badge verified.
- **Future Improvements:** Per-user targeting; WebSocket push instead of polling.

### 11. Acquisition Jobs (generic)
- **Purpose:** Shared job/progress plumbing for all acquisition sources.
- **Status:** ✅ Complete · **Sprint:** 3
- **Backend Components:** `models/acquisition.AcquisitionJob`, `repositories/acquisition_repository.AcquisitionJobRepository`, `core/acquisition_worker.py` (dispatch by `job_type`).
- **Frontend Components:** Download Queue panel in `pages/Ncert.tsx` (reuses `JobProgress`).
- **Database Tables:** `acquisition_jobs`.
- **Workers:** Acquisition worker.
- **APIs:** `GET /api/sources/ncert/jobs` (per-source listing).
- **Storage:** —
- **Configuration:** `ncert_concurrent_downloads` (pool size).
- **Dependencies:** —
- **Reusable Components:** The table + worker are the extension point for PDF/Image sources.
- **Verification Status:** ✅ Scan/download/refresh jobs run and report progress.
- **Future Improvements:** Job cancellation; job history pruning.

### 12. Knowledge Extraction Engine
- **Purpose:** Deterministically extract document structure from PDFs (text-layer detection, headings, paragraphs, tables, figures, bookmarks). No AI, no OCR — text-layer detection only flags whether OCR *would* be needed.
- **Status:** ✅ Complete · **Sprint:** 4
- **Backend Components:** `integrations/pdf_extractor.py` (PyMuPDF: `get_text("dict")` font-size heading classification, `find_tables()` cells, `get_image_info()` figures, `get_toc()` bookmarks, text-layer detection), `services/knowledge_service.py` (upload, import-from-NCERT unzip, `run_extraction`, reprocess, delete), `repositories/document_repository.py`, `routers/documents.py`. Reuses `acquisition_jobs` (`job_type="document_extract"`) and the **acquisition worker**.
- **Frontend Components:** `pages/Documents.tsx` (stats cards, Upload PDF, Import-from-NCERT, extraction queue via reused `JobProgress`, search + pagination, reprocess/delete), `pages/DocumentViewer.tsx` (bookmarks outline + structured rendering: headings by level, paragraphs, tables as grids, figures, type filters).
- **Database Tables:** `documents`, `document_elements`, `document_bookmarks` (all generic, reusable by any document source).
- **Workers:** Acquisition worker (`core/acquisition_worker.py`, `document_extract` branch).
- **APIs:** `/api/documents/`: `POST upload`, `POST import/ncert`, `GET ""`, `GET stats`, `GET jobs`, `GET ncert-books`, `GET {id}`, `GET {id}/elements`, `POST {id}/reprocess`, `DELETE {id}`.
- **Storage:** `storage/documents/upload/<uuid>.pdf`, `storage/documents/ncert/<code>/<chapter>.pdf`.
- **Configuration:** uses `storage_dir`; no new env keys.
- **Dependencies:** PyMuPDF (fitz).
- **Reusable Components:** generic `documents`/`document_elements`/`document_bookmarks` tables + `PdfExtractor` (any future document source feeds them); `JobProgress`, `acquisition_jobs`, acquisition worker, `notification_service`.
- **Verification Status:** ✅ HTTP E2E (upload → async extract → 3 headings/1 paragraph/1 table(3×3)/1 figure + 3 bookmarks; text-layer + needs_ocr detection; element type filter; notifications) and NCERT-zip import (2 PDFs → 2 documents). Idempotent reprocess verified.
- **Future Improvements:** OCR fallback for `needs_ocr` documents; reading-order refinement (pymupdf_layout); caption/figure-number association; question extraction from structured text.

### 13. Knowledge Mapping Engine
- **Purpose:** Deterministically map a processed document's extracted structure into a generic hierarchical knowledge tree (parent-child), with navigation + search APIs and a Knowledge Explorer. No AI, no OCR.
- **Status:** ✅ Complete · **Sprint:** 6
- **Backend Components:** `models/knowledge.py` (`KnowledgeNode`: self-referential `parent_id`, `depth`, `order_index`, materialized `path`, `element_id` provenance), `services/knowledge_map_service.py` (`map_document` tree builder; `tree`/`node_detail`+breadcrumb/`search` navigation), `repositories/knowledge_repository.py`, `routers/knowledge.py`. Mapping runs **automatically** at the end of `knowledge_service._extract_one` (reuses the existing extraction pipeline); `delete` clears nodes.
- **Frontend Components:** `pages/Knowledge.tsx` (Knowledge Explorer: stats cards, document selector, expandable tree, node-detail panel with breadcrumb/content/table/figure/children, in-document search, Remap).
- **Database Tables:** `knowledge_nodes` (generic, reusable by any source).
- **Workers:** — (mapping is fast and deterministic; runs inline within the `document_extract` job and on-demand via remap).
- **APIs:** `/api/knowledge/`: `GET stats`, `GET documents`, `GET documents/{id}/tree`, `GET nodes/{id}`, `GET search?q=&document_id=`, `POST documents/{id}/remap`.
- **Storage:** — (derived from `document_elements`/`document_bookmarks`).
- **Configuration:** none.
- **Dependencies:** — (pure Python over existing tables).
- **Reusable Components:** generic `knowledge_nodes` tree + `KnowledgeMapService` (any future structured source feeds the same hierarchy); reuses Documents/Extraction pipeline.
- **Verification Status:** ✅ HTTP E2E: upload PDF → auto extract+map → nested tree (root → chapters → subsections → paragraph/table/figure leaves), node detail with breadcrumb + children, content search with breadcrumb, idempotent remap. Heading-hierarchy + bookmark-fallback + flat strategies implemented.
- **Future Improvements:** Cross-document global search UI; node tagging/annotations; export subtree; question extraction seeded from sections.

---

## APIs (current)

| Method | Path | Permission |
|--------|------|------------|
| POST | `/api/auth/login` | public |
| GET | `/api/auth/me` | authenticated |
| GET/POST/PUT/DELETE | `/api/users[/{id}]` | `users:*` |
| GET | `/api/permissions` | `roles:view` |
| GET/POST/PUT/DELETE | `/api/roles[/{id}]` | `roles:*` |
| GET/POST | `/api/extractor/jobs` | `youtube_extractor:view/execute` |
| GET/DELETE | `/api/extractor/jobs/{id}` | `youtube_extractor:view/delete` |
| GET | `/api/extractor/jobs/{id}/frames` | `youtube_extractor:view` |
| GET | `/api/extractor/frames/{id}/image` | token (query) |
| POST | `/api/extractor/jobs/{id}/analyze` | `youtube_extractor:execute` |
| POST | `/api/extractor/jobs/{id}/ocr` | `youtube_extractor:execute` |
| GET | `/api/extractor/jobs/{id}/questions` | `youtube_extractor:view` |
| PUT/DELETE | `/api/extractor/questions/{id}` | `youtube_extractor:update` |
| POST | `/api/extractor/questions/{id}/approve\|reject` | `youtube_extractor:update` |
| GET | `/api/extractor/jobs/{id}/export?format=json\|csv\|sqlite` | `youtube_extractor:export` |
| POST | `/api/sources/ncert/scan\|refresh\|download\|download-all` | `ncert:execute` |
| GET | `/api/sources/ncert/books\|stats\|facets\|jobs` | `ncert:view` |
| POST | `/api/sources/ncert/books/{id}/retry` | `ncert:execute` |
| DELETE | `/api/sources/ncert/books/{id}/download` | `ncert:delete` |
| POST | `/api/documents/upload` (multipart PDF) | `documents:execute` |
| POST | `/api/documents/import/ncert` | `documents:execute` |
| GET | `/api/documents`, `/api/documents/stats`, `/api/documents/jobs`, `/api/documents/ncert-books` | `documents:view` |
| GET | `/api/documents/{id}`, `/api/documents/{id}/elements` | `documents:view` |
| POST | `/api/documents/{id}/reprocess` | `documents:execute` |
| DELETE | `/api/documents/{id}` | `documents:delete` |
| GET | `/api/knowledge/stats`, `/api/knowledge/documents` | `knowledge:view` |
| GET | `/api/knowledge/documents/{id}/tree`, `/api/knowledge/nodes/{id}` | `knowledge:view` |
| GET | `/api/knowledge/search?q=&document_id=` | `knowledge:view` |
| POST | `/api/knowledge/documents/{id}/remap` | `knowledge:execute` |
| GET | `/api/notifications` | authenticated |
| POST | `/api/notifications/read-all`, `/api/notifications/{id}/read` | authenticated |
| GET | `/api/health` | public |

## Background Jobs

| Job | Worker | Stages |
|-----|--------|--------|
| YouTube extraction | `core/worker.py` | downloading → extracting → analyzing → ready / failed |
| NCERT scan | `core/acquisition_worker.py` | queued → scanning → completed / failed |
| NCERT download | `core/acquisition_worker.py` | queued → downloading → completed / failed |
| NCERT refresh (version check) | `core/acquisition_worker.py` | queued → scanning → completed / failed |
| Document structure extraction | `core/acquisition_worker.py` | queued → processing → completed / failed |

## Configuration

All settings via env (prefix `QVAULT_`), see `config/.env.example`. Keys:
app/env/log; api host/port; cors; `database_url`; `storage_dir`; jwt secret/algo/expiry;
seed admin; `ffmpeg_path`/`ffprobe_path`; `frame_max_count`/`frame_min_interval`;
`question_threshold`/`dedup_mad`/`merge_threshold`; `ncert_page_url`/`ncert_files_base`/
`ncert_retry_count`/`ncert_concurrent_downloads`/`ncert_timeout`. Permission modules are
seeded in `core/seed.py`: `dashboard`, `youtube_extractor`, `ncert`, `documents`, `knowledge`, `users`, `roles`, `settings`.
The Knowledge Extraction & Mapping Engines add no new env keys (use `storage_dir`/existing tables).

## Current Status

Sprints 1–6 complete and verified. Backend imports cleanly (59 routes). Frontend
builds cleanly. Two live acquisition sources (YouTube, NCERT); a deterministic
Knowledge Extraction Engine (PDF → structure) feeding a Knowledge Mapping Engine
(structure → hierarchical knowledge tree + Explorer); plus automatic question
extraction, review, multi-format export, and notifications.

## Known Issues

- **NCERT TLS:** NCERT's WAF resets plain Python TLS; scraper/downloader use
  `curl_cffi` impersonating Chrome. (This dev sandbox also resets NCERT TLS — verify
  scans on the host network; the real server is unaffected.)
- **Worker durability:** Workers are in-process `ThreadPoolExecutor`; jobs do not
  survive a server restart (acceptable for current scale).
- **SQLite migrations:** Additive columns only (ALTER ADD COLUMN); no destructive
  migrations. Postgres + Alembic deferred to a future phase.
- **PDF structure heuristics:** Heading vs paragraph is font-size based and table
  detection is for ruled tables (PyMuPDF `find_tables`); borderless tables and
  multi-column reading order are approximate. Image-only PDFs are flagged
  `needs_ocr` but not OCR'd (acquisition/extraction only).

## Future Roadmap

- PDF & Image acquisition sources (reuse `acquisition_jobs` + acquisition worker).
- OCR fallback for documents flagged `needs_ocr` (image-only PDFs).
- Question extraction from extracted document structure (structured text → questions).
- Question Bank, Validation, Classification, Syllabus, Knowledge Graph.
- Search & Answering (embeddings → vector store; likely Postgres + pgvector).
- Hardening: durable queue, auth refresh tokens, audit logs, metrics.
- User Portal (student modules).

## Change History

| Date | Version | Change |
|------|---------|--------|
| 2026-06-28 | v0.1.0 | Sprint 1 — Admin Portal, Auth, RBAC, YouTube extractor (manual OCR workflow), export JSON. |
| 2026-06-29 | v0.2.0 | Sprint 2 — Automatic question extraction (frame detection, dedup, auto-OCR, merge, confidence), Review queue, CSV/SQLite export. |
| 2026-06-29 | v0.3.0 | Sprint 3 — NCERT Acquisition Agent, generic Acquisition Jobs, Notification system; sidebar "Sources" group. |
| 2026-06-29 | v0.4.0 | Sprint 4 — Knowledge Extraction Engine (PyMuPDF deterministic PDF structure: text-layer detection, headings, paragraphs, tables, figures, bookmarks); generic document tables; document structure viewer; reuses acquisition jobs/worker. |
| 2026-06-29 | v0.5.0 | Sprint 6 — Knowledge Mapping Engine (deterministic hierarchical `knowledge_nodes` tree from extracted structure; headings/bookmarks/flat strategies; auto-maps after extraction); navigation + search APIs; Knowledge Explorer. |
