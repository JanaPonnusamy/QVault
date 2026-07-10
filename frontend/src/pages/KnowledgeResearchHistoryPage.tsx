import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
    deleteSession,
    listSessions,
} from "../services/knowledgeResearchApi";

import {
    formatDateTime,
    formatDuration,
    sessionDurationSeconds,
    statusBadgeClass,
} from "../components/knowledge-research/format";

import {
    HistoryFilters,
    KnowledgeSession,
} from "../types/knowledgeResearch";

const STATUSES = ["", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "QUEUED"];

const EMPTY_FILTERS: HistoryFilters = {
    status: "",
    topic: "",
    date_from: "",
    date_to: "",
    provider: "",
    source_type: "",
};

export default function KnowledgeResearchHistoryPage() {

    const navigate = useNavigate();

    const [filters, setFilters] = useState<HistoryFilters>(EMPTY_FILTERS);
    const [sessions, setSessions] = useState<KnowledgeSession[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [confirmId, setConfirmId] = useState<number | null>(null);
    const [deletingId, setDeletingId] = useState<number | null>(null);

    const load = useCallback(async (activeFilters: HistoryFilters) => {
        setLoading(true);
        setError("");

        try {
            setSessions(await listSessions(activeFilters));
        }
        catch {
            setError("Failed to load history.");
        }
        finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load(EMPTY_FILTERS);
    }, [load]);

    function update(field: keyof HistoryFilters, value: string) {
        setFilters(previous => ({ ...previous, [field]: value }));
    }

    async function handleDelete(sessionId: number) {
        setDeletingId(sessionId);
        setError("");

        try {
            await deleteSession(sessionId);
            setSessions(current =>
                current.filter(session => session.id !== sessionId)
            );
        }
        catch (deleteError: any) {
            setError(
                deleteError?.response?.data?.detail ||
                "Failed to delete session."
            );
        }
        finally {
            setDeletingId(null);
            setConfirmId(null);
        }
    }

    function handleDuplicate(session: KnowledgeSession) {
        navigate("/research", {
            state: {
                prefill: {
                    mode: session.mode,
                    input_value: session.input_value,
                    source_count: session.source_count_requested,
                    source_type: session.source_type,
                    ai_provider: session.ai_provider,
                    ai_model: session.ai_model,
                    temperature: session.temperature,
                    max_tokens: session.max_tokens,
                },
            },
        });
    }

    return (
        <div className="qv-research d-flex flex-column gap-4">

            <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap flex-md-nowrap">
                <div style={{ minWidth: 0 }}>
                    <h1 className="h3 fw-bold mb-1">Research History</h1>
                    <p className="text-secondary mb-0">
                        Past knowledge research sessions
                    </p>
                </div>

                <Link className="btn btn-primary flex-shrink-0" to="/research">
                    <i className="bi bi-plus-lg me-2" />
                    New Research
                </Link>
            </div>

            <div className="card">
                <div className="card-body">
                    <div className="row g-3 align-items-end">

                        <div className="col-6 col-md-2">
                            <label className="form-label small fw-medium mb-1">
                                Status
                            </label>
                            <select
                                className="form-select form-select-sm"
                                value={filters.status}
                                onChange={event =>
                                    update("status", event.target.value)
                                }
                            >
                                {STATUSES.map(status => (
                                    <option key={status} value={status}>
                                        {status || "All"}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="col-6 col-md-3">
                            <label className="form-label small fw-medium mb-1">
                                Topic
                            </label>
                            <input
                                className="form-control form-control-sm"
                                placeholder="contains…"
                                value={filters.topic}
                                onChange={event =>
                                    update("topic", event.target.value)
                                }
                            />
                        </div>

                        <div className="col-6 col-md-2">
                            <label className="form-label small fw-medium mb-1">
                                From
                            </label>
                            <input
                                type="date"
                                className="form-control form-control-sm"
                                value={filters.date_from}
                                onChange={event =>
                                    update("date_from", event.target.value)
                                }
                            />
                        </div>

                        <div className="col-6 col-md-2">
                            <label className="form-label small fw-medium mb-1">
                                To
                            </label>
                            <input
                                type="date"
                                className="form-control form-control-sm"
                                value={filters.date_to}
                                onChange={event =>
                                    update("date_to", event.target.value)
                                }
                            />
                        </div>

                        <div className="col-12 col-md-3 d-flex gap-2">
                            <button
                                className="btn btn-primary btn-sm"
                                onClick={() => load(filters)}
                            >
                                <i className="bi bi-funnel me-1" />
                                Apply
                            </button>
                            <button
                                className="btn btn-outline-secondary btn-sm"
                                onClick={() => {
                                    setFilters(EMPTY_FILTERS);
                                    load(EMPTY_FILTERS);
                                }}
                            >
                                Reset
                            </button>
                        </div>

                    </div>
                </div>
            </div>

            {error && (
                <div className="alert alert-danger mb-0">
                    <i className="bi bi-exclamation-octagon me-2" />
                    {error}
                </div>
            )}

            <div className="card">
                <div className="table-responsive">
                    <table className="table table-hover align-middle mb-0">
                        <thead>
                            <tr className="text-secondary small">
                                <th className="ps-3">Title</th>
                                <th>Date</th>
                                <th>Sources</th>
                                <th>Provider / Model</th>
                                <th>Status</th>
                                <th>Duration</th>
                                <th>Cost</th>
                                <th className="text-end pe-3">Actions</th>
                            </tr>
                        </thead>

                        <tbody>
                            {loading && (
                                <tr>
                                    <td
                                        className="p-3 text-secondary"
                                        colSpan={8}
                                    >
                                        <span className="spinner-border spinner-border-sm me-2" />
                                        Loading…
                                    </td>
                                </tr>
                            )}

                            {!loading && !sessions.length && (
                                <tr>
                                    <td
                                        className="p-4 text-center text-secondary"
                                        colSpan={8}
                                    >
                                        No sessions found.
                                    </td>
                                </tr>
                            )}

                            {!loading &&
                                sessions.map(session => {
                                    const duration =
                                        sessionDurationSeconds(session);
                                    const running =
                                        session.status === "RUNNING" ||
                                        session.status === "QUEUED";

                                    return (
                                        <tr key={session.id}>
                                            <td
                                                className="ps-3 fw-medium"
                                                style={{ maxWidth: 280 }}
                                            >
                                                <Link
                                                    className="text-decoration-none d-block text-truncate"
                                                    to={`/research/${session.id}`}
                                                    title={session.input_value}
                                                >
                                                    {session.input_value}
                                                </Link>
                                                <span className="small text-secondary fw-normal">
                                                    #{session.id} ·{" "}
                                                    {session.mode}
                                                </span>
                                            </td>
                                            <td className="text-nowrap small">
                                                {formatDateTime(
                                                    session.created_at
                                                )}
                                            </td>
                                            <td>
                                                {
                                                    session.source_count_requested
                                                }
                                            </td>
                                            <td
                                                className="small"
                                                style={{ maxWidth: 200 }}
                                            >
                                                <div className="text-truncate">
                                                    {session.ai_provider} /{" "}
                                                    {session.ai_model}
                                                </div>
                                            </td>
                                            <td>
                                                <span
                                                    className={`badge ${statusBadgeClass(
                                                        session.status
                                                    )}`}
                                                >
                                                    {session.status}
                                                    {running &&
                                                        ` ${session.progress}%`}
                                                </span>
                                            </td>
                                            <td className="text-nowrap small">
                                                {duration !== null
                                                    ? formatDuration(duration)
                                                    : "—"}
                                            </td>
                                            <td className="text-nowrap small">
                                                {(session.total_cost ?? 0) > 0
                                                    ? `$${(
                                                          session.total_cost ??
                                                          0
                                                      ).toFixed(4)}`
                                                    : "—"}
                                            </td>
                                            <td className="text-end pe-3 text-nowrap">
                                                <div
                                                    className="btn-group btn-group-sm"
                                                    role="group"
                                                >
                                                    <Link
                                                        className="btn btn-outline-primary"
                                                        to={`/research/${session.id}`}
                                                        title="Open"
                                                    >
                                                        <i className="bi bi-box-arrow-up-right" />
                                                    </Link>
                                                    <button
                                                        className="btn btn-outline-secondary"
                                                        title="Duplicate"
                                                        onClick={() =>
                                                            handleDuplicate(
                                                                session
                                                            )
                                                        }
                                                    >
                                                        <i className="bi bi-copy" />
                                                    </button>
                                                    {confirmId ===
                                                    session.id ? (
                                                        <button
                                                            className="btn btn-danger"
                                                            title="Confirm delete"
                                                            disabled={
                                                                deletingId ===
                                                                session.id
                                                            }
                                                            onClick={() =>
                                                                handleDelete(
                                                                    session.id
                                                                )
                                                            }
                                                        >
                                                            {deletingId ===
                                                            session.id ? (
                                                                <span className="spinner-border spinner-border-sm" />
                                                            ) : (
                                                                "Confirm"
                                                            )}
                                                        </button>
                                                    ) : (
                                                        <button
                                                            className="btn btn-outline-danger"
                                                            title={
                                                                running
                                                                    ? "Cancel the session before deleting it"
                                                                    : "Delete"
                                                            }
                                                            disabled={running}
                                                            onClick={() =>
                                                                setConfirmId(
                                                                    session.id
                                                                )
                                                            }
                                                        >
                                                            <i className="bi bi-trash" />
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    );
}
