import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
    deleteSession,
    listSessions,
} from "../../services/knowledgeResearchApi";

import {
    KnowledgeSession,
    SessionCreateRequest,
} from "../../types/knowledgeResearch";

import {
    formatDateTime,
    formatDuration,
    sessionDurationSeconds,
    statusBadgeClass,
} from "./format";

interface Props {
    open: boolean;
    onClose: () => void;
    onOpenSession: (sessionId: number) => void;
    onDuplicate: (prefill: Partial<SessionCreateRequest>) => void;
}

export default function HistoryDrawer({
    open,
    onClose,
    onOpenSession,
    onDuplicate,
}: Props) {

    const [sessions, setSessions] = useState<KnowledgeSession[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [confirmId, setConfirmId] = useState<number | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError("");

        try {
            setSessions(await listSessions({}));
        }
        catch {
            setError("Failed to load history.");
        }
        finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (open) {
            load();
            setConfirmId(null);
        }
    }, [open, load]);

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

    if (!open) {
        return null;
    }

    return (
        <>
            <div className="qv-drawer-backdrop" onClick={onClose} />

            <div
                className="qv-drawer"
                role="dialog"
                aria-label="Research history"
            >
                <div className="qv-drawer-header">
                    <i className="bi bi-clock-history text-primary" />
                    <span className="fw-semibold flex-grow-1">
                        Research History
                    </span>
                    <Link
                        className="btn btn-outline-secondary btn-sm"
                        to="/research/history"
                        onClick={onClose}
                    >
                        Full view
                    </Link>
                    <button
                        className="btn btn-sm btn-light"
                        aria-label="Close"
                        onClick={onClose}
                    >
                        <i className="bi bi-x-lg" />
                    </button>
                </div>

                <div className="qv-drawer-body">

                    {error && (
                        <div className="alert alert-danger py-2 small">
                            {error}
                        </div>
                    )}

                    {loading && (
                        <div className="d-flex align-items-center gap-2 text-secondary py-3">
                            <span className="spinner-border spinner-border-sm" />
                            Loading…
                        </div>
                    )}

                    {!loading && sessions.length === 0 && !error && (
                        <div className="text-center text-secondary py-5">
                            <i className="bi bi-inbox d-block fs-2 mb-2" />
                            No research sessions yet.
                        </div>
                    )}

                    {!loading &&
                        sessions.map(session => {
                            const duration = sessionDurationSeconds(session);
                            const running =
                                session.status === "RUNNING" ||
                                session.status === "QUEUED";

                            return (
                                <div
                                    key={session.id}
                                    className="qv-history-item"
                                >
                                    <div className="d-flex align-items-start justify-content-between gap-2">
                                        <div
                                            className="fw-medium text-truncate"
                                            title={session.input_value}
                                        >
                                            {session.input_value}
                                        </div>
                                        <span
                                            className={`badge ${statusBadgeClass(
                                                session.status
                                            )}`}
                                        >
                                            {session.status}
                                            {running &&
                                                ` ${session.progress}%`}
                                        </span>
                                    </div>

                                    <div className="small text-secondary mt-1 d-flex flex-wrap column-gap-3">
                                        <span>
                                            <i className="bi bi-calendar3 me-1" />
                                            {formatDateTime(
                                                session.created_at
                                            )}
                                        </span>
                                        <span>
                                            <i className="bi bi-collection me-1" />
                                            {session.source_count_requested}{" "}
                                            source
                                            {session.source_count_requested !==
                                            1
                                                ? "s"
                                                : ""}
                                        </span>
                                        {duration !== null && (
                                            <span>
                                                <i className="bi bi-stopwatch me-1" />
                                                {formatDuration(duration)}
                                            </span>
                                        )}
                                        {(session.total_cost ?? 0) > 0 && (
                                            <span>
                                                <i className="bi bi-cash-coin me-1" />
                                                $
                                                {(
                                                    session.total_cost ?? 0
                                                ).toFixed(4)}
                                            </span>
                                        )}
                                    </div>

                                    <div className="d-flex gap-2 mt-2">
                                        <button
                                            className="btn btn-sm btn-outline-primary"
                                            onClick={() => {
                                                onOpenSession(session.id);
                                                onClose();
                                            }}
                                        >
                                            <i className="bi bi-box-arrow-up-right me-1" />
                                            Open
                                        </button>

                                        <button
                                            className="btn btn-sm btn-outline-secondary"
                                            onClick={() => {
                                                onDuplicate({
                                                    mode: session.mode,
                                                    input_value:
                                                        session.input_value,
                                                    source_count:
                                                        session.source_count_requested,
                                                    source_type:
                                                        session.source_type,
                                                    ai_provider:
                                                        session.ai_provider,
                                                    ai_model: session.ai_model,
                                                    temperature:
                                                        session.temperature,
                                                    max_tokens:
                                                        session.max_tokens,
                                                });
                                                onClose();
                                            }}
                                        >
                                            <i className="bi bi-copy me-1" />
                                            Duplicate
                                        </button>

                                        {confirmId === session.id ? (
                                            <span className="ms-auto d-flex gap-1">
                                                <button
                                                    className="btn btn-sm btn-danger"
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
                                                <button
                                                    className="btn btn-sm btn-light"
                                                    onClick={() =>
                                                        setConfirmId(null)
                                                    }
                                                >
                                                    Keep
                                                </button>
                                            </span>
                                        ) : (
                                            <button
                                                className="btn btn-sm btn-outline-danger ms-auto"
                                                disabled={running}
                                                title={
                                                    running
                                                        ? "Cancel the session before deleting it"
                                                        : "Delete session"
                                                }
                                                onClick={() =>
                                                    setConfirmId(session.id)
                                                }
                                            >
                                                <i className="bi bi-trash" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                </div>
            </div>
        </>
    );
}
