import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import HistoryDrawer from "../components/knowledge-research/HistoryDrawer";
import ProgressTracker from "../components/knowledge-research/ProgressTracker";
import ResearchForm from "../components/knowledge-research/ResearchForm";
import ResultsView from "../components/knowledge-research/ResultsView";
import SettingsDrawer from "../components/knowledge-research/SettingsDrawer";

import {
    cancelSession,
    createSession,
    getProviders,
    getResults,
} from "../services/knowledgeResearchApi";

import {
    KnowledgeProviders,
    KnowledgeResults,
    KnowledgeSession,
    SessionCreateRequest,
} from "../types/knowledgeResearch";

const POLL_INTERVAL_MS = 3000;

const TERMINAL_STATUSES = ["COMPLETED", "FAILED", "CANCELLED"];

export default function KnowledgeResearchPage() {

    const { sessionId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [providers, setProviders] =
        useState<KnowledgeProviders | null>(null);

    const [session, setSession] =
        useState<KnowledgeSession | null>(null);

    const [results, setResults] =
        useState<KnowledgeResults | null>(null);

    const [submitting, setSubmitting] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState("");

    const [historyOpen, setHistoryOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);

    const prefill = (location.state as {
        prefill?: Partial<SessionCreateRequest>;
    } | null)?.prefill;

    const pollRef = useRef<number | null>(null);

    useEffect(() => {
        getProviders()
            .then(setProviders)
            .catch(() => setError("Backend is not reachable."));
    }, []);

    const stopPolling = useCallback(() => {
        if (pollRef.current !== null) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    const refresh = useCallback(
        async (id: number) => {
            try {
                const current = await getResults(id);

                setSession(current.session);
                setResults(current);

                if (TERMINAL_STATUSES.includes(current.session.status)) {
                    stopPolling();
                }
            }
            catch {
                stopPolling();
                setError("Failed to load session.");
            }
        },
        [stopPolling]
    );

    useEffect(() => {
        stopPolling();
        setSession(null);
        setResults(null);
        setError("");

        const id = Number(sessionId);

        if (!id) {
            return;
        }

        refresh(id);

        pollRef.current = window.setInterval(
            () => refresh(id),
            POLL_INTERVAL_MS
        );

        return stopPolling;
    }, [sessionId, refresh, stopPolling]);

    async function handleStart(request: SessionCreateRequest) {
        setSubmitting(true);
        setError("");

        try {
            const id = await createSession(request);
            navigate(`/research/${id}`);
        }
        catch (requestError: any) {
            setError(
                requestError?.response?.data?.detail ||
                "Failed to start research."
            );
        }
        finally {
            setSubmitting(false);
        }
    }

    async function handleCancel() {
        const id = Number(sessionId);

        if (!id) {
            return;
        }

        setCancelling(true);

        try {
            await cancelSession(id);
            await refresh(id);
        }
        catch (cancelError: any) {
            setError(
                cancelError?.response?.data?.detail ||
                "Failed to cancel session."
            );
        }
        finally {
            setCancelling(false);
        }
    }

    function handleDuplicate(values: Partial<SessionCreateRequest>) {
        navigate("/research", { state: { prefill: values } });
    }

    const showResults =
        session?.status === "COMPLETED" && results?.report !== undefined;

    return (
        <div className="qv-research d-flex flex-column gap-4 pb-2">

            {/* Header */}
            <div className="d-flex align-items-start justify-content-between gap-3 flex-wrap flex-md-nowrap">
                <div style={{ minWidth: 0 }}>
                    <h1 className="h3 fw-bold mb-1">Knowledge Research</h1>
                    <p className="text-secondary mb-0">
                        Research any topic across sources and distill it into
                        facts, consensus and a report — powered by the AI
                        provider of your choice.
                    </p>
                </div>

                <div className="d-flex gap-2 flex-shrink-0">
                    <button
                        className="btn btn-outline-secondary"
                        onClick={() => setHistoryOpen(true)}
                    >
                        <i className="bi bi-clock-history me-2" />
                        History
                    </button>
                    <button
                        className="btn btn-outline-secondary"
                        onClick={() => setSettingsOpen(true)}
                        aria-label="Settings"
                    >
                        <i className="bi bi-gear" />
                    </button>
                </div>
            </div>

            {error && (
                <div className="alert alert-danger d-flex align-items-center mb-0">
                    <i className="bi bi-exclamation-octagon me-2" />
                    {error}
                </div>
            )}

            {!sessionId && (
                <ResearchForm
                    key={JSON.stringify(prefill) || "blank"}
                    providers={providers}
                    submitting={submitting}
                    prefill={prefill}
                    onStart={handleStart}
                    onOpenSettings={() => setSettingsOpen(true)}
                />
            )}

            {session && (
                <ProgressTracker
                    session={session}
                    results={results}
                    cancelling={cancelling}
                    onCancel={handleCancel}
                />
            )}

            {showResults && results && <ResultsView results={results} />}

            {sessionId && (
                <div>
                    <Link className="btn btn-outline-primary" to="/research">
                        <i className="bi bi-plus-lg me-2" />
                        New Research
                    </Link>
                </div>
            )}

            <HistoryDrawer
                open={historyOpen}
                onClose={() => setHistoryOpen(false)}
                onOpenSession={id => navigate(`/research/${id}`)}
                onDuplicate={handleDuplicate}
            />

            <SettingsDrawer
                open={settingsOpen}
                providers={providers}
                onClose={() => setSettingsOpen(false)}
            />

        </div>
    );
}
