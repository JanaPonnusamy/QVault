import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { AssembledDocument, ContentBlock, DocDetail, DocElement } from "../types";

const TYPE_ICON: Record<string, string> = {
  heading: "bi-type-h1",
  paragraph: "bi-text-paragraph",
  table: "bi-table",
  figure: "bi-image",
};

export default function DocumentViewer() {
  const { id } = useParams();
  const docId = Number(id);
  const { can } = useAuth();
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [elements, setElements] = useState<DocElement[]>([]);
  const [assembled, setAssembled] = useState<AssembledDocument | null>(null);
  const [mode, setMode] = useState<"reader" | "developer">("reader");
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, e, a] = await Promise.all([
        api.get<DocDetail>(`/api/documents/${docId}`),
        api.get<DocElement[]>(`/api/documents/${docId}/elements`),
        api.get<AssembledDocument>(`/api/content/documents/${docId}`),
      ]);
      setDoc(d.data);
      setElements(e.data);
      setAssembled(a.data);
    } catch (err) {
      setError(apiError(err));
    }
  }, [docId]);

  useEffect(() => {
    load();
  }, [load]);

  async function reassemble() {
    setBusy(true);
    try {
      await api.post(`/api/content/documents/${docId}/assemble`);
      await load();
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!doc) return <div className="spinner-border text-primary" role="status" />;

  return (
    <div>
      <div className="d-flex justify-content-between align-items-start mb-3 flex-wrap gap-2">
        <div>
          <h3 className="fw-bold mb-1">{doc.title}</h3>
          <div className="small text-muted">
            <span className="badge bg-light text-dark text-uppercase me-2">{doc.source}</span>
            {doc.page_count} pages · {doc.element_count} raw elements ·{" "}
            {assembled ? <>{assembled.block_count} assembled blocks · </> : null}
            {doc.has_text_layer
              ? <span className="badge bg-success">embedded text</span>
              : <span className="badge bg-warning text-dark">no text layer — needs OCR</span>}
          </div>
        </div>
        <div className="d-flex align-items-center gap-2">
          <div className="btn-group btn-group-sm" role="group">
            <button className={`btn ${mode === "reader" ? "btn-primary" : "btn-outline-primary"}`} onClick={() => setMode("reader")}>
              <i className="bi bi-book me-1" />Reader
            </button>
            <button className={`btn ${mode === "developer" ? "btn-primary" : "btn-outline-primary"}`} onClick={() => setMode("developer")}>
              <i className="bi bi-braces me-1" />Developer
            </button>
          </div>
          <Link to="/documents" className="btn btn-outline-secondary btn-sm">
            <i className="bi bi-arrow-left me-1" />Back
          </Link>
        </div>
      </div>

      <div className="row g-3">
        {/* Bookmarks / outline */}
        <div className="col-12 col-lg-3">
          <div className="card border-0 shadow-sm">
            <div className="card-header bg-white fw-semibold">
              <i className="bi bi-bookmarks me-2" />Bookmarks
            </div>
            <div className="card-body" style={{ maxHeight: 560, overflowY: "auto" }}>
              {doc.bookmarks.length === 0 && <div className="text-muted small">No bookmarks in this PDF.</div>}
              {doc.bookmarks.map((b) => (
                <div key={b.id} style={{ paddingLeft: (b.level - 1) * 14 }} className="small py-1">
                  <i className="bi bi-dot" />
                  {b.title} <span className="text-muted">· p{b.page}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Main */}
        <div className="col-12 col-lg-9">
          {mode === "reader" ? (
            <ReaderView assembled={assembled} canExecute={can("content:execute")} busy={busy} onReassemble={reassemble} />
          ) : (
            <DeveloperView elements={elements} typeFilter={typeFilter} setTypeFilter={setTypeFilter} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------- Reader Mode: assembled, readable content ---------------- */

function ReaderView({
  assembled, canExecute, busy, onReassemble,
}: {
  assembled: AssembledDocument | null;
  canExecute: boolean;
  busy: boolean;
  onReassemble: () => void;
}) {
  if (!assembled || assembled.sections.length === 0) {
    return (
      <div className="card border-0 shadow-sm">
        <div className="card-body text-center text-muted py-5">
          No assembled content yet.
          {canExecute && (
            <div className="mt-3">
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={onReassemble}>
                <i className="bi bi-magic me-1" />Assemble content
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="card border-0 shadow-sm">
      <div className="card-header bg-white d-flex justify-content-between align-items-center">
        <span className="fw-semibold"><i className="bi bi-book me-2" />Reader</span>
        {canExecute && (
          <button className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={onReassemble}>
            <i className="bi bi-arrow-repeat me-1" />Re-assemble
          </button>
        )}
      </div>
      <div className="card-body" style={{ maxHeight: 680, overflowY: "auto", maxWidth: 820 }}>
        {assembled.sections.map((section) => (
          <section key={section.id} className="mb-3">
            {section.level > 0 && (
              <Heading level={section.level} text={section.title} />
            )}
            {section.blocks.map((b) => <BlockView key={b.id} block={b} />)}
          </section>
        ))}
      </div>
    </div>
  );
}

function Heading({ level, text }: { level: number; text: string }) {
  const size = Math.max(1.0, 1.7 - level * 0.18);
  return <div className="fw-bold mt-3 mb-2" style={{ fontSize: `${size}rem` }}>{text}</div>;
}

function BlockView({ block }: { block: ContentBlock }) {
  if (block.block_type === "paragraph") {
    return <p className="mb-3" style={{ lineHeight: 1.7 }}>{block.text}</p>;
  }
  if (block.block_type === "example" || block.block_type === "exercise") {
    const isExample = block.block_type === "example";
    return (
      <div className={`border-start border-3 ${isExample ? "border-info" : "border-warning"} ps-3 py-2 mb-3 bg-light rounded`}>
        <div className="small fw-semibold text-uppercase text-muted mb-1">
          <i className={`bi ${isExample ? "bi-lightbulb" : "bi-pencil-square"} me-1`} />
          {block.block_type}
        </div>
        <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{block.text}</div>
      </div>
    );
  }
  if (block.block_type === "table") {
    const rows = block.extra?.rows ?? [];
    return (
      <div className="mb-3">
        <table className="table table-sm table-bordered">
          <tbody>
            {rows.map((row, i) => <tr key={i}>{row.map((c, j) => <td key={j}>{c}</td>)}</tr>)}
          </tbody>
        </table>
        {block.caption && <div className="small text-muted fst-italic">{block.caption}</div>}
      </div>
    );
  }
  if (block.block_type === "figure") {
    return (
      <figure className="text-center mb-3">
        <div className="border rounded d-inline-flex flex-column align-items-center justify-content-center text-muted"
          style={{ width: 200, height: 130, background: "#f8f9fa" }}>
          <i className="bi bi-image" style={{ fontSize: "2rem" }} />
          <span className="small mt-1">{block.extra?.width}×{block.extra?.height}</span>
        </div>
        {block.caption && <figcaption className="small text-muted fst-italic mt-1">{block.caption}</figcaption>}
      </figure>
    );
  }
  return null;
}

/* -------------- Developer Mode: raw extraction nodes (debug) -------------- */

function DeveloperView({
  elements, typeFilter, setTypeFilter,
}: {
  elements: DocElement[];
  typeFilter: string;
  setTypeFilter: (t: string) => void;
}) {
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of elements) c[e.element_type] = (c[e.element_type] ?? 0) + 1;
    return c;
  }, [elements]);

  const filtered = typeFilter ? elements.filter((e) => e.element_type === typeFilter) : elements;
  const pages = useMemo(() => {
    const map = new Map<number, DocElement[]>();
    for (const el of filtered) {
      if (!map.has(el.page)) map.set(el.page, []);
      map.get(el.page)!.push(el);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [filtered]);

  return (
    <div className="card border-0 shadow-sm">
      <div className="card-header bg-white d-flex gap-1 flex-wrap align-items-center">
        <span className="badge bg-secondary me-2">raw extraction</span>
        <button className={`btn btn-sm ${typeFilter === "" ? "btn-primary" : "btn-outline-secondary"}`} onClick={() => setTypeFilter("")}>
          All ({elements.length})
        </button>
        {["heading", "paragraph", "table", "figure"].map((t) => (
          <button key={t} className={`btn btn-sm ${typeFilter === t ? "btn-primary" : "btn-outline-secondary"}`} onClick={() => setTypeFilter(t)}>
            <i className={`bi ${TYPE_ICON[t]} me-1`} />{t} ({counts[t] ?? 0})
          </button>
        ))}
      </div>
      <div className="card-body" style={{ maxHeight: 660, overflowY: "auto" }}>
        {pages.length === 0 && <div className="text-muted small">No structural elements.</div>}
        {pages.map(([pageNo, els]) => (
          <div key={pageNo} className="mb-4">
            <div className="text-muted small text-uppercase fw-semibold border-bottom pb-1 mb-2">Page {pageNo}</div>
            {els.map((el) => <ElementView key={el.id} el={el} />)}
          </div>
        ))}
      </div>
    </div>
  );
}

function ElementView({ el }: { el: DocElement }) {
  if (el.element_type === "heading") {
    const size = Math.max(0.95, 1.5 - (el.level ?? 1) * 0.18);
    return (
      <div className="mb-2 d-flex align-items-center gap-2">
        <span className="badge bg-primary-subtle text-primary">H{el.level}</span>
        <span className="fw-bold" style={{ fontSize: `${size}rem` }}>{el.text}</span>
      </div>
    );
  }
  if (el.element_type === "paragraph") {
    return <p className="mb-2" style={{ whiteSpace: "pre-wrap" }}>{el.text}</p>;
  }
  if (el.element_type === "table") {
    const rows = el.extra?.rows ?? [];
    return (
      <div className="mb-3">
        <div className="small text-muted mb-1">
          <i className="bi bi-table me-1" />Table {el.extra?.n_rows}×{el.extra?.n_cols}
        </div>
        <table className="table table-sm table-bordered mb-0">
          <tbody>
            {rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
    );
  }
  if (el.element_type === "figure") {
    return (
      <div className="mb-3 border rounded d-inline-flex flex-column align-items-center justify-content-center text-muted"
        style={{ width: 160, height: 110, background: "#f8f9fa" }}>
        <i className="bi bi-image" style={{ fontSize: "1.8rem" }} />
        <span className="small mt-1">Figure {el.extra?.width}×{el.extra?.height}</span>
      </div>
    );
  }
  return null;
}
