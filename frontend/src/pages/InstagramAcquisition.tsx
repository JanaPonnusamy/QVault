import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, apiError, getToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ConfidenceBadge, { QuestionStatusBadge } from "../components/ConfidenceBadge";
import ExtractionStrategySelector from "../components/ExtractionStrategySelector";
import JobProgress, { StatusBadge } from "../components/JobProgress";
import { DEFAULT_EXTRACTION_OPTIONS } from "../types";
import type { ExtractionOptions, Frame, InstagramStats, Job, Question } from "../types";

const BASE = "/api/sources/instagram";

const CLASS_COLORS: Record<string, string> = {
  heading: "#2563eb",
  paragraph: "#64748b",
  question: "#16a34a",
  options: "#0891b2",
  answer: "#d97706",
  diagram: "#7c3aed",
  table: "#334155",
};

function fmtTime(seconds: number): string {
  const s = Math.floor(seconds % 60);
  const m = Math.floor(seconds / 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtDate(raw: string): string {
  if (!raw || raw.length !== 8) return raw || "";
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function ClassBadges({ tags }: { tags?: string[] }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="d-flex flex-wrap gap-1 mt-1">
      {tags.map((t) => (
        <span key={t} className="badge" style={{ fontSize: "0.65rem", backgroundColor: CLASS_COLORS[t] ?? "#64748b" }}>
          {t}
        </span>
      ))}
    </div>
  );
}

export default function InstagramAcquisition() {
  const { can } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<InstagramStats | null>(null);
  const [url, setUrl] = useState("");
  const [extractionOptions, setExtractionOptions] = useState<ExtractionOptions>(DEFAULT_EXTRACTION_OPTIONS);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [selectedFrames, setSelectedFrames] = useState<Set<number>>(new Set());
  const [questions, setQuestions] = useState<Question[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [textOnly, setTextOnly] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const framesRef = useRef<HTMLDivElement>(null);

  const canExecute = can("instagram:execute");
  const canExport = can("instagram:export");
  const canUpdate = can("instagram:update");
  const canDelete = can("instagram:delete");

  const loadJobs = useCallback(async () => {
    const [j, s] = await Promise.all([
      api.get<Job[]>(`${BASE}/jobs`),
      api.get<InstagramStats>(`${BASE}/stats`),
    ]);
    setJobs(j.data);
    setStats(s.data);
  }, []);

  const loadFramesAndQuestions = useCallback(async (jobId: number) => {
    const [f, q] = await Promise.all([
      api.get<Frame[]>(`${BASE}/jobs/${jobId}/frames`, { params: { include_duplicates: false } }),
      api.get<Question[]>(`${BASE}/jobs/${jobId}/questions`),
    ]);
    setFrames(f.data);
    setQuestions(q.data);
  }, []);

  useEffect(() => {
    loadJobs().catch((e) => setError(apiError(e)));
  }, [loadJobs]);

  useEffect(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (selectedId == null) {
      setJob(null);
      setFrames([]);
      setQuestions([]);
      return;
    }
    setSelectedFrames(new Set());

    const tick = async () => {
      try {
        const res = await api.get<Job>(`${BASE}/jobs/${selectedId}`);
        setJob(res.data);
        if (res.data.status === "ready") {
          await loadFramesAndQuestions(selectedId);
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          loadJobs();
        } else if (res.data.status === "failed") {
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          loadJobs();
        }
      } catch (e) {
        setError(apiError(e));
      }
    };

    tick();
    pollRef.current = window.setInterval(tick, 2000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [selectedId, loadFramesAndQuestions, loadJobs]);

  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setError("");
    setSubmitting(true);
    try {
      const res = await api.post<Job>(`${BASE}/jobs`, { url, ...extractionOptions });
      setUrl("");
      await loadJobs();
      setSelectedId(res.data.id);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function uploadFile(file: File) {
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.post<Job>(`${BASE}/upload`, form);
      await loadJobs();
      setSelectedId(res.data.id);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (!canExecute) return;
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  async function deleteJob(id: number) {
    try {
      await api.delete(`${BASE}/jobs/${id}`);
      if (selectedId === id) setSelectedId(null);
      await loadJobs();
    } catch (err) {
      setError(apiError(err));
    }
  }

  function toggleFrame(id: number) {
    setSelectedFrames((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function runAnalyze() {
    if (selectedId == null) return;
    setAnalyzing(true);
    setError("");
    try {
      await api.post(`${BASE}/jobs/${selectedId}/analyze`);
      await loadFramesAndQuestions(selectedId);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setAnalyzing(false);
    }
  }

  const visibleFrames = useMemo(
    () => (textOnly ? frames.filter((f) => (f.ocr_text ?? "").trim().length > 0) : frames),
    [textOnly, frames]
  );

  // Reels-style auto-scroll of the extracted-frames strip.
  useEffect(() => {
    const el = framesRef.current;
    if (!autoScroll || !el || visibleFrames.length === 0) return;
    const timer = window.setInterval(() => {
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 1) {
        el.scrollTop = 0;
      } else {
        el.scrollTop += 1;
      }
    }, 30);
    return () => window.clearInterval(timer);
  }, [autoScroll, visibleFrames.length]);

  async function runOcr() {
    if (selectedId == null || selectedFrames.size === 0) return;
    setOcrBusy(true);
    setError("");
    try {
      await api.post(`${BASE}/jobs/${selectedId}/ocr`, { frame_ids: [...selectedFrames] });
      await loadFramesAndQuestions(selectedId);
      setSelectedFrames(new Set());
    } catch (err) {
      setError(apiError(err));
    } finally {
      setOcrBusy(false);
    }
  }

  async function saveQuestion(q: Question) {
    try {
      await api.put(`${BASE}/questions/${q.id}`, { text: q.text });
      await loadFramesAndQuestions(selectedId!);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function setStatus(id: number, action: "approve" | "reject") {
    try {
      await api.post(`${BASE}/questions/${id}/${action}`);
      await loadFramesAndQuestions(selectedId!);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function deleteQuestion(id: number) {
    try {
      await api.delete(`${BASE}/questions/${id}`);
      await loadFramesAndQuestions(selectedId!);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function exportAs(format: "json" | "csv" | "sqlite") {
    if (selectedId == null) return;
    try {
      const res = await api.get(`${BASE}/jobs/${selectedId}/export`, {
        params: { format },
        responseType: "blob",
      });
      const href = URL.createObjectURL(res.data as Blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = `instagram_job_${selectedId}.${format}`;
      link.click();
      URL.revokeObjectURL(href);
    } catch (err) {
      setError(apiError(err));
    }
  }

  const ready = job?.status === "ready";
  const textFrameCount = frames.filter((f) => (f.ocr_text ?? "").trim().length > 0).length;
  const videoAvailable = !!job && !["pending", "queued", "downloading", "failed"].includes(job.status);

  return (
    <div>
      <div className="d-flex align-items-center mb-3">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-instagram me-2" style={{ color: "#d6249f" }} />
          Instagram Acquisition
        </h3>
      </div>

      {stats && (
        <div className="row g-2 mb-3">
          {[
            { label: "Acquisitions", value: stats.total, icon: "bi-collection", color: "#d6249f" },
            { label: "Completed", value: stats.completed, icon: "bi-check-circle", color: "#16a34a" },
            { label: "Processing", value: stats.processing, icon: "bi-arrow-repeat", color: "#2563eb" },
            { label: "Failed", value: stats.failed, icon: "bi-exclamation-triangle", color: "#dc2626" },
            { label: "Frames", value: stats.frames, icon: "bi-images", color: "#7c3aed" },
          ].map((c) => (
            <div className="col-6 col-md" key={c.label}>
              <div className="card border-0 shadow-sm">
                <div className="card-body py-2 d-flex align-items-center gap-2">
                  <i className={`bi ${c.icon}`} style={{ color: c.color, fontSize: "1.3rem" }} />
                  <div>
                    <div className="fw-bold lh-1">{c.value}</div>
                    <div className="small text-muted">{c.label}</div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="alert alert-danger d-flex justify-content-between">
          <span>{error}</span>
          <button className="btn-close" onClick={() => setError("")} />
        </div>
      )}

      <div className="row g-3">
        <div className="col-12 col-lg-4">
          <div className="card border-0 shadow-sm mb-3">
            <div className="card-body">
              <h6 className="fw-semibold mb-3">New acquisition</h6>
              <form onSubmit={submitUrl}>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-link-45deg" />
                  </span>
                  <input
                    className="form-control"
                    placeholder="Paste Instagram Reel/Post URL"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={!canExecute}
                  />
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary w-100 mt-2 d-flex justify-content-between align-items-center"
                  onClick={() => setShowSettings((v) => !v)}
                >
                  <span><i className="bi bi-sliders me-1" />Extraction settings</span>
                  <i className={`bi ${showSettings ? "bi-chevron-up" : "bi-chevron-down"}`} />
                </button>
                {showSettings && (
                  <div className="mt-2">
                    <ExtractionStrategySelector
                      value={extractionOptions}
                      onChange={setExtractionOptions}
                      url={url}
                      estimateEndpoint={`${BASE}/estimate`}
                      disabled={!canExecute}
                    />
                  </div>
                )}
                <button className="btn btn-primary w-100 mt-2" disabled={submitting || !canExecute || !url.trim()}>
                  {submitting ? "Starting..." : (
                    <>
                      <i className="bi bi-download me-1" />
                      Download &amp; Process
                    </>
                  )}
                </button>
                {!canExecute && (
                  <div className="form-text text-warning">You lack the execute permission for this module.</div>
                )}
              </form>
            </div>
          </div>

          <div className="card border-0 shadow-sm mb-3">
            <div className="card-body">
              <h6 className="fw-semibold mb-2">
                <i className="bi bi-camera-video me-2" style={{ color: "#d6249f" }} />
                Video viewer — drag &amp; drop to extract
              </h6>
              <input
                ref={fileRef}
                type="file"
                accept="video/*,.mp4,.mov,.webm,.mkv,.avi,.m4v"
                className="d-none"
                onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
              />
              <div
                role="button"
                onClick={() => canExecute && fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); if (canExecute) setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                className={`d-flex flex-column align-items-center justify-content-center text-center rounded p-4 ${dragOver ? "border-primary bg-primary-subtle" : "border-secondary-subtle text-muted"}`}
                style={{
                  border: "2px dashed",
                  cursor: canExecute ? "pointer" : "not-allowed",
                  minHeight: 130,
                  transition: "background-color .12s, border-color .12s",
                }}
              >
                {uploading ? (
                  <>
                    <div className="spinner-border text-primary mb-2" role="status" />
                    <div className="small">Uploading &amp; extracting…</div>
                  </>
                ) : (
                  <>
                    <i className="bi bi-cloud-arrow-up" style={{ fontSize: "2rem" }} />
                    <div className="fw-medium mt-1">Drop a video here</div>
                    <div className="small">or click to browse · mp4, mov, webm, mkv, avi</div>
                  </>
                )}
              </div>
              {!canExecute && (
                <div className="form-text text-warning">You lack the execute permission for this module.</div>
              )}
            </div>
          </div>

          <div className="card border-0 shadow-sm">
            <div className="card-header bg-white fw-semibold">Acquisitions</div>
            <div className="list-group list-group-flush" style={{ maxHeight: 460, overflowY: "auto" }}>
              {jobs.length === 0 && <div className="p-3 text-muted small">No acquisitions yet.</div>}
              {jobs.map((j) => (
                <button
                  key={j.id}
                  className={`list-group-item list-group-item-action ${selectedId === j.id ? "active" : ""}`}
                  onClick={() => setSelectedId(j.id)}
                >
                  <div className="d-flex justify-content-between align-items-start">
                    <span className="text-truncate me-2" style={{ maxWidth: 200 }}>
                      {j.author || j.title || j.url}
                    </span>
                    <StatusBadge status={j.status} />
                  </div>
                  <div className={`small ${selectedId === j.id ? "" : "text-muted"}`}>
                    #{j.id} · {j.frame_count} frames
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="col-12 col-lg-8">
          {!job && (
            <div className="card border-0 shadow-sm">
              <div className="card-body text-center text-muted py-5">
                <i className="bi bi-arrow-left-circle d-block mb-2" style={{ fontSize: "2rem" }} />
                Paste an Instagram URL or select an acquisition to begin.
              </div>
            </div>
          )}

          {job && (
            <>
              <div className="card border-0 shadow-sm mb-3">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div className="d-flex gap-3">
                      {videoAvailable ? (
                        <video
                          key={job.id}
                          controls
                          poster={job.thumbnail_url || undefined}
                          src={`${BASE}/jobs/${job.id}/video?token=${getToken()}`}
                          style={{ width: 160, maxHeight: 280, borderRadius: 8, backgroundColor: "#000" }}
                        />
                      ) : job.thumbnail_url ? (
                        <img
                          src={job.thumbnail_url}
                          alt=""
                          style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 8 }}
                          onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                        />
                      ) : null}
                      <div>
                        <div className="fw-semibold">
                          {job.author && <><i className="bi bi-person-circle me-1" />{job.author}</>}
                          {!job.author && (job.title || job.url)}
                        </div>
                        <div className="small text-muted">
                          {job.upload_date && <>{fmtDate(job.upload_date)} · </>}
                          {job.duration > 0 && <>{fmtTime(job.duration)} · </>}
                          {job.frame_count} frames
                        </div>
                        {job.caption && (
                          <div className="small text-muted mt-1" style={{ maxWidth: 520, whiteSpace: "pre-wrap" }}>
                            {job.caption.length > 220 ? job.caption.slice(0, 220) + "…" : job.caption}
                          </div>
                        )}
                        {job.url.startsWith("upload://") ? (
                          <span className="small text-muted">
                            <i className="bi bi-file-earmark-play me-1" />
                            Uploaded video
                          </span>
                        ) : (
                          <a href={job.url} target="_blank" rel="noreferrer" className="small">
                            <i className="bi bi-box-arrow-up-right me-1" />
                            Open original
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="d-flex gap-2">
                      {ready && canExport && (
                        <div className="dropdown">
                          <button className="btn btn-outline-success btn-sm dropdown-toggle" data-bs-toggle="dropdown">
                            <i className="bi bi-download me-1" />
                            Export
                          </button>
                          <ul className="dropdown-menu dropdown-menu-end">
                            <li><button className="dropdown-item" onClick={() => exportAs("json")}><i className="bi bi-filetype-json me-2" />JSON</button></li>
                            <li><button className="dropdown-item" onClick={() => exportAs("csv")}><i className="bi bi-filetype-csv me-2" />CSV</button></li>
                            <li><button className="dropdown-item" onClick={() => exportAs("sqlite")}><i className="bi bi-database me-2" />SQLite</button></li>
                          </ul>
                        </div>
                      )}
                      {canDelete && (
                        <button className="btn btn-outline-danger btn-sm" onClick={() => deleteJob(job.id)}>
                          <i className="bi bi-trash" />
                        </button>
                      )}
                    </div>
                  </div>
                  <JobProgress job={job} />
                  {ready && (
                    <div className="small text-muted mt-2">
                      <i className="bi bi-check2-circle text-success me-1" />
                      {frames.length} unique frames · {textFrameCount} with text · {questions.length} questions
                    </div>
                  )}
                </div>
              </div>

              {job.duration > 0 && (
                <div className="card border-0 shadow-sm mb-3">
                  <div className="card-header bg-white fw-semibold">
                    <i className="bi bi-play-btn me-2" style={{ color: "#d6249f" }} />
                    Player
                  </div>
                  <div className="card-body d-flex justify-content-center" style={{ background: "#000", borderRadius: "0 0 .5rem .5rem" }}>
                    <div
                      style={{
                        height: "min(70vh, 560px)",
                        aspectRatio: "9 / 16",
                        maxWidth: "100%",
                        background: "#000",
                        borderRadius: 18,
                        overflow: "hidden",
                        border: "3px solid #111",
                      }}
                    >
                      <video
                        key={job.id}
                        src={`${BASE}/jobs/${job.id}/video?token=${getToken()}`}
                        controls
                        autoPlay
                        muted
                        loop
                        playsInline
                        style={{ width: "100%", height: "100%", objectFit: "contain", background: "#000" }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {ready && (
                <div className="card border-0 shadow-sm mb-3">
                  <div className="card-header bg-white d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <span className="fw-semibold">
                      <i className="bi bi-images me-2" />
                      Frames &amp; Classification
                      <span className="text-muted small ms-2">{visibleFrames.length} shown</span>
                    </span>
                    <div className="d-flex align-items-center gap-2">
                      <div className="form-check form-switch mb-0">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="textOnly"
                          checked={textOnly}
                          onChange={(e) => setTextOnly(e.target.checked)}
                        />
                        <label className="form-check-label small" htmlFor="textOnly">Text frames only</label>
                      </div>
                      <div className="form-check form-switch mb-0">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="autoScroll"
                          checked={autoScroll}
                          onChange={(e) => setAutoScroll(e.target.checked)}
                        />
                        <label className="form-check-label small" htmlFor="autoScroll">Auto-scroll</label>
                      </div>
                      {canExecute && (
                        <button className="btn btn-outline-secondary btn-sm" disabled={analyzing} onClick={runAnalyze}>
                          <i className="bi bi-arrow-repeat me-1" />
                          {analyzing ? "Processing..." : "Re-run"}
                        </button>
                      )}
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={!canExecute || ocrBusy || selectedFrames.size === 0}
                        onClick={runOcr}
                      >
                        {ocrBusy ? "Running OCR..." : (
                          <>
                            <i className="bi bi-eye me-1" />
                            OCR selected ({selectedFrames.size})
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="card-body" ref={framesRef} style={{ maxHeight: 540, overflowY: "auto" }}>
                    {visibleFrames.length === 0 && (
                      <div className="text-muted small">
                        {frames.length === 0 ? "No frames extracted." : "No frames with detected text. Toggle the switch to view all frames."}
                      </div>
                    )}
                    <div className="row g-2">
                      {visibleFrames.map((f) => {
                        const selected = selectedFrames.has(f.id);
                        return (
                          <div className="col-6 col-md-4 col-xl-3" key={f.id}>
                            <div className={`qv-frame ${selected ? "selected" : ""}`} onClick={() => toggleFrame(f.id)}>
                              <img
                                src={`${BASE}/frames/${f.id}/image?token=${getToken()}`}
                                loading="lazy"
                                alt={`Frame at ${fmtTime(f.timestamp)}`}
                              />
                              <button
                                className="btn btn-light btn-sm position-absolute"
                                style={{ top: 6, left: 6, padding: "0 .3rem", lineHeight: 1.4, zIndex: 2 }}
                                title="View full image"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPreview(`${BASE}/frames/${f.id}/image?token=${getToken()}`);
                                }}
                              >
                                <i className="bi bi-arrows-fullscreen" style={{ fontSize: ".7rem" }} />
                              </button>
                              {selected && <i className="bi bi-check-circle-fill qv-frame-check" />}
                              <span className="qv-frame-ts">{fmtTime(f.timestamp)}</span>
                            </div>
                            <ClassBadges tags={f.classification} />
                            {f.ocr_text && (
                              <div className="small text-muted mt-1" style={{ maxHeight: 60, overflow: "hidden" }}>
                                {f.ocr_text.length > 90 ? f.ocr_text.slice(0, 90) + "…" : f.ocr_text}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {ready && (
                <div className="card border-0 shadow-sm">
                  <div className="card-header bg-white fw-semibold">
                    <i className="bi bi-patch-question me-2" />
                    Extracted Questions ({questions.length})
                  </div>
                  <div className="card-body">
                    {questions.length === 0 && (
                      <div className="text-muted small">
                        Questions are detected automatically. You can also select frame(s) above and run OCR manually.
                      </div>
                    )}
                    {questions.map((q) => (
                      <QuestionEditor
                        key={q.id}
                        question={q}
                        canUpdate={canUpdate}
                        onSave={saveQuestion}
                        onApprove={() => setStatus(q.id, "approve")}
                        onReject={() => setStatus(q.id, "reject")}
                        onDelete={deleteQuestion}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {preview && (
        <div
          onClick={() => setPreview(null)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 2000,
            display: "flex", alignItems: "center", justifyContent: "center", cursor: "zoom-out",
          }}
        >
          <img
            src={preview}
            alt="Full frame"
            style={{ maxWidth: "94vw", maxHeight: "94vh", objectFit: "contain", borderRadius: 8, boxShadow: "0 0 40px rgba(0,0,0,0.6)" }}
          />
          <button
            className="btn btn-light position-absolute top-0 end-0 m-3"
            onClick={(e) => { e.stopPropagation(); setPreview(null); }}
            title="Close"
          >
            <i className="bi bi-x-lg" />
          </button>
        </div>
      )}
    </div>
  );
}

function QuestionEditor({
  question,
  canUpdate,
  onSave,
  onApprove,
  onReject,
  onDelete,
}: {
  question: Question;
  canUpdate: boolean;
  onSave: (q: Question) => void;
  onApprove: () => void;
  onReject: () => void;
  onDelete: (id: number) => void;
}) {
  const [text, setText] = useState(question.text);

  useEffect(() => {
    setText(question.text);
  }, [question.text]);

  return (
    <div className="border rounded p-2 mb-2">
      <div className="d-flex justify-content-between align-items-center mb-1 flex-wrap gap-1">
        <div className="d-flex align-items-center gap-2">
          <span className="badge bg-light text-dark">
            <i className="bi bi-clock me-1" />
            {fmtTime(question.timestamp)}
          </span>
          <ConfidenceBadge value={question.overall_confidence} />
          <QuestionStatusBadge status={question.status} />
          {question.source === "auto" && <span className="badge bg-info text-dark">auto</span>}
        </div>
        {canUpdate && (
          <div className="btn-group btn-group-sm">
            <button className="btn btn-outline-success" title="Approve" onClick={onApprove}>
              <i className="bi bi-check-lg" />
            </button>
            <button className="btn btn-outline-warning" title="Reject" onClick={onReject}>
              <i className="bi bi-x-lg" />
            </button>
            <button className="btn btn-outline-primary" title="Save" disabled={text === question.text} onClick={() => onSave({ ...question, text })}>
              <i className="bi bi-save" />
            </button>
            <button className="btn btn-outline-danger" title="Delete" onClick={() => onDelete(question.id)}>
              <i className="bi bi-trash" />
            </button>
          </div>
        )}
      </div>
      <textarea
        className="form-control"
        rows={Math.min(6, Math.max(2, text.split("\n").length))}
        value={text}
        onChange={(e) => setText(e.target.value)}
        readOnly={!canUpdate}
      />
      {question.options.length > 0 && (
        <ul className="small mt-2 mb-0">
          {question.options.map((o, i) => (
            <li key={i}>{o}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
