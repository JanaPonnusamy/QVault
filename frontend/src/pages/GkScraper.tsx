import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import JobProgress from "../components/JobProgress";
import type { AcquisitionJob, GkProfile, GkVisitedUrlList } from "../types";

const URL_PAGE_SIZE = 25;

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
        if (found.length) {
          const latest = found[found.length - 1];
          setSelectedDomain(latest);
          setUrlPage(0);
          loadProfile(latest);
          loadUrls(latest, urlStatus, 0);
        }
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2500);
  }, [loadJobs, loadDomains, loadProfile, loadUrls, urlStatus]);

  useEffect(() => {
    loadDomains().catch((e) => setError(apiError(e)));
    loadJobs().then((data) => {
      if (data.some((j) => ["queued", "scanning", "downloading"].includes(j.status))) startPolling();
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function scan() {
    if (!homepageUrl.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.post("/api/sources/gk-scraper/scan", { homepage_url: homepageUrl.trim() });
      startPolling();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

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
            <label className="form-label small mb-1">Homepage URL</label>
            <div className="d-flex gap-2">
              <input
                className="form-control"
                placeholder="https://www.example.com"
                value={homepageUrl}
                onChange={(e) => setHomepageUrl(e.target.value)}
              />
              <button className="btn btn-primary text-nowrap" disabled={busy || !homepageUrl.trim()} onClick={scan}>
                <i className="bi bi-binoculars me-1" />
                Start Scan
              </button>
            </div>
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
                <div className="small text-muted mb-1">
                  Job #{j.id} · {j.processed}/{j.total || "?"}
                </div>
                <JobProgress job={{ ...j, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

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
