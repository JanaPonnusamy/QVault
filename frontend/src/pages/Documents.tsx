import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../branding/BrandingContext";
import JobProgress from "../components/JobProgress";
import { getModuleColor } from "../modules";
import type { AcquisitionJob, DocItem, DocStats, DownloadedBook } from "../types";

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-secondary",
  processing: "bg-info",
  processed: "bg-success",
  failed: "bg-danger",
};

const PAGE_SIZE = 25;

export default function Documents() {
  const { can } = useAuth();
  const { branding } = useBranding();
  const canExecute = can("documents:execute");
  const canDelete = can("documents:delete");

  const [stats, setStats] = useState<DocStats | null>(null);
  const [items, setItems] = useState<DocItem[]>([]);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState<AcquisitionJob[]>([]);
  const [ncertBooks, setNcertBooks] = useState<DownloadedBook[]>([]);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);

  const loadStats = useCallback(async () => {
    const s = await api.get<DocStats>("/api/documents/stats");
    setStats(s.data);
  }, []);

  const loadList = useCallback(async () => {
    try {
      const res = await api.get<{ items: DocItem[]; total: number }>("/api/documents", {
        params: { search: search || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
      });
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      setError(apiError(e));
    }
  }, [search, page]);

  const loadJobs = useCallback(async () => {
    const res = await api.get<AcquisitionJob[]>("/api/documents/jobs");
    setJobs(res.data);
    return res.data;
  }, []);

  const loadNcert = useCallback(async () => {
    try {
      const res = await api.get<DownloadedBook[]>("/api/documents/ncert-books");
      setNcertBooks(res.data);
    } catch {
      /* permission/empty */
    }
  }, []);

  useEffect(() => {
    loadStats().catch((e) => setError(apiError(e)));
    loadNcert();
  }, [loadStats, loadNcert]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const startPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const data = await loadJobs();
      loadStats();
      loadList();
      if (!data.some((j) => ["queued", "processing", "scanning", "downloading"].includes(j.status))) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2000);
  }, [loadJobs, loadStats, loadList]);

  useEffect(() => {
    loadJobs().then((data) => {
      if (data.some((j) => ["queued", "processing"].includes(j.status))) startPolling();
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [loadJobs, startPolling]);

  async function run(fn: () => Promise<unknown>) {
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

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await run(() => api.post("/api/documents/upload", form));
    if (fileRef.current) fileRef.current.value = "";
  }

  const importNcert = (bookId: number) =>
    run(() => api.post("/api/documents/import/ncert", { book_id: bookId }));
  const reprocess = (id: number) => run(() => api.post(`/api/documents/${id}/reprocess`));
  const remove = (id: number) => {
    if (!confirm("Delete this document and its structure?")) return;
    run(() => api.delete(`/api/documents/${id}`));
  };

  const activeJobs = jobs.filter((j) => ["queued", "processing"].includes(j.status));
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const cards = [
    { label: "Documents", value: stats?.total ?? 0, icon: "bi-files", color: getModuleColor("documents", branding) },
    { label: "Processed", value: stats?.processed ?? 0, icon: "bi-check-circle", color: "#16a34a" },
    { label: "Pending", value: stats?.pending ?? 0, icon: "bi-hourglass-split", color: "#d97706" },
    { label: "Failed", value: stats?.failed ?? 0, icon: "bi-x-circle", color: "#dc2626" },
    { label: "Needs OCR", value: stats?.needs_ocr ?? 0, icon: "bi-eye", color: "#9333ea" },
    { label: "Elements", value: stats?.elements ?? 0, icon: "bi-diagram-3", color: "#0d9488" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-file-earmark-text text-info me-2" />
          Knowledge Extraction
        </h3>
        {canExecute && (
          <div className="d-flex gap-2">
            <input ref={fileRef} type="file" accept="application/pdf" className="d-none" onChange={onUpload} />
            <button className="btn btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>
              <i className="bi bi-upload me-1" />
              Upload PDF
            </button>
            {ncertBooks.length > 0 && (
              <div className="dropdown">
                <button className="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown" disabled={busy}>
                  <i className="bi bi-journal-arrow-down me-1" />
                  Import NCERT
                </button>
                <ul className="dropdown-menu dropdown-menu-end" style={{ maxHeight: 320, overflowY: "auto" }}>
                  {ncertBooks.map((b) => (
                    <li key={b.id}>
                      <button className="dropdown-item small" onClick={() => importNcert(b.id)}>
                        {b.class_label} · {b.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
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
          <div className="col-6 col-md-4 col-xl-2" key={c.label}>
            <div className="card border-0 shadow-sm h-100">
              <div className="card-body d-flex align-items-center gap-3">
                <div className="qv-module-icon mb-0" style={{ background: c.color, width: 40, height: 40, fontSize: "1.1rem" }}>
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

      {activeJobs.length > 0 && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">
            <i className="bi bi-gear-wide-connected me-2" />Extraction Queue
          </div>
          <div className="card-body">
            {activeJobs.map((j) => (
              <div className="mb-2" key={j.id}>
                <div className="small text-muted mb-1">Job #{j.id} · {j.processed}/{j.total}</div>
                <JobProgress job={{ ...j, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card border-0 shadow-sm">
        <div className="card-header bg-white">
          <div className="input-group input-group-sm" style={{ maxWidth: 360 }}>
            <span className="input-group-text bg-white"><i className="bi bi-search" /></span>
            <input className="form-control" placeholder="Search documents..." value={search}
              onChange={(e) => { setPage(0); setSearch(e.target.value); }} />
          </div>
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Pages</th>
                <th>Text Layer</th>
                <th>Status</th>
                <th>Elements</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={7} className="text-center text-muted py-4">
                  No documents. Upload a PDF or import a downloaded NCERT book.
                </td></tr>
              )}
              {items.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link to={`/documents/${d.id}`} className="text-decoration-none fw-medium">{d.title}</Link>
                  </td>
                  <td><span className="badge bg-light text-dark text-uppercase">{d.source}</span></td>
                  <td>{d.page_count || "—"}</td>
                  <td>
                    {d.status === "processed" ? (
                      d.has_text_layer
                        ? <span className="badge bg-success">text</span>
                        : <span className="badge bg-warning text-dark">needs OCR</span>
                    ) : "—"}
                  </td>
                  <td><span className={`badge ${STATUS_BADGE[d.status] ?? "bg-secondary"}`}>{d.status}</span></td>
                  <td>{d.element_count}</td>
                  <td className="text-end text-nowrap">
                    <Link to={`/documents/${d.id}`} className="btn btn-sm btn-outline-primary me-1" title="View structure">
                      <i className="bi bi-eye" />
                    </Link>
                    {canExecute && (
                      <button className="btn btn-sm btn-outline-secondary me-1" disabled={busy} onClick={() => reprocess(d.id)} title="Re-extract">
                        <i className="bi bi-arrow-clockwise" />
                      </button>
                    )}
                    {canDelete && (
                      <button className="btn btn-sm btn-outline-danger" disabled={busy} onClick={() => remove(d.id)} title="Delete">
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
