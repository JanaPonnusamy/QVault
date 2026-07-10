import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import ResearchForm from "../components/knowledge-research/ResearchForm";
import ProgressTracker from "../components/knowledge-research/ProgressTracker";
import ResultsView from "../components/knowledge-research/ResultsView";

import {
    createSession,
    getProviders,
    getResults,
    getSession,
} from "../services/knowledgeResearchApi";

import {
    KnowledgeProviders,
    KnowledgeResults,
    KnowledgeSession,
    SessionCreateRequest,
} from "../types/knowledgeResearch";

const POLL_INTERVAL_MS = 3000;

export default function KnowledgeResearchPage() {

    const { sessionId } = useParams();
    const navigate = useNavigate();

    const [providers, setProviders] =
        useState<KnowledgeProviders | null>(null);

    const [session, setSession] =
        useState<KnowledgeSession | null>(null);

    const [results, setResults] =
        useState<KnowledgeResults | null>(null);

    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

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
                const current = await getSession(id);
                setSession(current);

                if (current.status === "COMPLETED") {
                    stopPolling();
                    setResults(await getResults(id));
                }

                if (current.status === "FAILED") {
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

    return (
        <div className="p-6 space-y-6">

            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">
                        Knowledge Research
                    </h1>

                    <p className="text-zinc-500 mt-2">
                        AI-powered research from multiple sources
                    </p>
                </div>

                <Link
                    className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-sm"
                    to="/research/history"
                >
                    History
                </Link>
            </div>

            {error && (
                <div className="text-sm text-red-400 border border-red-900 rounded p-3 bg-red-950/30">
                    {error}
                </div>
            )}

            {!sessionId && (
                <ResearchForm
                    providers={providers}
                    submitting={submitting}
                    onStart={handleStart}
                />
            )}

            {session && <ProgressTracker session={session} />}

            {results && <ResultsView results={results} />}

            {sessionId && (
                <Link
                    className="inline-block text-sm text-sky-400 hover:underline"
                    to="/research"
                >
                    Start a new research session
                </Link>
            )}

        </div>
    );
}
