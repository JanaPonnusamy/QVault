import { useCallback, useEffect, useRef, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  CatalogStats,
  ChapterOut,
  ExamOut,
  SubjectOut,
  SyllabusImportLogOut,
  TopicOut,
  UnitOut,
} from "../types";

const STATUS_BADGE: Record<string, string> = {
  running: "bg-info",
  success: "bg-success",
  failed: "bg-danger",
};

type ChildMap<T> = Record<string, T[] | undefined>;

export default function SyllabusCatalog() {
  const { can } = useAuth();
  const canExecute = can("catalog:execute");

  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [exams, setExams] = useState<ExamOut[]>([]);
  const [logs, setLogs] = useState<SyllabusImportLogOut[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [examCode, setExamCode] = useState("NEET");
  const fileRef = useRef<HTMLInputElement>(null);

  const [expandedExam, setExpandedExam] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<ChildMap<SubjectOut>>({});
  const [expandedSubject, setExpandedSubject] = useState<string | null>(null);
  const [units, setUnits] = useState<ChildMap<UnitOut>>({});
  const [expandedUnit, setExpandedUnit] = useState<string | null>(null);
  const [chapters, setChapters] = useState<ChildMap<ChapterOut>>({});
  const [expandedChapter, setExpandedChapter] = useState<string | null>(null);
  const [topics, setTopics] = useState<ChildMap<TopicOut>>({});

  const loadStats = useCallback(async () => {
    const s = await api.get<CatalogStats>("/api/catalog/stats");
    setStats(s.data);
  }, []);

  const loadExams = useCallback(async () => {
    const res = await api.get<ExamOut[]>("/api/catalog/exams");
    setExams(res.data);
  }, []);

  const loadLogs = useCallback(async () => {
    const res = await api.get<SyllabusImportLogOut[]>("/api/catalog/import/logs");
    setLogs(res.data);
  }, []);

  useEffect(() => {
    loadStats().catch((e) => setError(apiError(e)));
    loadExams().catch((e) => setError(apiError(e)));
    loadLogs().catch(() => {});
  }, [loadStats, loadExams, loadLogs]);

  async function toggleExam(exam: ExamOut) {
    if (expandedExam === exam.id) {
      setExpandedExam(null);
      return;
    }
    setExpandedExam(exam.id);
    if (!subjects[exam.id]) {
      try {
        const res = await api.get<SubjectOut[]>(`/api/catalog/exams/${exam.id}/subjects`);
        setSubjects((m) => ({ ...m, [exam.id]: res.data }));
      } catch (e) {
        setError(apiError(e));
      }
    }
  }

  async function toggleSubject(subject: SubjectOut) {
    if (expandedSubject === subject.id) {
      setExpandedSubject(null);
      return;
    }
    setExpandedSubject(subject.id);
    if (!units[subject.id]) {
      try {
        const res = await api.get<UnitOut[]>(`/api/catalog/subjects/${subject.id}/units`);
        setUnits((m) => ({ ...m, [subject.id]: res.data }));
      } catch (e) {
        setError(apiError(e));
      }
    }
  }

  async function toggleUnit(unit: UnitOut) {
    if (expandedUnit === unit.id) {
      setExpandedUnit(null);
      return;
    }
    setExpandedUnit(unit.id);
    if (!chapters[unit.id]) {
      try {
        const res = await api.get<ChapterOut[]>(`/api/catalog/units/${unit.id}/chapters`);
        setChapters((m) => ({ ...m, [unit.id]: res.data }));
      } catch (e) {
        setError(apiError(e));
      }
    }
  }

  async function toggleChapter(chapter: ChapterOut) {
    if (expandedChapter === chapter.id) {
      setExpandedChapter(null);
      return;
    }
    setExpandedChapter(chapter.id);
    if (!topics[chapter.id]) {
      try {
        const res = await api.get<TopicOut[]>(`/api/catalog/chapters/${chapter.id}/topics`);
        setTopics((m) => ({ ...m, [chapter.id]: res.data }));
      } catch (e) {
        setError(apiError(e));
      }
    }
  }

  async function onImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!examCode.trim()) {
      setError("Enter an exam code before importing.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("exam_code", examCode.trim().toUpperCase());
    setBusy(true);
    setError("");
    try {
      await api.post("/api/catalog/import", form);
      await Promise.all([loadStats(), loadExams(), loadLogs()]);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const cards = [
    { label: "Exams", value: stats?.exams ?? 0, icon: "bi-mortarboard", color: "#2563eb" },
    { label: "Subjects", value: stats?.subjects ?? 0, icon: "bi-book", color: "#059669" },
    { label: "Units", value: stats?.units ?? 0, icon: "bi-collection", color: "#0891b2" },
    { label: "Chapters", value: stats?.chapters ?? 0, icon: "bi-journal-text", color: "#d97706" },
    { label: "Topics", value: stats?.topics ?? 0, icon: "bi-tags", color: "#9333ea" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-list-check text-success me-2" />
          Syllabus Catalog
        </h3>
        {canExecute && (
          <div className="d-flex gap-2 align-items-center">
            <input
              className="form-control form-control-sm"
              style={{ width: 140 }}
              placeholder="Exam code (e.g. NEET)"
              value={examCode}
              onChange={(e) => setExamCode(e.target.value)}
            />
            <input ref={fileRef} type="file" accept="application/pdf" className="d-none" onChange={onImport} />
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => fileRef.current?.click()}>
              <i className="bi bi-upload me-1" />
              Import Syllabus PDF
            </button>
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

      <div className="card border-0 shadow-sm mb-3">
        <div className="card-header bg-white fw-semibold">
          <i className="bi bi-diagram-3 me-2" />
          Exam Hierarchy
        </div>
        <div className="list-group list-group-flush">
          {exams.length === 0 && (
            <div className="text-center text-muted py-4">
              No exams yet. Import an official syllabus PDF to populate the catalog.
            </div>
          )}
          {exams.map((exam) => (
            <div key={exam.id} className="list-group-item">
              <button className="btn btn-link text-decoration-none p-0 fw-semibold d-flex align-items-center gap-2" onClick={() => toggleExam(exam)}>
                <i className={`bi ${expandedExam === exam.id ? "bi-chevron-down" : "bi-chevron-right"}`} />
                {exam.name}
                <span className="badge bg-light text-dark text-uppercase">{exam.code}</span>
                {!exam.is_active && <span className="badge bg-secondary">inactive</span>}
              </button>

              {expandedExam === exam.id && (
                <div className="ms-4 mt-2">
                  {(subjects[exam.id] ?? []).length === 0 && (
                    <div className="text-muted small">No subjects.</div>
                  )}
                  {(subjects[exam.id] ?? []).map((subject) => (
                    <div key={subject.id} className="mb-1">
                      <button className="btn btn-link text-decoration-none p-0 d-flex align-items-center gap-2" onClick={() => toggleSubject(subject)}>
                        <i className={`bi ${expandedSubject === subject.id ? "bi-chevron-down" : "bi-chevron-right"}`} />
                        {subject.name}
                        <span className="badge bg-light text-dark text-uppercase small">{subject.code}</span>
                      </button>

                      {expandedSubject === subject.id && (
                        <div className="ms-4 mt-1">
                          {(units[subject.id] ?? []).length === 0 && (
                            <div className="text-muted small">No units.</div>
                          )}
                          {(units[subject.id] ?? []).map((unit) => (
                            <div key={unit.id} className="mb-1">
                              <button className="btn btn-link text-decoration-none p-0 d-flex align-items-center gap-2" onClick={() => toggleUnit(unit)}>
                                <i className={`bi ${expandedUnit === unit.id ? "bi-chevron-down" : "bi-chevron-right"}`} />
                                {unit.name}
                                <span className="badge bg-light text-dark text-uppercase small">{unit.code}</span>
                              </button>

                              {expandedUnit === unit.id && (
                                <div className="ms-4 mt-1">
                                  {(chapters[unit.id] ?? []).length === 0 && (
                                    <div className="text-muted small">No chapters.</div>
                                  )}
                                  {(chapters[unit.id] ?? []).map((chapter) => (
                                    <div key={chapter.id} className="mb-1">
                                      <button className="btn btn-link text-decoration-none p-0 d-flex align-items-center gap-2" onClick={() => toggleChapter(chapter)}>
                                        <i className={`bi ${expandedChapter === chapter.id ? "bi-chevron-down" : "bi-chevron-right"}`} />
                                        {chapter.name}
                                        <span className="badge bg-light text-dark text-uppercase small">{chapter.code}</span>
                                      </button>

                                      {expandedChapter === chapter.id && (
                                        <ul className="ms-4 mt-1 mb-0">
                                          {(topics[chapter.id] ?? []).length === 0 && (
                                            <li className="text-muted small list-unstyled">No topics.</li>
                                          )}
                                          {(topics[chapter.id] ?? []).map((topic) => (
                                            <li key={topic.id} className="small">{topic.name}</li>
                                          ))}
                                        </ul>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card border-0 shadow-sm">
        <div className="card-header bg-white fw-semibold">
          <i className="bi bi-clock-history me-2" />
          Import History
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Exam</th>
                <th>File</th>
                <th>Status</th>
                <th>Subjects</th>
                <th>Units</th>
                <th>Chapters</th>
                <th>Topics</th>
                <th>Created</th>
                <th>Updated</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && (
                <tr><td colSpan={10} className="text-center text-muted py-4">No import attempts yet.</td></tr>
              )}
              {logs.map((log) => (
                <tr key={log.id}>
                  <td><span className="badge bg-light text-dark text-uppercase">{log.exam_code}</span></td>
                  <td className="small">{log.source_file}</td>
                  <td><span className={`badge ${STATUS_BADGE[log.status] ?? "bg-secondary"}`}>{log.status}</span></td>
                  <td>{log.subjects_count}</td>
                  <td>{log.units_count}</td>
                  <td>{log.chapters_count}</td>
                  <td>{log.topics_count}</td>
                  <td>{log.created_count}</td>
                  <td>{log.updated_count}</td>
                  <td className="small text-muted">{new Date(log.started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
