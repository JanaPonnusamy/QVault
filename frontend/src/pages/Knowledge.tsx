import { useCallback, useEffect, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../branding/BrandingContext";
import { getModuleColor } from "../modules";
import type {
  KnowledgeNodeDetail,
  KnowledgeSearchResult,
  KnowledgeStats,
  KnowledgeTreeNode,
  MappedDocument,
} from "../types";

const NODE_ICON: Record<string, string> = {
  root: "bi-file-earmark-text",
  section: "bi-folder",
  paragraph: "bi-text-paragraph",
  table: "bi-table",
  figure: "bi-image",
};

export default function Knowledge() {
  const { can } = useAuth();
  const { branding } = useBranding();
  const canExecute = can("knowledge:execute");

  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [docs, setDocs] = useState<MappedDocument[]>([]);
  const [docId, setDocId] = useState<number | null>(null);
  const [tree, setTree] = useState<KnowledgeTreeNode | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<KnowledgeNodeDetail | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadDocs = useCallback(async () => {
    const [s, d] = await Promise.all([
      api.get<KnowledgeStats>("/api/knowledge/stats"),
      api.get<MappedDocument[]>("/api/knowledge/documents"),
    ]);
    setStats(s.data);
    setDocs(d.data);
    setDocId((prev) => prev ?? (d.data[0]?.id ?? null));
  }, []);

  const loadTree = useCallback(async (id: number) => {
    try {
      const res = await api.get<KnowledgeTreeNode>(`/api/knowledge/documents/${id}/tree`);
      setTree(res.data);
      setExpanded(new Set([res.data.id, ...res.data.children.map((c) => c.id)]));
      setSelectedId(res.data.id);
    } catch (e) {
      setTree(null);
      setError(apiError(e));
    }
  }, []);

  useEffect(() => {
    loadDocs().catch((e) => setError(apiError(e)));
  }, [loadDocs]);

  useEffect(() => {
    if (docId != null) {
      setResults(null);
      setQuery("");
      loadTree(docId);
    }
  }, [docId, loadTree]);

  useEffect(() => {
    if (selectedId == null) return;
    api.get<KnowledgeNodeDetail>(`/api/knowledge/nodes/${selectedId}`)
      .then((r) => setDetail(r.data))
      .catch((e) => setError(apiError(e)));
  }, [selectedId]);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || docId == null) return;
    try {
      const res = await api.get<KnowledgeSearchResult[]>("/api/knowledge/search", {
        params: { q: query, document_id: docId },
      });
      setResults(res.data);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function remap() {
    if (docId == null) return;
    setBusy(true);
    try {
      await api.post(`/api/knowledge/documents/${docId}/remap`);
      await loadDocs();
      await loadTree(docId);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const cards = [
    { label: "Mapped Docs", value: stats?.mapped_documents ?? 0, icon: "bi-files", color: getModuleColor("knowledge", branding) },
    { label: "Nodes", value: stats?.nodes ?? 0, icon: "bi-diagram-3", color: getModuleColor("knowledge", branding) },
    { label: "Sections", value: stats?.sections ?? 0, icon: "bi-folder", color: "#0d9488" },
    { label: "Paragraphs", value: stats?.paragraphs ?? 0, icon: "bi-text-paragraph", color: "#16a34a" },
    { label: "Tables", value: stats?.tables ?? 0, icon: "bi-table", color: "#d97706" },
    { label: "Figures", value: stats?.figures ?? 0, icon: "bi-image", color: "#dc2626" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-diagram-3 text-primary me-2" />
          Knowledge Explorer
        </h3>
        <div className="d-flex gap-2 align-items-center">
          <select className="form-select form-select-sm" style={{ maxWidth: 320 }}
            value={docId ?? ""} onChange={(e) => setDocId(e.target.value ? Number(e.target.value) : null)}>
            {docs.length === 0 && <option value="">No mapped documents</option>}
            {docs.map((d) => <option key={d.id} value={d.id}>{d.title} ({d.node_count})</option>)}
          </select>
          {canExecute && docId != null && (
            <button className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={remap}>
              <i className="bi bi-arrow-repeat me-1" />Remap
            </button>
          )}
        </div>
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

      {docs.length === 0 ? (
        <div className="card border-0 shadow-sm">
          <div className="card-body text-center text-muted py-5">
            No knowledge maps yet. Process a PDF in <strong>Documents</strong> — its structure is mapped automatically.
          </div>
        </div>
      ) : (
        <div className="row g-3">
          {/* Tree */}
          <div className="col-12 col-lg-5">
            <div className="card border-0 shadow-sm">
              <div className="card-header bg-white">
                <form onSubmit={runSearch} className="input-group input-group-sm">
                  <span className="input-group-text bg-white"><i className="bi bi-search" /></span>
                  <input className="form-control" placeholder="Search this document..." value={query}
                    onChange={(e) => setQuery(e.target.value)} />
                  {results != null && (
                    <button type="button" className="btn btn-outline-secondary" onClick={() => setResults(null)}>Clear</button>
                  )}
                </form>
              </div>
              <div className="card-body" style={{ maxHeight: 560, overflowY: "auto" }}>
                {results != null ? (
                  <>
                    <div className="small text-muted mb-2">{results.length} result(s)</div>
                    {results.map((r) => (
                      <button key={r.id} className="btn btn-sm btn-light w-100 text-start mb-1"
                        onClick={() => { setSelectedId(r.id); }}>
                        <i className={`bi ${NODE_ICON[r.node_type]} me-2`} />
                        <span className="fw-medium">{r.title}</span>
                        <div className="small text-muted text-truncate">{r.breadcrumb.join(" › ")}</div>
                      </button>
                    ))}
                  </>
                ) : tree ? (
                  <TreeNodeView node={tree} expanded={expanded} selectedId={selectedId}
                    onToggle={toggle} onSelect={setSelectedId} />
                ) : (
                  <div className="text-muted small">No map.</div>
                )}
              </div>
            </div>
          </div>

          {/* Detail */}
          <div className="col-12 col-lg-7">
            <div className="card border-0 shadow-sm">
              <div className="card-body" style={{ minHeight: 300 }}>
                {!detail ? (
                  <div className="text-muted text-center py-5">Select a node to inspect.</div>
                ) : (
                  <NodeDetailView detail={detail} onSelect={setSelectedId} />
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TreeNodeView({
  node, expanded, selectedId, onToggle, onSelect,
}: {
  node: KnowledgeTreeNode;
  expanded: Set<number>;
  selectedId: number | null;
  onToggle: (id: number) => void;
  onSelect: (id: number) => void;
}) {
  const hasChildren = node.children.length > 0;
  const isOpen = expanded.has(node.id);
  return (
    <div>
      <div
        className={`d-flex align-items-center gap-1 py-1 px-1 rounded ${selectedId === node.id ? "bg-primary-subtle" : ""}`}
        style={{ cursor: "pointer", paddingLeft: node.depth * 14 }}
        onClick={() => onSelect(node.id)}
      >
        {hasChildren ? (
          <i className={`bi ${isOpen ? "bi-caret-down-fill" : "bi-caret-right-fill"} text-muted`}
            style={{ fontSize: "0.7rem" }} onClick={(e) => { e.stopPropagation(); onToggle(node.id); }} />
        ) : <span style={{ width: 12 }} />}
        <i className={`bi ${NODE_ICON[node.node_type] ?? "bi-dot"} text-secondary`} />
        <span className="small text-truncate">{node.title}</span>
        {hasChildren && <span className="badge bg-light text-muted ms-auto">{node.children.length}</span>}
      </div>
      {isOpen && node.children.map((c) => (
        <TreeNodeView key={c.id} node={c} expanded={expanded} selectedId={selectedId} onToggle={onToggle} onSelect={onSelect} />
      ))}
    </div>
  );
}

function NodeDetailView({ detail, onSelect }: { detail: KnowledgeNodeDetail; onSelect: (id: number) => void }) {
  return (
    <div>
      {detail.breadcrumb.length > 0 && (
        <nav className="mb-2">
          <ol className="breadcrumb mb-0 small">
            {detail.breadcrumb.map((b) => (
              <li key={b.id} className="breadcrumb-item">
                <button className="btn btn-link btn-sm p-0 text-decoration-none" onClick={() => onSelect(b.id)}>{b.title}</button>
              </li>
            ))}
            <li className="breadcrumb-item active text-truncate" style={{ maxWidth: 220 }}>{detail.title}</li>
          </ol>
        </nav>
      )}
      <div className="d-flex align-items-center gap-2 mb-3">
        <span className="badge bg-secondary text-uppercase">{detail.node_type}</span>
        {detail.level != null && <span className="badge bg-light text-dark">level {detail.level}</span>}
        {detail.page > 0 && <span className="badge bg-light text-dark">page {detail.page}</span>}
      </div>
      <h5 className="fw-bold">{detail.title}</h5>

      {detail.node_type === "table" && detail.extra?.rows && (
        <table className="table table-sm table-bordered mt-2">
          <tbody>
            {detail.extra.rows.map((row, i) => (
              <tr key={i}>{row.map((c, j) => <td key={j}>{c}</td>)}</tr>
            ))}
          </tbody>
        </table>
      )}
      {detail.node_type === "figure" && (
        <div className="border rounded d-inline-flex flex-column align-items-center justify-content-center text-muted mt-2"
          style={{ width: 160, height: 110, background: "#f8f9fa" }}>
          <i className="bi bi-image" style={{ fontSize: "1.8rem" }} />
          <span className="small mt-1">{detail.extra?.width}×{detail.extra?.height}</span>
        </div>
      )}
      {detail.content && <p className="mt-2" style={{ whiteSpace: "pre-wrap" }}>{detail.content}</p>}

      {detail.children.length > 0 && (
        <div className="mt-3">
          <div className="small text-uppercase fw-semibold text-muted mb-2">Children ({detail.children.length})</div>
          {detail.children.map((c) => (
            <button key={c.id} className="btn btn-sm btn-light w-100 text-start mb-1" onClick={() => onSelect(c.id)}>
              <i className={`bi ${NODE_ICON[c.node_type] ?? "bi-dot"} me-2`} />{c.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
