import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ConfidenceBadge, { QuestionStatusBadge } from "../components/ConfidenceBadge";
import type { Job, Question } from "../types";

function fmtTime(seconds: number): string {
  const s = Math.floor(seconds % 60);
  const m = Math.floor(seconds / 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function Review() {
  const { jobId } = useParams();
  const id = Number(jobId);
  const { can } = useAuth();
  const canUpdate = can("youtube_extractor:update");

  const [job, setJob] = useState<Job | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState("");

  // Editable draft for the selected question.
  const [text, setText] = useState("");
  const [options, setOptions] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const [j, q] = await Promise.all([
        api.get<Job>(`/api/extractor/jobs/${id}`),
        api.get<Question[]>(`/api/extractor/jobs/${id}/questions`),
      ]);
      setJob(j.data);
      setQuestions(q.data);
      setSelectedId((prev) => prev ?? (q.data[0]?.id ?? null));
    } catch (e) {
      setError(apiError(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => questions.find((q) => q.id === selectedId) ?? null,
    [questions, selectedId]
  );

  useEffect(() => {
    setText(selected?.text ?? "");
    setOptions(selected ? [...selected.options] : []);
  }, [selected]);

  const filtered = useMemo(
    () => (filter === "all" ? questions : questions.filter((q) => q.status === filter)),
    [questions, filter]
  );

  const counts = useMemo(() => {
    const c = { all: questions.length, pending: 0, approved: 0, rejected: 0 } as Record<string, number>;
    for (const q of questions) c[q.status] = (c[q.status] ?? 0) + 1;
    return c;
  }, [questions]);

  async function save() {
    if (!selected) return;
    try {
      await api.put(`/api/extractor/questions/${selected.id}`, {
        text,
        options: options.filter((o) => o.trim()),
      });
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  async function setStatus(action: "approve" | "reject") {
    if (!selected) return;
    try {
      await api.post(`/api/extractor/questions/${selected.id}/${action}`);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  async function remove() {
    if (!selected || !confirm("Delete this question?")) return;
    try {
      await api.delete(`/api/extractor/questions/${selected.id}`);
      setSelectedId(null);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h3 className="fw-bold mb-0">
            <i className="bi bi-list-check me-2" />
            Question Review
          </h3>
          <div className="small text-muted">{job?.title || job?.url}</div>
        </div>
        <Link to="/extractor" className="btn btn-outline-secondary btn-sm">
          <i className="bi bi-arrow-left me-1" />
          Back to Extractor
        </Link>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="row g-3">
        {/* Left: question list */}
        <div className="col-12 col-lg-5 col-xl-4">
          <div className="card border-0 shadow-sm">
            <div className="card-header bg-white d-flex gap-1 flex-wrap">
              {["all", "pending", "approved", "rejected"].map((f) => (
                <button
                  key={f}
                  className={`btn btn-sm ${filter === f ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setFilter(f)}
                >
                  {f} ({counts[f] ?? 0})
                </button>
              ))}
            </div>
            <div className="list-group list-group-flush" style={{ maxHeight: 560, overflowY: "auto" }}>
              {filtered.length === 0 && <div className="p-3 text-muted small">No questions.</div>}
              {filtered.map((q) => (
                <button
                  key={q.id}
                  className={`list-group-item list-group-item-action ${
                    selectedId === q.id ? "active" : ""
                  }`}
                  onClick={() => setSelectedId(q.id)}
                >
                  <div className="d-flex justify-content-between align-items-start gap-2">
                    <span className="text-truncate">{q.text.split("\n")[0] || "(empty)"}</span>
                    <QuestionStatusBadge status={q.status} />
                  </div>
                  <div className={`small mt-1 ${selectedId === q.id ? "" : "text-muted"}`}>
                    <i className="bi bi-clock me-1" />
                    {fmtTime(q.timestamp)} · {Math.round(q.overall_confidence * 100)}% · {q.options.length} options
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: editor */}
        <div className="col-12 col-lg-7 col-xl-8">
          {!selected && (
            <div className="card border-0 shadow-sm">
              <div className="card-body text-muted text-center py-5">Select a question to review.</div>
            </div>
          )}
          {selected && (
            <div className="card border-0 shadow-sm">
              <div className="card-body">
                <div className="d-flex flex-wrap gap-2 mb-3">
                  <ConfidenceBadge value={selected.overall_confidence} label="Overall" />
                  <ConfidenceBadge value={selected.ocr_confidence} label="OCR" />
                  <ConfidenceBadge value={selected.frame_confidence} label="Frame" />
                  <ConfidenceBadge value={selected.merge_confidence} label="Merge" />
                  <QuestionStatusBadge status={selected.status} />
                  {selected.source === "auto" && <span className="badge bg-info">auto</span>}
                  {selected.frame_start != null && (
                    <span className="badge bg-light text-dark">
                      frames {selected.frame_start}–{selected.frame_end}
                    </span>
                  )}
                </div>

                <label className="form-label fw-medium">Question text</label>
                <textarea
                  className="form-control mb-3"
                  rows={Math.min(8, Math.max(3, text.split("\n").length))}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  readOnly={!canUpdate}
                />

                <label className="form-label fw-medium">Options</label>
                {options.map((opt, i) => (
                  <div className="input-group mb-2" key={i}>
                    <span className="input-group-text">{String.fromCharCode(65 + i)}</span>
                    <input
                      className="form-control"
                      value={opt}
                      readOnly={!canUpdate}
                      onChange={(e) =>
                        setOptions(options.map((o, j) => (j === i ? e.target.value : o)))
                      }
                    />
                    {canUpdate && (
                      <button
                        className="btn btn-outline-danger"
                        onClick={() => setOptions(options.filter((_, j) => j !== i))}
                      >
                        <i className="bi bi-x-lg" />
                      </button>
                    )}
                  </div>
                ))}
                {canUpdate && (
                  <button
                    className="btn btn-sm btn-outline-secondary mb-3"
                    onClick={() => setOptions([...options, ""])}
                  >
                    <i className="bi bi-plus-lg me-1" />
                    Add option
                  </button>
                )}

                {canUpdate && (
                  <div className="d-flex gap-2 border-top pt-3">
                    <button className="btn btn-primary" onClick={save}>
                      <i className="bi bi-save me-1" />
                      Save
                    </button>
                    <button className="btn btn-success" onClick={() => setStatus("approve")}>
                      <i className="bi bi-check-lg me-1" />
                      Approve
                    </button>
                    <button className="btn btn-warning" onClick={() => setStatus("reject")}>
                      <i className="bi bi-x-lg me-1" />
                      Reject
                    </button>
                    <button className="btn btn-outline-danger ms-auto" onClick={remove}>
                      <i className="bi bi-trash me-1" />
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
