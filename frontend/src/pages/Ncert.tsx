import { useCallback, useEffect, useRef, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import JobProgress from "../components/JobProgress";
import type { AcquisitionJob, NcertBook, NcertFacets, NcertStats } from "../types";

const STATUS_BADGE: Record<string, string> = {
  available: "bg-secondary",
  queued: "bg-info",
  downloading: "bg-info",
  downloaded: "bg-success",
  failed: "bg-danger",
  update_available: "bg-warning text-dark",
};

const PAGE_SIZE = 25;

function fmtSize(bytes: number): string {
  if (!bytes) return "—";
  const mb = bytes / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

export default function Ncert() {
  const { can } = useAuth();
  const canExecute = can("ncert:execute");
  const canDelete = can("ncert:delete");

  const [stats, setStats] = useState<NcertStats | null>(null);
  const [facets, setFacets] = useState<NcertFacets>({ classes: [], subjects: [], languages: [], statuses: [] });
  const [books, setBooks] = useState<NcertBook[]>([]);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState<AcquisitionJob[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [search, setSearch] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [subject, setSubject] = useState("");
  const [language, setLanguage] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const pollRef = useRef<number | null>(null);

  const loadStats = useCallback(async () => {
    const [s, f] = await Promise.all([
      api.get<NcertStats>("/api/sources/ncert/stats"),
      api.get<NcertFacets>("/api/sources/ncert/facets"),
    ]);
    setStats(s.data);
    setFacets(f.data);
  }, []);

  const loadBooks = useCallback(async () => {
    try {
      const res = await api.get<{ items: NcertBook[]; total: number }>("/api/sources/ncert/books", {
        params: {
          search: search || undefined,
          class_level: classLevel || undefined,
          subject: subject || undefined,
          language: language || undefined,
          status: status || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        },
      });
      setBooks(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      setError(apiError(e));
    }
  }, [search, classLevel, subject, language, status, page]);

  const loadJobs = useCallback(async () => {
    const res = await api.get<AcquisitionJob[]>("/api/sources/ncert/jobs");
    setJobs(res.data);
    return res.data;
  }, []);

  useEffect(() => {
    loadStats().catch((e) => setError(apiError(e)));
  }, [loadStats]);

  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  // Poll jobs; while any is active, refresh data; stop when all settle.
  const startPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const data = await loadJobs();
      const active = data.some((j) => ["queued", "scanning", "downloading"].includes(j.status));
      if (!active) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
        loadStats();
        loadBooks();
      } else {
        loadStats();
        loadBooks();
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2500);
  }, [loadJobs, loadStats, loadBooks]);

  useEffect(() => {
    loadJobs().then((data) => {
      if (data.some((j) => ["queued", "scanning", "downloading"].includes(j.status))) startPolling();
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [loadJobs, startPolling]);

  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      startPolling();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const scan = () => action(() => api.post("/api/sources/ncert/scan"));
  const refresh = () => action(() => api.post("/api/sources/ncert/refresh"));
  const downloadAll = () => action(() => api.post("/api/sources/ncert/download-all"));
  const downloadSelected = () =>
    action(async () => {
      await api.post("/api/sources/ncert/download", { book_ids: [...selected] });
      setSelected(new Set());
    });
  const retry = (id: number) => action(() => api.post(`/api/sources/ncert/books/${id}/retry`));
  const removeDownload = (id: number) =>
    action(() => api.delete(`/api/sources/ncert/books/${id}/download`));

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    const ids = books.filter((b) => !b.downloaded).map((b) => b.id);
    const allOn = ids.every((id) => selected.has(id)) && ids.length > 0;
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (allOn ? next.delete(id) : next.add(id)));
      return next;
    });
  }

  function resetFilters() {
    setSearch("");
    setClassLevel("");
    setSubject("");
    setLanguage("");
    setStatus("");
    setPage(0);
  }

  const activeJobs = jobs.filter((j) => ["queued", "scanning", "downloading"].includes(j.status));
  const lastJob = jobs[0];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const cards = [
    { label: "Available", value: stats?.available ?? 0, icon: "bi-collection", color: "#2563eb" },
    { label: "Downloaded", value: stats?.downloaded ?? 0, icon: "bi-check-circle", color: "#16a34a" },
    { label: "Pending", value: stats?.pending ?? 0, icon: "bi-hourglass-split", color: "#d97706" },
    { label: "Failed", value: stats?.failed ?? 0, icon: "bi-x-circle", color: "#dc2626" },
    { label: "Updates", value: stats?.update_available ?? 0, icon: "bi-arrow-repeat", color: "#9333ea" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-journal-bookmark text-info me-2" />
          NCERT Acquisition
        </h3>
        {canExecute && (
          <div className="d-flex gap-2">
            <button className="btn btn-primary" disabled={busy} onClick={scan}>
              <i className="bi bi-binoculars me-1" />
              Scan Website
            </button>
            <button className="btn btn-outline-secondary" disabled={busy} onClick={refresh}>
              <i className="bi bi-arrow-repeat me-1" />
              Check Updates
            </button>
            <button className="btn btn-success" disabled={busy} onClick={downloadAll}>
              <i className="bi bi-cloud-download me-1" />
              Download All
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-danger d-flex justify-content-between">
          <span>{error}</span>
          <button className="btn-close" onClick={() => setError("")} />
        </div>
      )}

      <div className="row g-3 mb-3">
        {cards.map((c) => (
          <div className="col-6 col-md-4 col-xl-2 flex-xl-fill" key={c.label}>
            <div className="card border-0 shadow-sm h-100">
              <div className="card-body d-flex align-items-center gap-3">
                <div
                  className="qv-module-icon mb-0"
                  style={{ background: c.color, width: 40, height: 40, fontSize: "1.1rem" }}
                >
                  <i className={`bi ${c.icon}`} />
                </div>
                <div>
                  <div className="fs-4 fw-bold lh-1">{c.value}</div>
                  <div className="small text-muted">{c.label}</div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Active / latest jobs */}
      {(activeJobs.length > 0 || lastJob) && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold d-flex justify-content-between">
            <span><i className="bi bi-list-task me-2" />Download Queue</span>
            {lastJob && (
              <span className="small text-muted">
                Latest: {lastJob.job_type} · {new Date(lastJob.updated_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="card-body">
            {activeJobs.length === 0 && <div className="small text-muted">No active jobs.</div>}
            {activeJobs.map((j) => (
              <div className="mb-3" key={j.id}>
                <div className="small text-muted mb-1">
                  Job #{j.id} · {j.job_type} · {j.processed}/{j.total || "?"}
                </div>
                <JobProgress job={{ ...j, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card border-0 shadow-sm mb-3">
        <div className="card-body">
          <div className="row g-2 align-items-end">
            <div className="col-12 col-md-3">
              <label className="form-label small mb-1">Search</label>
              <input
                className="form-control form-control-sm"
                placeholder="Title, subject, code"
                value={search}
                onChange={(e) => { setPage(0); setSearch(e.target.value); }}
              />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">Class</label>
              <select className="form-select form-select-sm" value={classLevel} onChange={(e) => { setPage(0); setClassLevel(e.target.value); }}>
                <option value="">All</option>
                {facets.classes.map((c) => <option key={c} value={c}>Class {c}</option>)}
              </select>
            </div>
            <div className="col-6 col-md-3">
              <label className="form-label small mb-1">Subject</label>
              <select className="form-select form-select-sm" value={subject} onChange={(e) => { setPage(0); setSubject(e.target.value); }}>
                <option value="">All</option>
                {facets.subjects.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">Language</label>
              <select className="form-select form-select-sm" value={language} onChange={(e) => { setPage(0); setLanguage(e.target.value); }}>
                <option value="">All</option>
                {facets.languages.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">Status</label>
              <select className="form-select form-select-sm" value={status} onChange={(e) => { setPage(0); setStatus(e.target.value); }}>
                <option value="">All</option>
                {facets.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="d-flex justify-content-between align-items-center mt-3">
            <span className="small text-muted">{total} books · {selected.size} selected</span>
            <div className="d-flex gap-2">
              <button className="btn btn-sm btn-outline-secondary" onClick={resetFilters}>Reset</button>
              {canExecute && (
                <button className="btn btn-sm btn-primary" disabled={busy || selected.size === 0} onClick={downloadSelected}>
                  <i className="bi bi-download me-1" />
                  Download Selected ({selected.size})
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Book table */}
      <div className="card border-0 shadow-sm">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th style={{ width: 36 }}>
                  <input type="checkbox" className="form-check-input" onChange={toggleAll}
                    checked={books.filter((b) => !b.downloaded).length > 0 && books.filter((b) => !b.downloaded).every((b) => selected.has(b.id))} />
                </th>
                <th>Class</th>
                <th>Subject</th>
                <th>Title</th>
                <th>Part</th>
                <th>Language</th>
                <th>Status</th>
                <th>Size</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {books.length === 0 && (
                <tr><td colSpan={9} className="text-center text-muted py-4">
                  No books. Click <strong>Scan Website</strong> to discover NCERT books.
                </td></tr>
              )}
              {books.map((b) => (
                <tr key={b.id}>
                  <td>
                    <input type="checkbox" className="form-check-input" disabled={b.downloaded}
                      checked={selected.has(b.id)} onChange={() => toggle(b.id)} />
                  </td>
                  <td className="text-nowrap">{b.class_label.replace("Class ", "")}</td>
                  <td>{b.subject}</td>
                  <td>
                    {b.title}
                    <div className="text-muted" style={{ fontSize: "0.72rem" }}>{b.book_code}</div>
                  </td>
                  <td>{b.part || "—"}</td>
                  <td>{b.language}</td>
                  <td><span className={`badge ${STATUS_BADGE[b.status] ?? "bg-secondary"}`}>{b.status.replace("_", " ")}</span></td>
                  <td className="text-nowrap">{fmtSize(b.file_size)}</td>
                  <td className="text-end text-nowrap">
                    {canExecute && (b.status === "failed" || b.status === "update_available") && (
                      <button className="btn btn-sm btn-outline-primary me-1" disabled={busy} onClick={() => retry(b.id)} title="Download / Retry">
                        <i className="bi bi-arrow-clockwise" />
                      </button>
                    )}
                    {canDelete && b.downloaded && (
                      <button className="btn btn-sm btn-outline-danger" disabled={busy} onClick={() => removeDownload(b.id)} title="Delete download">
                        <i className="bi bi-trash" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {total > PAGE_SIZE && (
          <div className="card-footer bg-white d-flex justify-content-between align-items-center">
            <span className="small text-muted">Page {page + 1} of {totalPages}</span>
            <div className="btn-group btn-group-sm">
              <button className="btn btn-outline-secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                <i className="bi bi-chevron-left" />
              </button>
              <button className="btn btn-outline-secondary" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
                <i className="bi bi-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
