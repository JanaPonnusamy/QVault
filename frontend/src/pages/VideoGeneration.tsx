import { useCallback, useEffect, useRef, useState } from "react";

import { api, apiError, getToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../branding/BrandingContext";
import JobProgress from "../components/JobProgress";
import { getModuleColor } from "../modules";
import type {
  AcquisitionJob,
  TimelinePreview,
  TTSProviderInfo,
  VideoItem,
  VideoSource,
  VideoStats,
  VideoTemplate,
} from "../types";

const PAGE_SIZE = 12;

const KIND_BADGE: Record<string, string> = {
  video: "bg-primary",
  short: "bg-danger",
  reel: "bg-warning text-dark",
};

const STATUS_BADGE: Record<string, string> = {
  queued: "bg-secondary",
  rendering: "bg-info",
  completed: "bg-success",
  failed: "bg-danger",
};

function fmtDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s.toString().padStart(2, "0")}s` : `${s}s`;
}

function fmtSize(bytes: number): string {
  if (!bytes) return "—";
  if (bytes > 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function VideoGeneration() {
  const { can } = useAuth();
  const { branding } = useBranding();
  const canExecute = can("videos:execute");
  const canDelete = can("videos:delete");
  const canExport = can("videos:export");

  const [stats, setStats] = useState<VideoStats | null>(null);
  const [sources, setSources] = useState<VideoSource[]>([]);
  const [templates, setTemplates] = useState<VideoTemplate[]>([]);
  const [providers, setProviders] = useState<TTSProviderInfo[]>([]);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [jobs, setJobs] = useState<AcquisitionJob[]>([]);
  const [page, setPage] = useState(0);
  const [kindFilter, setKindFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<TimelinePreview | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const pollRef = useRef<number | null>(null);

  // generation form
  const [sourceFile, setSourceFile] = useState("");
  const [topic, setTopic] = useState("");
  const [category, setCategory] = useState("General Knowledge");
  const [kind, setKind] = useState("video");
  const [orientation, setOrientation] = useState("");
  const [questionCount, setQuestionCount] = useState<number | "">("");
  const [template, setTemplate] = useState("glass_dark");
  const [provider, setProvider] = useState("edge");
  const [voice, setVoice] = useState("");
  const [batchCount, setBatchCount] = useState(10);

  const selectedSource = sources.find((s) => s.path === sourceFile);
  const selectedProvider = providers.find((p) => p.name === provider);

  const loadStats = useCallback(async () => {
    const res = await api.get<VideoStats>("/api/videos/stats");
    setStats(res.data);
  }, []);

  const loadVideos = useCallback(async () => {
    try {
      const res = await api.get<{ items: VideoItem[]; total: number }>("/api/videos", {
        params: {
          kind: kindFilter || undefined,
          status: statusFilter || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        },
      });
      setVideos(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      setError(apiError(e));
    }
  }, [kindFilter, statusFilter, page]);

  const loadJobs = useCallback(async () => {
    const res = await api.get<AcquisitionJob[]>("/api/videos/jobs");
    setJobs(res.data);
    return res.data;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [src, tpl, prov] = await Promise.all([
          api.get<VideoSource[]>("/api/videos/sources"),
          api.get<VideoTemplate[]>("/api/videos/templates"),
          api.get<TTSProviderInfo[]>("/api/videos/tts-providers"),
        ]);
        setSources(src.data);
        setTemplates(tpl.data);
        setProviders(prov.data);
        if (src.data.length > 0) setSourceFile(src.data[0].path);
        await loadStats();
      } catch (e) {
        setError(apiError(e));
      }
    })();
  }, [loadStats]);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const startPolling = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      const data = await loadJobs();
      loadStats();
      loadVideos();
      if (!data.some((j) => ["queued", "processing", "rendering"].includes(j.status))) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2500);
  }, [loadJobs, loadStats, loadVideos]);

  useEffect(() => {
    loadJobs().then((data) => {
      if (data.some((j) => ["queued", "processing", "rendering"].includes(j.status))) startPolling();
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [loadJobs, startPolling]);

  function generationPayload() {
    return {
      source_file: sourceFile,
      kind,
      orientation: orientation || null,
      category,
      topic: topic || null,
      question_count: questionCount === "" ? null : questionCount,
      template,
      tts_provider: provider,
      tts_voice: voice || null,
    };
  }

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

  async function onPreview() {
    setBusy(true);
    setError("");
    try {
      const res = await api.post<TimelinePreview>("/api/videos/preview", {
        source_file: sourceFile,
        kind,
        category,
        topic: topic || null,
        question_count: questionCount === "" ? null : questionCount,
      });
      setPreview(res.data);
      setPreviewOpen(true);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(video: VideoItem) {
    if (!window.confirm(`Delete "${video.title}"?`)) return;
    try {
      await api.delete(`/api/videos/${video.id}`);
      loadVideos();
      loadStats();
    } catch (e) {
      setError(apiError(e));
    }
  }

  const activeJobs = jobs.filter((j) => ["queued", "processing", "rendering"].includes(j.status));
  const token = getToken();
  const pages = Math.ceil(total / PAGE_SIZE);

  const cards = [
    { label: "Total Videos", value: stats?.total ?? 0, icon: "bi-camera-video", color: getModuleColor("videos", branding) },
    { label: "Completed", value: stats?.completed ?? 0, icon: "bi-check-circle", color: "#16a34a" },
    { label: "In Progress", value: stats?.in_progress ?? 0, icon: "bi-hourglass-split", color: "#0891b2" },
    { label: "Failed", value: stats?.failed ?? 0, icon: "bi-x-circle", color: "#dc2626" },
    { label: "Shorts / Reels", value: (stats?.shorts ?? 0) + (stats?.reels ?? 0), icon: "bi-phone", color: "#7c3aed" },
    { label: "Total Runtime", value: fmtDuration(stats?.total_duration ?? 0), icon: "bi-clock-history", color: "#d97706" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-camera-video text-danger me-2" />
          Video Generation
        </h3>
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
                  <div className="fs-5 fw-bold lh-1">{c.value}</div>
                  <div className="small text-muted">{c.label}</div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {canExecute && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">
            <i className="bi bi-magic me-2" />
            Generate Videos
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-6 col-xl-4">
                <label className="form-label small fw-semibold">Question Source (storage/**/*.json)</label>
                <select className="form-select form-select-sm" value={sourceFile}
                  onChange={(e) => { setSourceFile(e.target.value); setTopic(""); }}>
                  {sources.length === 0 && <option value="">No question JSON found under storage/</option>}
                  {sources.map((s) => (
                    <option key={s.path} value={s.path}>
                      {s.path} ({s.usable_count} usable questions)
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-md-6 col-xl-4">
                <label className="form-label small fw-semibold">Topic filter</label>
                <select className="form-select form-select-sm" value={topic} onChange={(e) => setTopic(e.target.value)}>
                  <option value="">All topics</option>
                  {selectedSource &&
                    Object.entries(selectedSource.topics).map(([t, n]) => (
                      <option key={t} value={t}>{t} ({n})</option>
                    ))}
                </select>
              </div>
              <div className="col-md-6 col-xl-4">
                <label className="form-label small fw-semibold">Category title (shown on screen)</label>
                <input className="form-control form-control-sm" value={category}
                  onChange={(e) => setCategory(e.target.value)} maxLength={60} />
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Output</label>
                <select className="form-select form-select-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="video">YouTube Video (20–25 Q)</option>
                  <option value="short">YouTube Short (1 Q)</option>
                  <option value="reel">Instagram Reel (1 Q)</option>
                </select>
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Orientation</label>
                <select className="form-select form-select-sm" value={orientation} onChange={(e) => setOrientation(e.target.value)}>
                  <option value="">Auto ({kind === "video" ? "Landscape 1920×1080" : "Portrait 1080×1920"})</option>
                  <option value="landscape">Landscape 1920×1080</option>
                  <option value="portrait">Portrait 1080×1920</option>
                </select>
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Questions</label>
                <input type="number" min={1} max={50} className="form-control form-control-sm"
                  placeholder={kind === "video" ? "25" : "1"} value={questionCount}
                  onChange={(e) => setQuestionCount(e.target.value === "" ? "" : Number(e.target.value))} />
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Theme</label>
                <select className="form-select form-select-sm" value={template} onChange={(e) => setTemplate(e.target.value)}>
                  {templates.map((t) => (
                    <option key={t.key} value={t.key} title={t.description}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Voice Provider</label>
                <select className="form-select form-select-sm" value={provider}
                  onChange={(e) => { setProvider(e.target.value); setVoice(""); }}>
                  {providers.map((p) => (
                    <option key={p.name} value={p.name} disabled={!p.available}>
                      {p.label}{p.available ? "" : " (not configured)"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-6 col-xl-2">
                <label className="form-label small fw-semibold">Voice</label>
                <select className="form-select form-select-sm" value={voice} onChange={(e) => setVoice(e.target.value)}>
                  <option value="">Default</option>
                  {selectedProvider?.voices.map((v) => (
                    <option key={v.id} value={v.id}>{v.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="d-flex align-items-center gap-2 mt-3 flex-wrap">
              <button className="btn btn-outline-secondary btn-sm" disabled={busy || !sourceFile} onClick={onPreview}>
                <i className="bi bi-eye me-1" />
                Preview Timeline
              </button>
              <button className="btn btn-primary btn-sm" disabled={busy || !sourceFile}
                onClick={() => run(() => api.post("/api/videos/generate", generationPayload()))}>
                <i className="bi bi-play-circle me-1" />
                Generate 1 Video
              </button>
              <div className="input-group input-group-sm" style={{ width: 220 }}>
                <span className="input-group-text">Batch</span>
                <input type="number" min={1} max={100} className="form-control" value={batchCount}
                  onChange={(e) => setBatchCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))} />
                <button className="btn btn-outline-primary" disabled={busy || !sourceFile}
                  onClick={() => run(() => api.post("/api/videos/batch", { ...generationPayload(), batch_count: batchCount }))}>
                  <i className="bi bi-collection-play me-1" />
                  Generate {batchCount}
                </button>
              </div>
              {busy && <span className="spinner-border spinner-border-sm text-primary" />}
            </div>
          </div>
        </div>
      )}

      {activeJobs.length > 0 && (
        <div className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">
            <i className="bi bi-gear-wide-connected me-2" />
            Generation Queue
          </div>
          <div className="card-body">
            {activeJobs.map((j) => (
              <div className="mb-2" key={j.id}>
                <div className="small text-muted mb-1">Render job #{j.id}</div>
                <JobProgress job={{ ...j, frame_count: 0 } as never} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card border-0 shadow-sm">
        <div className="card-header bg-white d-flex align-items-center gap-2 flex-wrap">
          <span className="fw-semibold me-auto">
            <i className="bi bi-collection-play me-2" />
            Generated Videos ({total})
          </span>
          <select className="form-select form-select-sm" style={{ width: 140 }} value={kindFilter}
            onChange={(e) => { setPage(0); setKindFilter(e.target.value); }}>
            <option value="">All kinds</option>
            <option value="video">Videos</option>
            <option value="short">Shorts</option>
            <option value="reel">Reels</option>
          </select>
          <select className="form-select form-select-sm" style={{ width: 150 }} value={statusFilter}
            onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}>
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="rendering">Rendering</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th style={{ width: 90 }}>Preview</th>
                <th>Title</th>
                <th>Kind</th>
                <th>Format</th>
                <th>Questions</th>
                <th>Duration</th>
                <th>Size</th>
                <th>Status</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {videos.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-muted py-4">
                    No videos yet. Pick a question source above and generate your first video.
                  </td>
                </tr>
              )}
              {videos.map((v) => (
                <tr key={v.id}>
                  <td>
                    {v.has_thumbnail ? (
                      <img
                        src={`/api/videos/${v.id}/thumbnail?token=${token}`}
                        alt=""
                        style={{
                          width: v.orientation === "portrait" ? 36 : 80,
                          height: 45,
                          objectFit: "cover",
                          borderRadius: 6,
                        }}
                      />
                    ) : (
                      <div className="bg-light rounded d-flex align-items-center justify-content-center" style={{ width: 80, height: 45 }}>
                        <i className="bi bi-camera-video text-muted" />
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="fw-medium text-truncate" style={{ maxWidth: 300 }} title={v.title}>{v.title}</div>
                    <div className="small text-muted">{v.template} · {v.tts_provider}{v.topic ? ` · ${v.topic}` : ""}</div>
                  </td>
                  <td><span className={`badge ${KIND_BADGE[v.kind] ?? "bg-secondary"}`}>{v.kind}</span></td>
                  <td className="small">{v.width}×{v.height}</td>
                  <td>{v.question_count}</td>
                  <td>{fmtDuration(v.duration)}</td>
                  <td>{fmtSize(v.file_size)}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[v.status] ?? "bg-secondary"}`}>{v.status}</span>
                    {v.status === "failed" && v.error && (
                      <i className="bi bi-info-circle text-danger ms-1" title={v.error} />
                    )}
                  </td>
                  <td className="text-end text-nowrap">
                    {canExport && v.status === "completed" && (
                      <>
                        <a className="btn btn-sm btn-outline-primary me-1" title="Download MP4"
                          href={`/api/videos/${v.id}/download?token=${token}`}>
                          <i className="bi bi-download" />
                        </a>
                        {v.has_srt && (
                          <a className="btn btn-sm btn-outline-secondary me-1" title="Download subtitles (SRT)"
                            href={`/api/videos/${v.id}/subtitles?token=${token}`}>
                            <i className="bi bi-badge-cc" />
                          </a>
                        )}
                      </>
                    )}
                    {canDelete && v.status !== "rendering" && (
                      <button className="btn btn-sm btn-outline-danger" title="Delete" onClick={() => onDelete(v)}>
                        <i className="bi bi-trash" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {pages > 1 && (
          <div className="card-footer bg-white d-flex justify-content-between align-items-center">
            <span className="small text-muted">
              Page {page + 1} of {pages}
            </span>
            <div className="btn-group">
              <button className="btn btn-sm btn-outline-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
                <i className="bi bi-chevron-left" />
              </button>
              <button className="btn btn-sm btn-outline-secondary" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
                <i className="bi bi-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {previewOpen && preview && (
        <>
          <div className="modal fade show d-block" tabIndex={-1} onClick={() => setPreviewOpen(false)}>
            <div className="modal-dialog modal-lg modal-dialog-scrollable" onClick={(e) => e.stopPropagation()}>
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-stopwatch me-2" />
                    Timeline Preview — estimated {fmtDuration(preview.duration)}
                  </h5>
                  <button className="btn-close" onClick={() => setPreviewOpen(false)} />
                </div>
                <div className="modal-body">
                  <p className="small text-muted">
                    Estimated narration pacing (~2.5 words/sec). Real timings come from the synthesized
                    voice during generation. Intro ends at {preview.intro_end.toFixed(1)}s · outro starts at{" "}
                    {preview.outro_in.toFixed(1)}s.
                  </p>
                  <div className="table-responsive">
                    <table className="table table-sm align-middle">
                      <thead className="table-light">
                        <tr>
                          <th>#</th>
                          <th>Question</th>
                          <th>Q in</th>
                          <th>Options</th>
                          <th>Countdown</th>
                          <th>Reveal</th>
                          <th>Explanation</th>
                          <th>End</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.scenes.map((s) => (
                          <tr key={s.index}>
                            <td>{s.index + 1}</td>
                            <td className="small">
                              <div className="text-truncate" style={{ maxWidth: 260 }} title={s.question}>{s.question}</div>
                              <div className="text-success small">✓ {s.answer}</div>
                            </td>
                            <td>{s.question_in.toFixed(1)}s</td>
                            <td>{s.options_in[0]?.toFixed(1)}–{s.options_in[s.options_in.length - 1]?.toFixed(1)}s</td>
                            <td>{s.countdown_in.toFixed(1)}s</td>
                            <td>{s.reveal_at.toFixed(1)}s</td>
                            <td>{s.explanation_in ? `${s.explanation_in.toFixed(1)}s` : "—"}</td>
                            <td>{s.end.toFixed(1)}s</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show" />
        </>
      )}
    </div>
  );
}
