import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, apiError, getToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ConfidenceBadge, { QuestionStatusBadge } from "../components/ConfidenceBadge";
import JobProgress, { StatusBadge } from "../components/JobProgress";
import type { Frame, Job, Question } from "../types";

function fmtTime(seconds: number): string {
  const s = Math.floor(seconds % 60);
  const m = Math.floor(seconds / 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function YouTubeExtractor() {
  const { can } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [url, setUrl] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [selectedFrames, setSelectedFrames] = useState<Set<number>>(new Set());
  const [questions, setQuestions] = useState<Question[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const pollRef = useRef<number | null>(null);

  const canExecute = can("youtube_extractor:execute");
  const canExport = can("youtube_extractor:export");
  const canUpdate = can("youtube_extractor:update");

  const loadJobs = useCallback(async () => {
    const res = await api.get<Job[]>("/api/extractor/jobs");
    setJobs(res.data);
  }, []);

  const loadFramesAndQuestions = useCallback(async (jobId: number) => {
    const [f, q] = await Promise.all([
      api.get<Frame[]>(`/api/extractor/jobs/${jobId}/frames`),
      api.get<Question[]>(`/api/extractor/jobs/${jobId}/questions`),
    ]);
    setFrames(f.data);
    setQuestions(q.data);
  }, []);

  useEffect(() => {
    loadJobs().catch((e) => setError(apiError(e)));
  }, [loadJobs]);

  // Poll the selected job while it is processing.
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
        const res = await api.get<Job>(`/api/extractor/jobs/${selectedId}`);
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
      const res = await api.post<Job>("/api/extractor/jobs", { url });
      setUrl("");
      await loadJobs();
      setSelectedId(res.data.id);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setSubmitting(false);
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
      await api.post(`/api/extractor/jobs/${selectedId}/analyze`);
      await loadFramesAndQuestions(selectedId);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setAnalyzing(false);
    }
  }

  const visibleFrames = useMemo(
    () => (showAll ? frames : frames.filter((f) => f.is_question && !f.is_duplicate)),
    [showAll, frames]
  );

  async function runOcr() {
    if (selectedId == null || selectedFrames.size === 0) return;
    setOcrBusy(true);
    setError("");
    try {
      await api.post(`/api/extractor/jobs/${selectedId}/ocr`, {
        frame_ids: [...selectedFrames],
      });
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
      await api.put(`/api/extractor/questions/${q.id}`, { text: q.text });
      await loadFramesAndQuestions(selectedId!);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function deleteQuestion(id: number) {
    try {
      await api.delete(`/api/extractor/questions/${id}`);
      await loadFramesAndQuestions(selectedId!);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function exportAs(format: "json" | "csv" | "sqlite") {
    if (selectedId == null) return;
    try {
      const res = await api.get(`/api/extractor/jobs/${selectedId}/export`, {
        params: { format },
        responseType: "blob",
      });
      const href = URL.createObjectURL(res.data as Blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = `questions_job_${selectedId}.${format}`;
      link.click();
      URL.revokeObjectURL(href);
    } catch (err) {
      setError(apiError(err));
    }
  }

  const ready = job?.status === "ready";

  return (
    <div>
      <div className="d-flex align-items-center mb-3">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-youtube text-danger me-2" />
          YouTube Question Extractor
        </h3>
      </div>

      {error && (
        <div className="alert alert-danger d-flex justify-content-between">
          <span>{error}</span>
          <button className="btn-close" onClick={() => setError("")} />
        </div>
      )}

      <div className="row g-3">
        {/* Left column: input + jobs */}
        <div className="col-12 col-lg-4">
          <div className="card border-0 shadow-sm mb-3">
            <div className="card-body">
              <h6 className="fw-semibold mb-3">New extraction</h6>
              <form onSubmit={submitUrl}>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-link-45deg" />
                  </span>
                  <input
                    className="form-control"
                    placeholder="Paste YouTube URL"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={!canExecute}
                  />
                </div>
                <button
                  className="btn btn-primary w-100 mt-2"
                  disabled={submitting || !canExecute || !url.trim()}
                >
                  {submitting ? "Starting..." : (
                    <>
                      <i className="bi bi-download me-1" />
                      Download &amp; Extract Frames
                    </>
                  )}
                </button>
                {!canExecute && (
                  <div className="form-text text-warning">
                    You lack the execute permission for this module.
                  </div>
                )}
              </form>
            </div>
          </div>

          <div className="card border-0 shadow-sm">
            <div className="card-header bg-white fw-semibold">Extractions</div>
            <div className="list-group list-group-flush" style={{ maxHeight: 460, overflowY: "auto" }}>
              {jobs.length === 0 && <div className="p-3 text-muted small">No extractions yet.</div>}
              {jobs.map((j) => (
                <button
                  key={j.id}
                  className={`list-group-item list-group-item-action ${
                    selectedId === j.id ? "active" : ""
                  }`}
                  onClick={() => setSelectedId(j.id)}
                >
                  <div className="d-flex justify-content-between align-items-start">
                    <span className="text-truncate me-2" style={{ maxWidth: 200 }}>
                      {j.title || j.url}
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

        {/* Right column: workflow */}
        <div className="col-12 col-lg-8">
          {!job && (
            <div className="card border-0 shadow-sm">
              <div className="card-body text-center text-muted py-5">
                <i className="bi bi-arrow-left-circle d-block mb-2" style={{ fontSize: "2rem" }} />
                Paste a YouTube URL or select an extraction to begin.
              </div>
            </div>
          )}

          {job && (
            <>
              <div className="card border-0 shadow-sm mb-3">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <div>
                      <div className="fw-semibold">{job.title || job.url}</div>
                      <div className="small text-muted">
                        {job.duration > 0 && <>Duration {fmtTime(job.duration)} · </>}
                        {job.frame_count} frames
                      </div>
                    </div>
                    <div className="d-flex gap-2">
                      {ready && (
                        <Link to={`/review/${job.id}`} className="btn btn-outline-primary btn-sm">
                          <i className="bi bi-list-check me-1" />
                          Review ({questions.length})
                        </Link>
                      )}
                      {ready && canExport && (
                        <div className="dropdown">
                          <button
                            className="btn btn-outline-success btn-sm dropdown-toggle"
                            data-bs-toggle="dropdown"
                          >
                            <i className="bi bi-download me-1" />
                            Export
                          </button>
                          <ul className="dropdown-menu dropdown-menu-end">
                            <li>
                              <button className="dropdown-item" onClick={() => exportAs("json")}>
                                <i className="bi bi-filetype-json me-2" />
                                JSON
                              </button>
                            </li>
                            <li>
                              <button className="dropdown-item" onClick={() => exportAs("csv")}>
                                <i className="bi bi-filetype-csv me-2" />
                                CSV
                              </button>
                            </li>
                            <li>
                              <button className="dropdown-item" onClick={() => exportAs("sqlite")}>
                                <i className="bi bi-database me-2" />
                                SQLite
                              </button>
                            </li>
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                  <JobProgress job={job} />
                </div>
              </div>

              {ready && (
                <div className="card border-0 shadow-sm mb-3">
                  <div className="card-header bg-white d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <span className="fw-semibold">
                      <i className="bi bi-images me-2" />
                      Frame Gallery
                      <span className="text-muted small ms-2">
                        {visibleFrames.length} shown · {frames.filter((f) => !f.is_duplicate).length} unique ·{" "}
                        {frames.filter((f) => f.is_question && !f.is_duplicate).length} probable
                      </span>
                    </span>
                    <div className="d-flex align-items-center gap-2">
                      <div className="form-check form-switch mb-0">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          id="showAll"
                          checked={showAll}
                          onChange={(e) => setShowAll(e.target.checked)}
                        />
                        <label className="form-check-label small" htmlFor="showAll">
                          Show all frames
                        </label>
                      </div>
                      {canExecute && (
                        <button className="btn btn-outline-secondary btn-sm" disabled={analyzing} onClick={runAnalyze}>
                          <i className="bi bi-arrow-repeat me-1" />
                          {analyzing ? "Detecting..." : "Re-run detection"}
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
                  <div className="card-body">
                    {visibleFrames.length === 0 && (
                      <div className="text-muted small">
                        {frames.length === 0
                          ? "No frames extracted."
                          : "No probable question frames detected. Toggle “Show all frames” to view every frame."}
                      </div>
                    )}
                    <div className="row g-2">
                      {visibleFrames.map((f) => {
                        const selected = selectedFrames.has(f.id);
                        return (
                          <div className="col-6 col-md-4 col-xl-3" key={f.id}>
                            <div
                              className={`qv-frame ${selected ? "selected" : ""}`}
                              onClick={() => toggleFrame(f.id)}
                              style={f.is_duplicate ? { opacity: 0.6 } : undefined}
                            >
                              <img
                                src={`/api/extractor/frames/${f.id}/image?token=${getToken()}`}
                                loading="lazy"
                                alt={`Frame at ${fmtTime(f.timestamp)}`}
                              />
                              {selected && <i className="bi bi-check-circle-fill qv-frame-check" />}
                              <span
                                className={`badge position-absolute top-0 start-0 m-1 ${
                                  f.is_question ? "bg-success" : "bg-secondary"
                                }`}
                              >
                                {Math.round(f.question_score * 100)}%
                              </span>
                              {f.is_duplicate && (
                                <span className="badge bg-dark position-absolute top-0 end-0 m-1">dup</span>
                              )}
                              <span className="qv-frame-ts">{fmtTime(f.timestamp)}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {ready && (
                <div className="card border-0 shadow-sm">
                  <div className="card-header bg-white d-flex justify-content-between align-items-center">
                    <span className="fw-semibold">
                      <i className="bi bi-patch-question me-2" />
                      Extracted Questions ({questions.length})
                    </span>
                    {questions.length > 0 && (
                      <Link to={`/review/${job.id}`} className="btn btn-sm btn-primary">
                        <i className="bi bi-list-check me-1" />
                        Open Review Queue
                      </Link>
                    )}
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
    </div>
  );
}

function QuestionEditor({
  question,
  canUpdate,
  onSave,
  onDelete,
}: {
  question: Question;
  canUpdate: boolean;
  onSave: (q: Question) => void;
  onDelete: (id: number) => void;
}) {
  const [text, setText] = useState(question.text);

  useEffect(() => {
    setText(question.text);
  }, [question.text]);

  return (
    <div className="border rounded p-2 mb-2">
      <div className="d-flex justify-content-between align-items-center mb-1">
        <div className="d-flex align-items-center gap-2">
          <span className="badge bg-light text-dark">
            <i className="bi bi-clock me-1" />
            {fmtTime(question.timestamp)}
          </span>
          <ConfidenceBadge value={question.overall_confidence} />
          <QuestionStatusBadge status={question.status} />
          {question.source === "auto" && <span className="badge bg-info">auto</span>}
        </div>
        {canUpdate && (
          <div className="btn-group btn-group-sm">
            <button
              className="btn btn-outline-primary"
              disabled={text === question.text}
              onClick={() => onSave({ ...question, text })}
            >
              <i className="bi bi-save" />
            </button>
            <button className="btn btn-outline-danger" onClick={() => onDelete(question.id)}>
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
    </div>
  );
}
