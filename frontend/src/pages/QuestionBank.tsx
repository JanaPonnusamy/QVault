import { useCallback, useEffect, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import ConfidenceBadge from "../components/ConfidenceBadge";
import Modal from "../components/Modal";
import type {
  BankQuestion,
  BankQuestionDetail,
  BankQuestionOption,
  BankQuestionStats,
  BankQuestionTopic,
  ChapterOut,
  ExamOut,
  SubjectOut,
  TopicOut,
  UnitOut,
} from "../types";
import { QUESTION_STATUSES, QUESTION_TYPES } from "../types";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-secondary",
  pending_review: "bg-warning text-dark",
  approved: "bg-success",
  rejected: "bg-danger",
  duplicate: "bg-dark",
};

const PAGE_SIZE = 25;

interface OptionDraft {
  label: string;
  text: string;
  is_correct: boolean;
}

const EMPTY_OPTIONS: OptionDraft[] = [
  { label: "A", text: "", is_correct: false },
  { label: "B", text: "", is_correct: false },
  { label: "C", text: "", is_correct: false },
  { label: "D", text: "", is_correct: false },
];

interface TopicDraft {
  subject_id: string | null;
  unit_id: string | null;
  chapter_id: string | null;
  topic_id: string | null;
  is_primary: boolean;
  subject_name?: string;
  unit_name?: string;
  chapter_name?: string;
  topic_name?: string;
}

// Cascading exam -> subject -> unit -> chapter -> topic picker, reading the
// Syllabus Catalog (/api/catalog/*) — the picker is shared by the filter bar
// and the create/edit form.
function useCatalogPicker() {
  const [exams, setExams] = useState<ExamOut[]>([]);
  const [subjects, setSubjects] = useState<SubjectOut[]>([]);
  const [units, setUnits] = useState<UnitOut[]>([]);
  const [chapters, setChapters] = useState<ChapterOut[]>([]);
  const [topics, setTopics] = useState<TopicOut[]>([]);

  useEffect(() => {
    api.get<ExamOut[]>("/api/catalog/exams").then((r) => setExams(r.data)).catch(() => {});
  }, []);

  const loadSubjects = useCallback(async (examId: string) => {
    if (!examId) { setSubjects([]); return; }
    const r = await api.get<SubjectOut[]>(`/api/catalog/exams/${examId}/subjects`);
    setSubjects(r.data);
  }, []);
  const loadUnits = useCallback(async (subjectId: string) => {
    if (!subjectId) { setUnits([]); return; }
    const r = await api.get<UnitOut[]>(`/api/catalog/subjects/${subjectId}/units`);
    setUnits(r.data);
  }, []);
  const loadChapters = useCallback(async (unitId: string) => {
    if (!unitId) { setChapters([]); return; }
    const r = await api.get<ChapterOut[]>(`/api/catalog/units/${unitId}/chapters`);
    setChapters(r.data);
  }, []);
  const loadTopics = useCallback(async (chapterId: string) => {
    if (!chapterId) { setTopics([]); return; }
    const r = await api.get<TopicOut[]>(`/api/catalog/chapters/${chapterId}/topics`);
    setTopics(r.data);
  }, []);

  return { exams, subjects, units, chapters, topics, loadSubjects, loadUnits, loadChapters, loadTopics };
}

export default function QuestionBank() {
  const { can } = useAuth();
  const canCreate = can("question_bank:create");
  const canUpdate = can("question_bank:update");
  const canDelete = can("question_bank:delete");

  const [stats, setStats] = useState<BankQuestionStats | null>(null);
  const [items, setItems] = useState<BankQuestion[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const filterCatalog = useCatalogPicker();
  const [search, setSearch] = useState("");
  const [filterExamId, setFilterExamId] = useState("");
  const [filterSubjectId, setFilterSubjectId] = useState("");
  const [filterUnitId, setFilterUnitId] = useState("");
  const [filterChapterId, setFilterChapterId] = useState("");
  const [filterTopicId, setFilterTopicId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  // Defaults to MCQ: GK Scraper batches vary in composition (some runs land
  // on article-heavy pages, producing mostly "essay" rows), which was
  // burying the real question+answer content under scraped article text.
  // "All Types" is one click away in the dropdown below.
  const [typeFilter, setTypeFilter] = useState("mcq");

  const formCatalog = useCatalogPicker();
  const [editing, setEditing] = useState<BankQuestionDetail | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [fExam, setFExam] = useState("");
  const [fYear, setFYear] = useState("");
  const [fDifficulty, setFDifficulty] = useState("");
  const [fType, setFType] = useState("mcq");
  const [fText, setFText] = useState("");
  const [fOptions, setFOptions] = useState<OptionDraft[]>(EMPTY_OPTIONS);
  const [fCorrectAnswer, setFCorrectAnswer] = useState("");
  const [fSolution, setFSolution] = useState("");
  const [fTopics, setFTopics] = useState<TopicDraft[]>([]);
  const [pickExamId, setPickExamId] = useState("");
  const [pickSubjectId, setPickSubjectId] = useState("");
  const [pickUnitId, setPickUnitId] = useState("");
  const [pickChapterId, setPickChapterId] = useState("");
  const [pickTopicId, setPickTopicId] = useState("");

  const loadStats = useCallback(async () => {
    const s = await api.get<BankQuestionStats>("/api/question-bank/stats");
    setStats(s.data);
  }, []);

  const loadList = useCallback(async () => {
    try {
      const res = await api.get<{ items: BankQuestion[]; total: number }>("/api/question-bank", {
        params: {
          search: search || undefined,
          subject_id: filterSubjectId || undefined,
          unit_id: filterUnitId || undefined,
          chapter_id: filterChapterId || undefined,
          topic_id: filterTopicId || undefined,
          status: statusFilter || undefined,
          question_type: typeFilter || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        },
      });
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      setError(apiError(e));
    }
  }, [search, filterSubjectId, filterUnitId, filterChapterId, filterTopicId, statusFilter, typeFilter, page]);

  useEffect(() => {
    loadStats().catch((e) => setError(apiError(e)));
  }, [loadStats]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  function resetForm() {
    setEditing(null);
    setFExam("");
    setFYear("");
    setFDifficulty("");
    setFType("mcq");
    setFText("");
    setFOptions(EMPTY_OPTIONS.map((o) => ({ ...o })));
    setFCorrectAnswer("");
    setFSolution("");
    setFTopics([]);
    setPickExamId(""); setPickSubjectId(""); setPickUnitId(""); setPickChapterId(""); setPickTopicId("");
  }

  function openCreate() {
    resetForm();
    setShowForm(true);
  }

  async function openEdit(id: string) {
    try {
      const res = await api.get<BankQuestionDetail>(`/api/question-bank/${id}`);
      const q = res.data;
      setEditing(q);
      setFExam(q.exam);
      setFYear(q.year ? String(q.year) : "");
      setFDifficulty(q.difficulty);
      setFType(q.question_type);
      setFText(q.question_text);
      setFCorrectAnswer(q.correct_answer_text);
      setFSolution(q.solutions[0]?.solution_text ?? "");
      setFOptions(
        q.options.length
          ? q.options.map((o: BankQuestionOption) => ({ label: o.label, text: o.text, is_correct: o.is_correct }))
          : EMPTY_OPTIONS.map((o) => ({ ...o }))
      );
      setFTopics(
        q.topics.map((t: BankQuestionTopic) => ({
          subject_id: t.subject_id, unit_id: t.unit_id, chapter_id: t.chapter_id, topic_id: t.topic_id,
          is_primary: t.is_primary,
        }))
      );
      setShowForm(true);
    } catch (e) {
      setError(apiError(e));
    }
  }

  const usesOptions = fType === "mcq" || fType === "msq";

  function addTopicMapping() {
    if (!pickSubjectId) return;
    const subject = formCatalog.subjects.find((s) => s.id === pickSubjectId);
    const unit = formCatalog.units.find((u) => u.id === pickUnitId);
    const chapter = formCatalog.chapters.find((c) => c.id === pickChapterId);
    const topic = formCatalog.topics.find((t) => t.id === pickTopicId);
    setFTopics((prev) => [
      ...prev,
      {
        subject_id: pickSubjectId || null,
        unit_id: pickUnitId || null,
        chapter_id: pickChapterId || null,
        topic_id: pickTopicId || null,
        is_primary: prev.length === 0,
        subject_name: subject?.name,
        unit_name: unit?.name,
        chapter_name: chapter?.name,
        topic_name: topic?.name,
      },
    ]);
    setPickSubjectId(""); setPickUnitId(""); setPickChapterId(""); setPickTopicId("");
  }

  function removeTopicMapping(idx: number) {
    setFTopics((prev) => prev.filter((_, i) => i !== idx));
  }

  function makePrimary(idx: number) {
    setFTopics((prev) => prev.map((t, i) => ({ ...t, is_primary: i === idx })));
  }

  async function save() {
    if (!fText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const body = {
        exam: fExam,
        year: fYear ? Number(fYear) : null,
        difficulty: fDifficulty,
        question_type: fType,
        question_text: fText,
        correct_answer_text: usesOptions ? "" : fCorrectAnswer,
        options: usesOptions ? fOptions.filter((o) => o.text.trim()) : [],
        topics: fTopics.map(({ subject_id, unit_id, chapter_id, topic_id, is_primary }) => ({
          subject_id, unit_id, chapter_id, topic_id, is_primary,
        })),
        solution_text: fSolution,
      };
      if (editing) {
        await api.put(`/api/question-bank/${editing.id}`, body);
      } else {
        await api.post("/api/question-bank", body);
      }
      setShowForm(false);
      resetForm();
      await Promise.all([loadList(), loadStats()]);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this question?")) return;
    setBusy(true);
    try {
      await api.delete(`/api/question-bank/${id}`);
      await Promise.all([loadList(), loadStats()]);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(id: string, action: "approve" | "reject") {
    setBusy(true);
    try {
      await api.post(`/api/question-bank/${id}/${action}`);
      await Promise.all([loadList(), loadStats()]);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const cards = [
    { label: "Total", value: stats?.total ?? 0, icon: "bi-collection", color: "#2563eb" },
    { label: "Approved", value: stats?.approved ?? 0, icon: "bi-check-circle", color: "#16a34a" },
    { label: "Pending Review", value: stats?.pending_review ?? 0, icon: "bi-hourglass-split", color: "#d97706" },
    { label: "Duplicates", value: stats?.duplicate ?? 0, icon: "bi-files", color: "#9333ea" },
    { label: "With Solution", value: stats?.with_solution ?? 0, icon: "bi-lightbulb", color: "#0d9488" },
    { label: "Sources", value: stats?.sources ?? 0, icon: "bi-link-45deg", color: "#dc2626" },
  ];

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-collection text-primary me-2" />
          Question Bank
        </h3>
        {canCreate && (
          <button className="btn btn-primary" onClick={openCreate}>
            <i className="bi bi-plus-lg me-1" />
            Add Question
          </button>
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

      <div className="card border-0 shadow-sm">
        <div className="card-header bg-white">
          <div className="row g-2">
            <div className="col-md-3">
              <input className="form-control form-control-sm" placeholder="Search question text..." value={search}
                onChange={(e) => { setPage(0); setSearch(e.target.value); }} />
            </div>
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={filterExamId}
                onChange={(e) => {
                  const v = e.target.value;
                  setPage(0); setFilterExamId(v); setFilterSubjectId(""); setFilterUnitId(""); setFilterChapterId(""); setFilterTopicId("");
                  filterCatalog.loadSubjects(v);
                }}>
                <option value="">All Exams</option>
                {filterCatalog.exams.map((ex) => <option key={ex.id} value={ex.id}>{ex.name}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={filterSubjectId} disabled={!filterExamId}
                onChange={(e) => {
                  const v = e.target.value;
                  setPage(0); setFilterSubjectId(v); setFilterUnitId(""); setFilterChapterId(""); setFilterTopicId("");
                  filterCatalog.loadUnits(v);
                }}>
                <option value="">All Subjects</option>
                {filterCatalog.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={filterUnitId} disabled={!filterSubjectId}
                onChange={(e) => {
                  const v = e.target.value;
                  setPage(0); setFilterUnitId(v); setFilterChapterId(""); setFilterTopicId("");
                  filterCatalog.loadChapters(v);
                }}>
                <option value="">All Units</option>
                {filterCatalog.units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={filterChapterId} disabled={!filterUnitId}
                onChange={(e) => {
                  const v = e.target.value;
                  setPage(0); setFilterChapterId(v); setFilterTopicId("");
                  filterCatalog.loadTopics(v);
                }}>
                <option value="">All Chapters</option>
                {filterCatalog.chapters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="col-md-1">
              <select className="form-select form-select-sm" value={filterTopicId} disabled={!filterChapterId}
                onChange={(e) => { setPage(0); setFilterTopicId(e.target.value); }}>
                <option value="">Topic</option>
                {filterCatalog.topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>
          <div className="row g-2 mt-1">
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={statusFilter}
                onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }}>
                <option value="">All Statuses</option>
                {QUESTION_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <select className="form-select form-select-sm" value={typeFilter}
                onChange={(e) => { setPage(0); setTypeFilter(e.target.value); }}>
                <option value="">All Types</option>
                {QUESTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Question</th>
                <th>Type</th>
                <th>Exam / Year</th>
                <th>Stage</th>
                <th>Status</th>
                <th>Confidence</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={7} className="text-center text-muted py-4">
                  No questions yet. Add one manually or wire up an acquisition source.
                </td></tr>
              )}
              {items.map((q) => (
                <tr key={q.id}>
                  <td style={{ maxWidth: 420 }}>
                    <div className="text-truncate" title={q.question_text}>{q.question_text}</div>
                    {q.duplicate_score >= 1 && <span className="badge bg-dark mt-1">possible duplicate</span>}
                  </td>
                  <td><span className="badge bg-light text-dark text-uppercase">{q.question_type}</span></td>
                  <td className="small">{[q.exam, q.year].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="small text-muted">{q.current_stage}</td>
                  <td><span className={`badge ${STATUS_BADGE[q.status] ?? "bg-secondary"}`}>{q.status}</span></td>
                  <td><ConfidenceBadge value={q.confidence} /></td>
                  <td className="text-end text-nowrap">
                    {canUpdate && (
                      <>
                        <button className="btn btn-sm btn-outline-primary me-1" disabled={busy} onClick={() => openEdit(q.id)} title="Edit">
                          <i className="bi bi-pencil" />
                        </button>
                        {q.status !== "approved" && (
                          <button className="btn btn-sm btn-outline-success me-1" disabled={busy} onClick={() => setStatus(q.id, "approve")} title="Approve">
                            <i className="bi bi-check-lg" />
                          </button>
                        )}
                        {q.status !== "rejected" && (
                          <button className="btn btn-sm btn-outline-warning me-1" disabled={busy} onClick={() => setStatus(q.id, "reject")} title="Reject">
                            <i className="bi bi-x-lg" />
                          </button>
                        )}
                      </>
                    )}
                    {canDelete && (
                      <button className="btn btn-sm btn-outline-danger" disabled={busy} onClick={() => remove(q.id)} title="Delete">
                        <i className="bi bi-trash" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {total > PAGE_SIZE && (
          <div className="card-footer bg-white d-flex justify-content-between align-items-center">
            <span className="small text-muted">Page {page + 1} of {totalPages}</span>
            <div className="btn-group btn-group-sm">
              <button className="btn btn-outline-secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                <i className="bi bi-chevron-left" />
              </button>
              <button className="btn btn-outline-secondary" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
                <i className="bi bi-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      <Modal
        title={editing ? "Edit Question" : "Add Question"}
        open={showForm}
        onClose={() => setShowForm(false)}
        size="lg"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={busy || !fText.trim()} onClick={save}>Save</button>
          </>
        }
      >
        <div className="row g-2 mb-2">
          <div className="col-md-3">
            <label className="form-label small">Exam (label)</label>
            <input className="form-control form-control-sm" value={fExam} onChange={(e) => setFExam(e.target.value)} placeholder="e.g. NEET" />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Year</label>
            <input className="form-control form-control-sm" type="number" value={fYear} onChange={(e) => setFYear(e.target.value)} />
          </div>
          <div className="col-md-3">
            <label className="form-label small">Difficulty</label>
            <select className="form-select form-select-sm" value={fDifficulty} onChange={(e) => setFDifficulty(e.target.value)}>
              <option value="">—</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
          <div className="col-md-3">
            <label className="form-label small">Type</label>
            <select className="form-select form-select-sm" value={fType} onChange={(e) => setFType(e.target.value)}>
              {QUESTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="mb-2">
          <label className="form-label small">Question Text</label>
          <textarea className="form-control" rows={3} value={fText} onChange={(e) => setFText(e.target.value)} />
        </div>

        {usesOptions ? (
          <div className="mb-2">
            <label className="form-label small">Options</label>
            {fOptions.map((opt, idx) => (
              <div className="input-group input-group-sm mb-1" key={idx}>
                <span className="input-group-text">{opt.label}</span>
                <input className="form-control" value={opt.text}
                  onChange={(e) => setFOptions((prev) => prev.map((o, i) => (i === idx ? { ...o, text: e.target.value } : o)))} />
                <span className="input-group-text">
                  <input type={fType === "msq" ? "checkbox" : "radio"} name="correct" checked={opt.is_correct}
                    onChange={() => setFOptions((prev) => prev.map((o, i) => ({
                      ...o,
                      is_correct: fType === "msq" ? (i === idx ? !o.is_correct : o.is_correct) : i === idx,
                    })))} />
                </span>
              </div>
            ))}
            <div className="form-text">Check the correct option(s).</div>
          </div>
        ) : (
          <div className="mb-2">
            <label className="form-label small">Correct Answer</label>
            <input className="form-control" value={fCorrectAnswer} onChange={(e) => setFCorrectAnswer(e.target.value)} />
          </div>
        )}

        <div className="mb-2">
          <label className="form-label small">Solution / Explanation</label>
          <textarea className="form-control" rows={2} value={fSolution} onChange={(e) => setFSolution(e.target.value)} />
        </div>

        <div className="mb-1">
          <label className="form-label small">Topic Mappings</label>
          <div className="border rounded p-2 mb-2">
            <div className="row g-2">
              <div className="col-md-3">
                <select className="form-select form-select-sm" value={pickExamId}
                  onChange={(e) => { const v = e.target.value; setPickExamId(v); setPickSubjectId(""); setPickUnitId(""); setPickChapterId(""); setPickTopicId(""); formCatalog.loadSubjects(v); }}>
                  <option value="">Exam</option>
                  {formCatalog.exams.map((ex) => <option key={ex.id} value={ex.id}>{ex.name}</option>)}
                </select>
              </div>
              <div className="col-md-3">
                <select className="form-select form-select-sm" value={pickSubjectId} disabled={!pickExamId}
                  onChange={(e) => { const v = e.target.value; setPickSubjectId(v); setPickUnitId(""); setPickChapterId(""); setPickTopicId(""); formCatalog.loadUnits(v); }}>
                  <option value="">Subject</option>
                  {formCatalog.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="col-md-2">
                <select className="form-select form-select-sm" value={pickUnitId} disabled={!pickSubjectId}
                  onChange={(e) => { const v = e.target.value; setPickUnitId(v); setPickChapterId(""); setPickTopicId(""); formCatalog.loadChapters(v); }}>
                  <option value="">Unit</option>
                  {formCatalog.units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </div>
              <div className="col-md-2">
                <select className="form-select form-select-sm" value={pickChapterId} disabled={!pickUnitId}
                  onChange={(e) => { const v = e.target.value; setPickChapterId(v); setPickTopicId(""); formCatalog.loadTopics(v); }}>
                  <option value="">Chapter</option>
                  {formCatalog.chapters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div className="col-md-1">
                <select className="form-select form-select-sm" value={pickTopicId} disabled={!pickChapterId}
                  onChange={(e) => setPickTopicId(e.target.value)}>
                  <option value="">Topic</option>
                  {formCatalog.topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="col-md-1">
                <button className="btn btn-sm btn-outline-primary w-100" disabled={!pickSubjectId} onClick={addTopicMapping}>
                  <i className="bi bi-plus-lg" />
                </button>
              </div>
            </div>
          </div>
          {fTopics.length === 0 && <div className="text-muted small">No topic mappings yet.</div>}
          {fTopics.map((t, idx) => (
            <div key={idx} className="d-flex align-items-center justify-content-between border rounded px-2 py-1 mb-1">
              <span className="small">
                {[t.subject_name, t.unit_name, t.chapter_name, t.topic_name].filter(Boolean).join(" → ")}
                {t.is_primary && <span className="badge bg-primary ms-2">primary</span>}
              </span>
              <div>
                {!t.is_primary && (
                  <button className="btn btn-sm btn-link" onClick={() => makePrimary(idx)}>make primary</button>
                )}
                <button className="btn btn-sm btn-outline-danger" onClick={() => removeTopicMapping(idx)}>
                  <i className="bi bi-x" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
