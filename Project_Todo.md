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

## IN PROGRESS

- _(none)_

## COMPLETED

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
