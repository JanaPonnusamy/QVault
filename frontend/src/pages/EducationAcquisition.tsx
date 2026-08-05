import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import JobProgress from "../components/JobProgress";
import type {
  AcquisitionJob,
  EducationDocument,
  EducationDocumentDetail,
  EducationDocumentList,
  EducationFieldCatalog,
  EducationFieldCoverage,
  EducationSource,
  EducationSourceList,
  EducationStats,
} from "../types";

const PROVIDERS = [
  { key: "manual_url", label: "Manual URLs" },
  { key: "sitemap", label: "Sitemap" },
  { key: "website_crawl", label: "Website Crawl" },
  { key: "pdf_discovery", label: "PDF Discovery" },
  { key: "document_discovery", label: "Document Discovery" },
  { key: "government_portal", label: "Government Portal" },
  { key: "rss", label: "RSS" },
  { key: "duckduckgo", label: "DuckDuckGo" },
  { key: "bing", label: "Bing" },
  { key: "google", label: "Google" },
] as const;

const DEFAULT_QUERIES = [
  "site:edu.in admission form",
  "site:school admission form india",
  "site:school prospectus india",
  "site:school fee structure india",
  "site:school academic calendar india",
  "filetype:pdf school handbook india",
  "filetype:pdf transfer certificate form school india",
].join("\n");

export default function EducationAcquisition() {
  const { can } = useAuth();
  const canExecute = can("education_acquisition:execute");
  const canExport = can("education_acquisition:export");

  const [queries, setQueries] = useState(DEFAULT_QUERIES);
  const [rootUrls, setRootUrls] = useState("https://www.cbse.gov.in\nhttps://www.education.gov.in");
  const [manualUrls, setManualUrls] = useState("");
  const [rssUrls, setRssUrls] = useState("");
  const [governmentUrls, setGovernmentUrls] = useState("https://www.cbse.gov.in\nhttps://www.education.gov.in");
  const [selectedProviders, setSelectedProviders] = useState<string[]>([
    "sitemap", "website_crawl", "pdf_discovery", "document_discovery", "government_portal", "duckduckgo",
  ]);
  const [jobs, setJobs] = useState<AcquisitionJob[]>([]);
  const [stats, setStats] = useState<EducationStats>({ sources: 0, documents: 0, fields: 0, forms: 0 });
  const [fieldCatalog, setFieldCatalog] = useState<EducationFieldCatalog>({ enquiry_fields: [], application_fields: [], notes: [] });
  const [sources, setSources] = useState<EducationSource[]>([]);
  const [documents, setDocuments] = useState<EducationDocument[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<EducationDocumentDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<number | null>(null);

  const activeJobs = useMemo(() => jobs.filter((j) => ["queued", "scanning", "downloading"].includes(j.status)), [jobs]);

  const loadJobs = useCallback(async () => {
    const res = await api.get<AcquisitionJob[]>("/api/sources/education/jobs");
    setJobs(res.data);
    return res.data;
  }, []);

  const loadStats = useCallback(async () => {
    const res = await api.get<EducationStats>("/api/sources/education/stats");
    setStats(res.data);
  }, []);

  const loadFieldCatalog = useCallback(async () => {
    const res = await api.get<EducationFieldCatalog>("/api/sources/education/field-catalog");
    setFieldCatalog(res.data);
  }, []);

  const loadSources = useCallback(async () => {
    const res = await api.get<EducationSourceList>("/api/sources/education/sources", { params: { limit: 10, offset: 0 } });
    setSources(res.data.items);
  }, []);

  const loadDocuments = useCallback(async () => {
    const res = await api.get<EducationDocumentList>("/api/sources/education/documents", { params: { limit: 25, offset: 0 } });
    setDocuments(res.data.items);
  }, []);

  const loadDocument = useCallback(async (documentId: string) => {
    const res = await api.get<EducationDocumentDetail>(`/api/sources/education/documents/${documentId}`);
    setSelectedDocument(res.data);
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadJobs(), loadStats(), loadFieldCatalog(), loadSources(), loadDocuments()]);
  }, [loadJobs, loadStats, loadFieldCatalog, loadSources, loadDocuments]);

  const startPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const currentJobs = await loadJobs();
      await Promise.all([loadStats(), loadFieldCatalog(), loadSources(), loadDocuments()]);
      const active = currentJobs.some((j) => ["queued", "scanning", "downloading"].includes(j.status));
      if (!active && pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    tick().catch((e) => setError(apiError(e)));
    pollRef.current = window.setInterval(() => {
      tick().catch((e) => setError(apiError(e)));
    }, 3000);
  }, [loadDocuments, loadFieldCatalog, loadJobs, loadSources, loadStats]);

  useEffect(() => {
    refreshAll().then(() => {
      if (activeJobs.length) startPolling();
    }).catch((e) => setError(apiError(e)));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runScan() {
    setBusy(true);
    setError("");
    try {
      await api.post("/api/sources/education/scan", {
        queries: splitLines(queries),
        root_urls: splitLines(rootUrls),
        manual_urls: splitLines(manualUrls),
        rss_urls: splitLines(rssUrls),
        government_urls: splitLines(governmentUrls),
        providers: selectedProviders,
        max_pages_per_root: 40,
        max_search_results: 25,
      });
      startPolling();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function exportAs(format: "json" | "csv" | "markdown" | "sqlite") {
    window.open(`${api.defaults.baseURL}/api/sources/education/export?format=${format}`, "_blank");
  }

  function toggleProvider(providerKey: string) {
    setSelectedProviders((current) => (
      current.includes(providerKey) ? current.filter((item) => item !== providerKey) : [...current, providerKey]
    ));
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <div>
          <h3 className="fw-bold mb-1">
            <i className="bi bi-buildings text-success me-2" />
            Education Knowledge
          </h3>
          <p className="text-muted small mb-0">
            Public-web knowledge acquisition for Indian school, college, university, board, and government education content.
          </p>
        </div>
        {canExport && (
          <div className="btn-group">
            <button className="btn btn-outline-secondary btn-sm dropdown-toggle" data-bs-toggle="dropdown">
              <i className="bi bi-download me-1" />
              Export
            </button>
            <ul className="dropdown-menu dropdown-menu-end">
              <li><button className="dropdown-item" onClick={() => exportAs("json")}>JSON</button></li>
              <li><button className="dropdown-item" onClick={() => exportAs("csv")}>CSV</button></li>
              <li><button className="dropdown-item" onClick={() => exportAs("markdown")}>Markdown</button></li>
              <li><button className="dropdown-item" onClick={() => exportAs("sqlite")}>SQLite</button></li>
            </ul>
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
        <StatCard label="Sources" value={stats.sources} icon="bi-buildings" />
        <StatCard label="Documents" value={stats.documents} icon="bi-file-earmark-text" />
        <StatCard label="Fields" value={stats.fields} icon="bi-tags" />
        <StatCard label="Forms" value={stats.forms} icon="bi-ui-checks-grid" />
      </div>

      <div className="card border-0 shadow-sm mb-3">
        <div className="card-header bg-white fw-semibold">Admission Field Blueprint</div>
        <div className="card-body">
          <div className="row g-3">
            <div className="col-lg-4">
              <div className="small fw-semibold mb-2">Enquiry Stage</div>
              <FieldBlueprintList fields={fieldCatalog.enquiry_fields} />
            </div>
            <div className="col-lg-8">
              <div className="small fw-semibold mb-2">Application Stage</div>
              <FieldBlueprintList fields={fieldCatalog.application_fields} />
            </div>
          </div>
          {fieldCatalog.notes.length > 0 && (
            <div className="alert alert-light border mt-3 mb-0 small">
              {fieldCatalog.notes.map((note) => (
                <div key={note}>{note}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      {canExecute && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">New Scan</div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-lg-6">
                <label className="form-label small fw-semibold">Search Queries</label>
                <textarea className="form-control" rows={8} value={queries} onChange={(e) => setQueries(e.target.value)} />
              </div>
              <div className="col-lg-6">
                <label className="form-label small fw-semibold">Root URLs</label>
                <textarea className="form-control mb-3" rows={3} value={rootUrls} onChange={(e) => setRootUrls(e.target.value)} />
                <label className="form-label small fw-semibold">Government URLs</label>
                <textarea className="form-control mb-3" rows={3} value={governmentUrls} onChange={(e) => setGovernmentUrls(e.target.value)} />
                <label className="form-label small fw-semibold">Manual URLs / RSS URLs</label>
                <div className="row g-2">
                  <div className="col-md-6">
                    <textarea className="form-control" rows={3} placeholder="Manual URLs" value={manualUrls} onChange={(e) => setManualUrls(e.target.value)} />
                  </div>
                  <div className="col-md-6">
                    <textarea className="form-control" rows={3} placeholder="RSS URLs" value={rssUrls} onChange={(e) => setRssUrls(e.target.value)} />
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <div className="small fw-semibold mb-2">Providers</div>
              <div className="d-flex flex-wrap gap-3">
                {PROVIDERS.map((provider) => (
                  <label className="form-check-label small" key={provider.key}>
                    <input
                      className="form-check-input me-2"
                      type="checkbox"
                      checked={selectedProviders.includes(provider.key)}
                      onChange={() => toggleProvider(provider.key)}
                    />
                    {provider.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="mt-3">
              <button className="btn btn-primary" disabled={busy || selectedProviders.length === 0} onClick={runScan}>
                <i className="bi bi-play-circle me-1" />
                Start Education Scan
              </button>
            </div>
          </div>
        </div>
      )}

      {(activeJobs.length > 0 || jobs[0]) && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">Jobs</div>
          <div className="card-body">
            {jobs.slice(0, 5).map((job) => (
              <div className="mb-3" key={job.id}>
                <div className="small text-muted mb-1">
                  Job #{job.id} · {job.status} · {job.processed}/{job.total || "?"}
                </div>
                <JobProgress job={{ ...job, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="row g-3">
        <div className="col-lg-4">
          <div className="card border-0 shadow-sm h-100">
            <div className="card-header bg-white fw-semibold">Institutions</div>
            <div className="list-group list-group-flush">
              {sources.length === 0 && <div className="p-3 small text-muted">No sources yet.</div>}
              {sources.map((source: EducationSource) => (
                <button key={source.id} className="list-group-item list-group-item-action">
                  <div className="fw-semibold">{source.institution_name || source.source_key}</div>
                  <div className="small text-muted">{source.institution_type || "education"} · {source.board || "unclassified"} · {source.state || "unknown state"}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="col-lg-8">
          <div className="card border-0 shadow-sm mb-3">
            <div className="card-header bg-white fw-semibold">Documents</div>
            <div className="table-responsive">
              <table className="table table-sm mb-0 align-middle">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.length === 0 && (
                    <tr><td colSpan={3} className="text-center py-3 text-muted small">No documents yet.</td></tr>
                  )}
                  {documents.map((document: EducationDocument) => (
                    <tr key={document.id} role="button" onClick={() => loadDocument(document.id).catch((e) => setError(apiError(e)))}>
                      <td className="small">
                        <div className="fw-semibold">{document.title || document.url}</div>
                        <div className="text-muted text-break">{document.url}</div>
                      </td>
                      <td className="small">
                        <span className="badge bg-light text-dark border">{document.classification || document.document_type}</span>
                      </td>
                      <td className="small text-muted">{new Date(document.updated_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card border-0 shadow-sm">
            <div className="card-header bg-white fw-semibold">Document Detail</div>
            <div className="card-body">
              {!selectedDocument && <div className="small text-muted">Select a document to inspect normalized fields and tags.</div>}
              {selectedDocument && (
                <>
                  <div className="mb-3">
                    <div className="fw-semibold">{selectedDocument.title}</div>
                    <div className="small text-muted text-break">{selectedDocument.url}</div>
                    <div className="small mt-2">{selectedDocument.summary || "No summary extracted."}</div>
                    <div className="mt-2 d-flex flex-wrap gap-2">
                      {selectedDocument.tags.map((tag) => <span className="badge bg-light text-dark border" key={tag}>{tag}</span>)}
                    </div>
                  </div>
                  <div className="row g-3 mb-3">
                    <div className="col-lg-5">
                      <div className="border rounded p-3 h-100">
                        <div className="fw-semibold small mb-2">Enquiry Coverage</div>
                        <FieldCoverageTable
                          fields={selectedDocument.field_summary.enquiry_fields}
                          missing={selectedDocument.field_summary.missing_required_enquiry}
                        />
                      </div>
                    </div>
                    <div className="col-lg-7">
                      <div className="border rounded p-3 h-100">
                        <div className="fw-semibold small mb-2">Application Coverage</div>
                        <FieldCoverageTable
                          fields={selectedDocument.field_summary.application_fields}
                          missing={selectedDocument.field_summary.missing_required_application}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="row g-3 mb-3">
                    <div className="col-lg-6">
                      <div className="border rounded p-3 h-100">
                        <div className="fw-semibold small mb-2">Custom School Fields</div>
                        {selectedDocument.field_summary.custom_fields.length === 0 ? (
                          <div className="small text-muted">No extra custom fields yet.</div>
                        ) : (
                          <div className="table-responsive">
                            <table className="table table-sm mb-0">
                              <thead>
                                <tr>
                                  <th>Field</th>
                                  <th>Value</th>
                                  <th>Source</th>
                                </tr>
                              </thead>
                              <tbody>
                                {selectedDocument.field_summary.custom_fields.map((field) => (
                                  <tr key={`${field.key}-${field.label}`}>
                                    <td className="small">{field.label}</td>
                                    <td className="small text-break">{field.value || "-"}</td>
                                    <td className="small text-muted">{field.source_kind}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="col-lg-6">
                      <div className="border rounded p-3 h-100">
                        <div className="fw-semibold small mb-2">Metadata Preserved</div>
                        {selectedDocument.field_summary.raw_metadata_fields.length === 0 ? (
                          <div className="small text-muted">No extra metadata preserved.</div>
                        ) : (
                          <div className="table-responsive">
                            <table className="table table-sm mb-0">
                              <thead>
                                <tr>
                                  <th>Key</th>
                                  <th>Value</th>
                                </tr>
                              </thead>
                              <tbody>
                                {selectedDocument.field_summary.raw_metadata_fields.map((field) => (
                                  <tr key={field.key}>
                                    <td className="small">{field.key}</td>
                                    <td className="small text-break">{field.value}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Value</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedDocument.fields.length === 0 && (
                          <tr><td colSpan={3} className="text-muted small">No normalized fields extracted yet.</td></tr>
                        )}
                        {selectedDocument.fields.map((field) => (
                          <tr key={field.id}>
                            <td className="small">{field.canonical_key}</td>
                            <td className="small text-break">{field.value}</td>
                            <td className="small text-muted">{field.source_kind}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldBlueprintList({ fields }: { fields: EducationFieldCatalog["enquiry_fields"] }) {
  return (
    <div className="table-responsive">
      <table className="table table-sm mb-0">
        <thead>
          <tr>
            <th>Field</th>
            <th>Req.</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field.key}>
              <td className="small">
                <div className="fw-semibold">{field.label}</div>
                <div className="text-muted">{field.description}</div>
              </td>
              <td className="small">{field.required ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FieldCoverageTable({ fields, missing }: { fields: EducationFieldCoverage[]; missing: string[] }) {
  return (
    <>
      {missing.length > 0 && (
        <div className="alert alert-warning py-2 small">
          Missing required: {missing.join(", ")}
        </div>
      )}
      <div className="table-responsive">
        <table className="table table-sm mb-0">
          <thead>
            <tr>
              <th>Field</th>
              <th>Present</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field.key}>
                <td className="small">{field.label}</td>
                <td className="small">{field.present ? "Yes" : "No"}</td>
                <td className="small text-break">
                  {field.values.length > 0 ? field.values.map((item) => item.value || item.label).join(", ") : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function splitLines(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: string }) {
  return (
    <div className="col-6 col-xl-3">
      <div className="card border-0 shadow-sm h-100">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-start">
            <div>
              <div className="text-muted small">{label}</div>
              <div className="fs-4 fw-bold">{value}</div>
            </div>
            <i className={`bi ${icon} text-secondary`} />
          </div>
        </div>
      </div>
    </div>
  );
}
