# AGENTS.md — QVault Permanent Development Rules

These are the permanent rules for QVault. **Every future task must follow them.**
This file, `Project_Master_Document.md`, and `Project_Todo.md` are the only
documents a future chat should read before starting work.

---

## Project Purpose

QVault is an **AI-powered Exam Intelligence Platform**. It acquires exam-relevant
content from multiple sources (YouTube, NCERT, and future PDF/Image sources),
extracts structured questions, and will eventually make them searchable,
classified, and answerable.

The application has two areas:
- **Admin Portal** — 30+ admin modules (current focus).
- **User Portal** — 3–5 student modules (future).

Everything must be designed so new modules can be added without redesign.

---

## Coding Standards

- **Backend:** Python 3.11+ / FastAPI. Strict layering, typed Pydantic v2 DTOs,
  SQLAlchemy 2.0 models. No unnecessary abstraction.
- **Frontend:** React 18 + TypeScript + Vite + **Bootstrap 5** + Bootstrap Icons.
  Functional components, hooks, `strict` TypeScript (build must pass `tsc`).
- Production-ready code only. No placeholder code, no mock data, no dead stubs.
- Minimal comments — only where intent is non-obvious. Code reads like the
  surrounding code.
- Every change must leave the backend importing cleanly and the frontend building
  cleanly (`npm run build`).

---

## Architecture Rules

- One backend package root: `backend/app/`. Never create a parallel package tree.
- Strict one-directional dependencies:
  `api → services → repositories → database`, `services → integrations`,
  `workers → services`, `core` wires everything at startup.
- HTTP routers are thin adapters. Business logic lives in services. SQL/ORM lives
  only in repositories. Third-party tools (yt-dlp, ffmpeg, OCR, scrapers) live
  only in `integrations/`.
- RBAC is module-based: permissions are `module:action` (e.g. `ncert:execute`).
  Guard every endpoint with `require_permission(...)`.
- Background work runs through a worker (`ThreadPoolExecutor`) writing job rows
  with status/progress; the frontend polls. Never block request handlers on long
  work.
- New acquisition sources reuse the generic `acquisition_jobs` table and the
  `acquisition_worker`. The YouTube extractor keeps its dedicated tables/worker.

---

## Reuse Policy

- Reuse before building. Check `Project_Master_Document.md` for existing services,
  workers, tables, APIs, and UI components first.
- Extend existing functionality instead of rewriting it.
- Never duplicate functionality. Never create a second worker/table/endpoint that
  does what an existing one does.
- Reuse shared UI: `Layout`, `JobProgress`, `Modal`, `ConfidenceBadge`, status
  badges, the module registry (`modules.ts`).
- Keep implementations modular so the next source/module can reuse them.

---

## Token Saving Policy (MANDATORY — project rules)

1. Read Project_Master_Document.md first.
2. Read Project_Todo.md second.
3. Read additional source files ONLY if required for the current task.
4. Never rescan the whole project.
5. Never reread completed modules unless modification is required.
6. Reuse existing services, workers, APIs and UI.
7. If functionality already exists, extend it instead of rewriting.
8. Prefer deterministic Python processing over AI whenever possible.
9. Use AI only when deterministic algorithms cannot solve the problem.
10. Never redesign completed modules unless explicitly instructed.
11. Never create duplicate functionality.
12. Keep implementations modular and reusable.
13. Reuse existing database tables where appropriate.
14. Reuse existing workers before creating new ones.
15. Keep UI consistent with the Admin Portal.
16. Build production-ready code only.
17. No placeholder code.
18. No mock data.
19. Do not modify unrelated modules.
20. At the end of every completed sprint, update Project_Master_Document.md and Project_Todo.md.

---

## Development Workflow

1. Read `Project_Master_Document.md`, then `Project_Todo.md`.
2. Move the task into **IN PROGRESS** in `Project_Todo.md`.
3. Implement, reusing existing components per the Reuse Policy.
4. Verify: backend imports cleanly (`python -c "from app.core.app import app"`),
   frontend builds (`npm run build`), and the feature works end-to-end.
5. Do not modify unrelated modules.
6. On completion, update `Project_Master_Document.md` and move the task to
   **COMPLETED** in `Project_Todo.md`.

### Running the project
```
# Backend  -> http://127.0.0.1:8004
cd E:\QVault\backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8004

# Frontend -> http://localhost:5173
cd E:\QVault\frontend
npm install
npm run dev
```
Port 8000 is permanently reserved by an unrelated app (NEXORA) on this machine
— QVault's backend always runs on **8004** (never 8000); `frontend/vite.config.ts`'s
dev proxy already targets `127.0.0.1:8004` to match. Do not change either back to
8000.

Default login: **admin / admin123**. FFmpeg must be on PATH. NCERT scraping uses
`curl_cffi` (browser-TLS) because NCERT's WAF resets plain Python TLS.

---

## Completion Checklist

- [ ] Followed the Token Saving Policy (read master + todo first; no full rescan).
- [ ] Reused existing services/workers/tables/APIs/UI where possible.
- [ ] No duplicate functionality, no placeholder code, no mock data.
- [ ] Unrelated modules untouched; existing APIs unbroken.
- [ ] Backend imports cleanly; frontend `npm run build` passes.
- [ ] Feature verified end-to-end (real data, not mocked).
- [ ] RBAC permissions added/seeded for any new module.
- [ ] `Project_Master_Document.md` updated (module entry + Change History).
- [ ] `Project_Todo.md` updated (task moved to COMPLETED).
