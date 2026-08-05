import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import JobProgress from "../components/JobProgress";
import { addRemoteNode, getRemoteNodes, removeRemoteNode, type RemoteNode } from "../remoteNodes";
import type { AcquisitionJob, GkProfile, GkSiteReport, GkVisitedUrlList } from "../types";

const URL_PAGE_SIZE = 25;
const NODE_KEY = "qvault_selected_node";

function jobSiteLabel(job: AcquisitionJob): string {
  try {
    const parsed = JSON.parse(job.payload || "{}");
    const url = parsed.homepage_url as string | undefined;
    return url ? new URL(url).hostname : "";
  } catch {
    return "";
  }
}

function jobNodeLabel(job: AcquisitionJob): string {
  try {
    return JSON.parse(job.payload || "{}").node || "";
  } catch {
    return "";
  }
}

export default function GkScraper() {
  const { can } = useAuth();
  const canExecute = can("gk_scraper:execute");

  const [homepageUrl, setHomepageUrl] = useState("");
  const [jobs, setJobs] = useState<AcquisitionJob[]>([]);
  const [domains, setDomains] = useState<string[]>([]);
  const [selectedDomain, setSelectedDomain] = useState("");
  const [profile, setProfile] = useState<GkProfile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<number | null>(null);

  const [urlList, setUrlList] = useState<GkVisitedUrlList | null>(null);
  const [urlStatus, setUrlStatus] = useState("");
  const [urlPage, setUrlPage] = useState(0);
  const [siteReports, setSiteReports] = useState<GkSiteReport[]>([]);

  const [nodes, setNodes] = useState<RemoteNode[]>(() => getRemoteNodes());
  const [selectedNodeId, setSelectedNodeId] = useState(() => localStorage.getItem(NODE_KEY) || "");
  const [showNodeManager, setShowNodeManager] = useState(false);
  const [newNodeName, setNewNodeName] = useState("");
  const [newNodeUrl, setNewNodeUrl] = useState("");

  function selectNode(id: string) {
    setSelectedNodeId(id);
    localStorage.setItem(NODE_KEY, id);
  }

  function addNode() {
    if (!newNodeName.trim() || !newNodeUrl.trim()) return;
    setNodes(addRemoteNode(newNodeName, newNodeUrl));
    setNewNodeName("");
    setNewNodeUrl("");
  }

  function deleteNode(id: string) {
    setNodes(removeRemoteNode(id));
    if (selectedNodeId === id) selectNode("");
  }

  const activeNode = nodes.find((n) => n.id === selectedNodeId);

  const loadJobs = useCallback(async () => {
    const res = await api.get<AcquisitionJob[]>("/api/sources/gk-scraper/jobs");
    setJobs(res.data);
    return res.data;
  }, []);

  const loadDomains = useCallback(async () => {
    const res = await api.get<{ domains: string[] }>("/api/sources/gk-scraper/profiles");
    setDomains(res.data.domains);
    return res.data.domains;
  }, []);

  const loadSiteReports = useCallback(async () => {
    const res = await api.get<{ sites: GkSiteReport[] }>("/api/sources/gk-scraper/site-reports");
    setSiteReports(res.data.sites);
    return res.data.sites;
  }, []);

  const loadProfile = useCallback(async (domain: string) => {
    if (!domain) {
      setProfile(null);
      return;
    }
    try {
      const res = await api.get<GkProfile>(`/api/sources/gk-scraper/profiles/${domain}`);
      setProfile(res.data);
    } catch (e) {
      setError(apiError(e));
    }
  }, []);

  const loadUrls = useCallback(async (domain: string, status: string, page: number) => {
    if (!domain) {
      setUrlList(null);
      return;
    }
    try {
      const res = await api.get<GkVisitedUrlList>(`/api/sources/gk-scraper/profiles/${domain}/urls`, {
        params: { status: status || undefined, limit: URL_PAGE_SIZE, offset: page * URL_PAGE_SIZE },
      });
      setUrlList(res.data);
    } catch (e) {
      setError(apiError(e));
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const data = await loadJobs();
      const active = data.some((j) => ["queued", "scanning", "downloading"].includes(j.status));
      if (!active) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
        const found = await loadDomains();
        loadSiteReports().catch((e) => setError(apiError(e)));
        if (found.length) {
          const latest = found[found.length - 1];
          setSelectedDomain(latest);
          setUrlPage(0);
          loadProfile(latest);
          loadUrls(latest, urlStatus, 0);
        }
      } else {
        loadSiteReports().catch(() => undefined);
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2000);
  }, [loadJobs, loadDomains, loadSiteReports, loadProfile, loadUrls, urlStatus]);

  useEffect(() => {
    loadDomains().catch((e) => setError(apiError(e)));
    loadSiteReports().catch((e) => setError(apiError(e)));
    loadJobs().then((data) => {
      if (data.some((j) => ["queued", "scanning", "downloading"].includes(j.status))) startPolling();
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function cancelJob(jobId: number) {
    try {
      await api.post(`/api/sources/gk-scraper/jobs/${jobId}/cancel`);
      await loadJobs();
    } catch (e) {
      setError(apiError(e));
    }
  }

  async function scan(url?: string) {
    const target = (url ?? homepageUrl).trim();
    if (!target) return;
    setBusy(true);
    setError("");
    try {
      // A registered node sends the trigger straight to that machine's own
      // API (absolute URL bypasses the local vite proxy) -- the current
      // login token still works there since both nodes share the same DB
      // and JWT secret (see deploy/README.md). Everything else (progress,
      // site reports) keeps reading from THIS backend regardless, since
      // both nodes write into the same shared database.
      const endpoint = activeNode
        ? `${activeNode.baseUrl}/api/sources/gk-scraper/scan`
        : "/api/sources/gk-scraper/scan";
      await api.post(endpoint, { homepage_url: target });
      startPolling();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const STATUS_BADGE: Record<string, string> = {
    not_started: "bg-secondary",
    queued: "bg-info text-dark",
    scanning: "bg-info text-dark",
    downloading: "bg-primary",
    partial: "bg-warning text-dark",
    completed: "bg-success",
    failed: "bg-danger",
  };

  const activeJobs = jobs.filter((j) => ["queued", "scanning", "downloading"].includes(j.status));
  const lastJob = jobs[0];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-globe2 text-warning me-2" />
          GK Scraper
        </h3>
        <Link to="/question-bank" className="btn btn-outline-secondary btn-sm">
          <i className="bi bi-collection me-1" />
          View in Question Bank
        </Link>
      </div>

      <p className="text-muted small">
        Give a homepage URL. QVault crawls the site (sitemap first, link-following as a fallback),
        classifies each page as MCQ / essay / fill-in-the-blank / PDF, extracts questions into the
        shared Question Bank (category: <strong>General Knowledge</strong>), and writes a markdown
        profile of what it found.
      </p>

      {error && (
        <div className="alert alert-danger d-flex justify-content-between">
          <span>{error}</span>
          <button className="btn-close" onClick={() => setError("")} />
        </div>
      )}

      {canExecute && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <label className="form-label small mb-0">Homepage URL</label>
              <button className="btn btn-link btn-sm p-0" onClick={() => setShowNodeManager((v) => !v)}>
                <i className="bi bi-hdd-network me-1" />
                Run on: <strong>{activeNode ? activeNode.name : "This PC"}</strong>
              </button>
            </div>
            <div className="d-flex gap-2">
              <select
                className="form-select w-auto"
                value={selectedNodeId}
                onChange={(e) => selectNode(e.target.value)}
                title="Which machine will run this scan"
              >
                <option value="">This PC (local)</option>
                {nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
              <input
                className="form-control"
                placeholder="https://www.example.com"
                value={homepageUrl}
                onChange={(e) => setHomepageUrl(e.target.value)}
              />
              <button className="btn btn-primary text-nowrap" disabled={busy || !homepageUrl.trim()} onClick={() => scan()}>
                <i className="bi bi-binoculars me-1" />
                Start Scan
              </button>
            </div>

            {showNodeManager && (
              <div className="mt-3 pt-3 border-top">
                <div className="small text-muted mb-2">
                  Remote scraper nodes (e.g. a headless PC set up per <code>deploy/README.md</code>) — registered here
                  in your browser only. Scans sent to a node run on that machine; progress and results still show up
                  here automatically since both share the same database.
                </div>
                {nodes.length > 0 && (
                  <ul className="list-group list-group-flush mb-2">
                    {nodes.map((n) => (
                      <li key={n.id} className="list-group-item d-flex justify-content-between align-items-center px-0">
                        <span><strong>{n.name}</strong> <span className="text-muted small">{n.baseUrl}</span></span>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => deleteNode(n.id)}>
                          <i className="bi bi-trash" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="d-flex gap-2">
                  <input
                    className="form-control form-control-sm"
                    placeholder="Name (e.g. Node 2)"
                    value={newNodeName}
                    onChange={(e) => setNewNodeName(e.target.value)}
                  />
                  <input
                    className="form-control form-control-sm"
                    placeholder="http://192.168.10.50:8005"
                    value={newNodeUrl}
                    onChange={(e) => setNewNodeUrl(e.target.value)}
                  />
                  <button className="btn btn-sm btn-outline-primary text-nowrap" onClick={addNode}>
                    <i className="bi bi-plus-lg me-1" />
                    Add
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {(activeJobs.length > 0 || lastJob) && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold d-flex justify-content-between">
            <span><i className="bi bi-list-task me-2" />Scrape Jobs</span>
            {lastJob && (
              <span className="small text-muted">
                Latest: {new Date(lastJob.updated_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="card-body">
            {activeJobs.length === 0 && <div className="small text-muted">No active jobs.</div>}
            {activeJobs.map((j) => (
              <div className="mb-3" key={j.id}>
                <div className="small text-muted mb-1 d-flex justify-content-between align-items-center">
                  <span>
                    Job #{j.id}
                    {jobSiteLabel(j) && <> · <strong>{jobSiteLabel(j)}</strong></>}
                    {jobNodeLabel(j) && <> <span className="badge bg-secondary-subtle text-secondary-emphasis"><i className="bi bi-hdd-network me-1" />{jobNodeLabel(j)}</span></>}
                    {" "}· {j.stage || j.status} · {j.processed}/{j.total || "?"}
                  </span>
                  {canExecute && (
                    <button className="btn btn-sm btn-outline-danger" onClick={() => cancelJob(j.id)}>
                      <i className="bi bi-x-circle me-1" />
                      Cancel
                    </button>
                  )}
                </div>
                <JobProgress job={{ ...j, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card border-0 shadow-sm mb-3">
        <div className="card-header bg-white fw-semibold">
          <i className="bi bi-bar-chart-steps me-2" />Sites Report
        </div>
        <div className="card-body p-0">
          {siteReports.length === 0 ? (
            <div className="small text-muted py-3 text-center">No sites scanned yet.</div>
          ) : (
            <div className="table-responsive">
              <table className="table table-sm mb-0 align-middle">
                <thead>
                  <tr>
                    <th>Site</th>
                    <th>Status</th>
                    <th className="text-end">Total pages</th>
                    <th className="text-end">Scraped</th>
                    <th className="text-end">Failed</th>
                    <th className="text-end">Questions</th>
                    <th className="text-end">Options</th>
                    <th>Last scanned</th>
                    {canExecute && <th />}
                  </tr>
                </thead>
                <tbody>
                  {siteReports.map((s) => (
                    <tr key={s.domain}>
                      <td>
                        <a href={s.homepage_url} target="_blank" rel="noreferrer">{s.domain}</a>
                      </td>
                      <td>
                        <span className={`badge ${STATUS_BADGE[s.status] || "bg-secondary"}`}>
                          {s.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="text-end">{s.total_pages}</td>
                      <td className="text-end">{s.scraped_pages}</td>
                      <td className="text-end">{s.failed_pages || "—"}</td>
                      <td className="text-end">{s.questions}</td>
                      <td className="text-end">{s.options}</td>
                      <td className="small text-muted">{s.last_scanned ? new Date(s.last_scanned).toLocaleString() : "—"}</td>
                      {canExecute && (
                        <td>
                          {["not_started", "completed", "partial", "failed"].includes(s.status) && (
                            <button
                              className="btn btn-sm btn-outline-primary"
                              disabled={busy}
                              onClick={() => scan(s.homepage_url)}
                            >
                              <i className="bi bi-binoculars me-1" />
                              {s.status === "not_started" ? "Scan" : "Rescan"}
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="card border-0 shadow-sm">
        <div className="card-header bg-white fw-semibold d-flex justify-content-between align-items-center">
          <span><i className="bi bi-file-earmark-text me-2" />Site Profile</span>
          {domains.length > 0 && (
            <select
              className="form-select form-select-sm w-auto"
              value={selectedDomain}
              onChange={(e) => {
                setSelectedDomain(e.target.value);
                setUrlPage(0);
                loadProfile(e.target.value);
                loadUrls(e.target.value, urlStatus, 0);
              }}
            >
              <option value="">Select a scanned site…</option>
              {domains.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          )}
        </div>
        <div className="card-body">
          {!profile && <div className="small text-muted py-3 text-center">No profile selected yet. Run a scan or pick a site above.</div>}
          {profile && (
            <>
              <div className="small text-muted mb-2">Last updated {new Date(profile.updated_at).toLocaleString()}</div>
              <pre className="bg-light p-3 rounded" style={{ whiteSpace: "pre-wrap", maxHeight: 480, overflowY: "auto", fontSize: "0.8rem" }}>
                {profile.content}
              </pre>
            </>
          )}
        </div>
      </div>

      {selectedDomain && (
        <div className="card border-0 shadow-sm mt-3">
          <div className="card-header bg-white fw-semibold d-flex justify-content-between align-items-center flex-wrap gap-2">
            <span><i className="bi bi-link-45deg me-2" />Scraped &amp; Visited URLs{urlList ? ` (${urlList.total})` : ""}</span>
            <select
              className="form-select form-select-sm w-auto"
              value={urlStatus}
              onChange={(e) => { setUrlStatus(e.target.value); setUrlPage(0); loadUrls(selectedDomain, e.target.value, 0); }}
            >
              <option value="">All statuses</option>
              <option value="completed">Completed</option>
              <option value="discovered">Discovered</option>
              <option value="downloading">Downloading</option>
              <option value="retry">Retry</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className="card-body p-0">
            {!urlList || urlList.items.length === 0 ? (
              <div className="small text-muted py-3 text-center">No URLs recorded yet.</div>
            ) : (
              <div className="table-responsive">
                <table className="table table-sm mb-0 align-middle">
                  <thead>
                    <tr>
                      <th>URL</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Last updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {urlList.items.map((u) => (
                      <tr key={u.id}>
                        <td className="text-break small">
                          <a href={u.source_url} target="_blank" rel="noreferrer">{u.source_url}</a>
                          {u.error && <div className="text-danger" style={{ fontSize: "0.75rem" }}>{u.error}</div>}
                        </td>
                        <td className="small">{u.document_type || "—"}</td>
                        <td>
                          <span className={`badge ${u.status === "completed" ? "bg-success" : u.status === "failed" ? "bg-danger" : "bg-secondary"}`}>
                            {u.status}
                          </span>
                        </td>
                        <td className="small text-muted">{new Date(u.updated_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {urlList && urlList.total > URL_PAGE_SIZE && (
            <div className="card-footer bg-white d-flex justify-content-between align-items-center">
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={urlPage === 0}
                onClick={() => { const p = urlPage - 1; setUrlPage(p); loadUrls(selectedDomain, urlStatus, p); }}
              >
                <i className="bi bi-chevron-left" /> Prev
              </button>
              <span className="small text-muted">
                Page {urlPage + 1} of {Math.max(1, Math.ceil(urlList.total / URL_PAGE_SIZE))}
              </span>
              <button
                className="btn btn-sm btn-outline-secondary"
                disabled={(urlPage + 1) * URL_PAGE_SIZE >= urlList.total}
                onClick={() => { const p = urlPage + 1; setUrlPage(p); loadUrls(selectedDomain, urlStatus, p); }}
              >
                Next <i className="bi bi-chevron-right" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
