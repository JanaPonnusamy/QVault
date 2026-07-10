import { useEffect, useMemo, useRef, useState } from "react";

import {
    KnowledgeResults,
    KnowledgeSession,
} from "../../types/knowledgeResearch";

import { formatDuration, parseUtc } from "./format";

const STAGES = [
    "QUEUED",
    "SEARCHING",
    "DOWNLOADING",
    "EXTRACTING",
    "TRANSCRIBING",
    "OCR",
    "ANALYZING",
    "COMPARING",
    "GENERATING",
    "COMPLETED",
];

const STAGE_LABELS: Record<string, string> = {
    QUEUED: "Queued",
    SEARCHING: "Searching sources",
    DOWNLOADING: "Downloading media",
    EXTRACTING: "Extracting content",
    TRANSCRIBING: "Transcribing audio",
    OCR: "Reading on-screen text",
    ANALYZING: "AI analysis",
    COMPARING: "Building consensus",
    GENERATING: "Generating report",
    COMPLETED: "Completed",
    CANCELLED: "Cancelled",
    FAILED: "Failed",
};

interface LogEntry {
    time: string;
    text: string;
    tone: "" | "text-warning" | "text-danger" | "text-success";
}

interface Props {
    session: KnowledgeSession;
    results: KnowledgeResults | null;
    cancelling: boolean;
    onCancel: () => void;
}

export default function ProgressTracker({
    session,
    results,
    cancelling,
    onCancel,
}: Props) {

    const running =
        session.status === "RUNNING" || session.status === "QUEUED";
    const failed = session.status === "FAILED";
    const cancelled = session.status === "CANCELLED";
    const completed = session.status === "COMPLETED";

    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        if (!running) {
            return;
        }

        const timer = window.setInterval(() => setNow(Date.now()), 1000);
        return () => window.clearInterval(timer);
    }, [running]);

    const documents = useMemo(
        () => results?.documents ?? [],
        [results]
    );
    const aiRuns = useMemo(() => results?.ai_runs ?? [], [results]);

    const currentDocument =
        documents.find(document => document.status === "PROCESSING") ||
        (running ? documents[documents.length - 1] : undefined);

    const finishedDocuments = documents.filter(
        document =>
            document.status === "COMPLETED" || document.status === "FAILED"
    ).length;

    const totalTokens = aiRuns.reduce(
        (sum, run) => sum + run.input_tokens + run.output_tokens,
        0
    );
    const totalCost = aiRuns.reduce(
        (sum, run) => sum + (run.estimated_cost || 0),
        0
    );

    const startedMs = parseUtc(session.created_at).getTime();
    const endMs = running ? now : parseUtc(session.updated_at).getTime();
    const elapsedSeconds = (endMs - startedMs) / 1000;

    const etaSeconds =
        running && session.progress >= 5
            ? (elapsedSeconds / session.progress) * (100 - session.progress)
            : null;

    const logEntries = useMemo<LogEntry[]>(() => {
        const entries: LogEntry[] = [
            {
                time: session.created_at,
                text: `Session #${session.id} created — ${session.mode} · ${session.input_value}`,
                tone: "",
            },
        ];

        for (const document of documents) {
            const tone =
                document.status === "FAILED"
                    ? "text-danger"
                    : document.status === "COMPLETED"
                        ? "text-success"
                        : "";

            entries.push({
                time: document.updated_at || "",
                text: `[${document.status}] ${document.title || document.url}${
                    document.status === "FAILED" && document.error_message
                        ? ` — ${document.error_message}`
                        : ""
                }`,
                tone,
            });
        }

        for (const run of aiRuns) {
            entries.push({
                time: run.created_at,
                text: `LLM ${run.stage} · ${run.model} · ${run.input_tokens}+${run.output_tokens} tokens · ${run.latency_ms} ms · ${run.status}`,
                tone: run.status === "FAILED" ? "text-danger" : "",
            });
        }

        entries.sort((a, b) => (a.time < b.time ? -1 : 1));

        return entries;
    }, [session, documents, aiRuns]);

    const logRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (logRef.current) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
        }
    }, [logEntries.length]);

    const currentIndex = STAGES.indexOf(session.current_stage);
    const stageLabel =
        STAGE_LABELS[session.current_stage] || session.current_stage;

    return (
        <div className="card">
            <div className="card-header d-flex align-items-center gap-3 flex-wrap">
                {running && (
                    <span
                        className="spinner-border spinner-border-sm text-primary"
                        role="status"
                    />
                )}
                <span className="fw-semibold">
                    {running
                        ? "Researching…"
                        : STAGE_LABELS[session.status] || session.status}
                </span>
                <span className="text-secondary small text-truncate flex-grow-1">
                    #{session.id} · {session.mode} · {session.input_value}
                </span>

                {running && (
                    <button
                        className="btn btn-outline-danger btn-sm"
                        disabled={cancelling}
                        onClick={onCancel}
                    >
                        {cancelling ? (
                            <span className="spinner-border spinner-border-sm me-1" />
                        ) : (
                            <i className="bi bi-x-circle me-1" />
                        )}
                        Cancel
                    </button>
                )}
            </div>

            <div className="card-body d-flex flex-column gap-4">

                <div>
                    <div className="d-flex justify-content-between small mb-1">
                        <span className="fw-medium">{stageLabel}</span>
                        <span className="text-secondary">
                            {session.progress}%
                        </span>
                    </div>
                    <div
                        className="progress"
                        role="progressbar"
                        aria-valuenow={session.progress}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        style={{ height: 10 }}
                    >
                        <div
                            className={`progress-bar ${
                                failed
                                    ? "bg-danger"
                                    : cancelled
                                        ? "bg-secondary"
                                        : completed
                                            ? "bg-success"
                                            : "progress-bar-striped progress-bar-animated"
                            }`}
                            style={{ width: `${session.progress}%` }}
                        />
                    </div>
                </div>

                <div className="row g-2 row-cols-2 row-cols-md-3 row-cols-xl-6">
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">Sources</div>
                            <div className="qv-stat-value">
                                {finishedDocuments}/
                                {session.source_count_requested}
                            </div>
                        </div>
                    </div>
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">Current source</div>
                            <div
                                className="qv-stat-value"
                                title={currentDocument?.title || "—"}
                            >
                                {currentDocument?.title || "—"}
                            </div>
                        </div>
                    </div>
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">AI task</div>
                            <div className="qv-stat-value">{stageLabel}</div>
                        </div>
                    </div>
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">Tokens</div>
                            <div className="qv-stat-value">
                                {totalTokens.toLocaleString()}
                            </div>
                        </div>
                    </div>
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">Elapsed</div>
                            <div className="qv-stat-value">
                                {formatDuration(elapsedSeconds)}
                            </div>
                        </div>
                    </div>
                    <div className="col">
                        <div className="qv-stat">
                            <div className="qv-stat-label">
                                {running ? "Est. remaining" : "Est. cost"}
                            </div>
                            <div className="qv-stat-value">
                                {running
                                    ? etaSeconds !== null
                                        ? `~${formatDuration(etaSeconds)}`
                                        : "—"
                                    : `$${totalCost.toFixed(4)}`}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="d-flex flex-wrap gap-1">
                    {STAGES.map((stage, index) => {
                        const reached =
                            currentIndex >= 0 && index <= currentIndex;

                        return (
                            <span
                                key={stage}
                                className={`badge rounded-pill ${
                                    reached && !failed && !cancelled
                                        ? "text-bg-primary"
                                        : "text-bg-light border text-secondary"
                                }`}
                            >
                                {STAGE_LABELS[stage] || stage}
                            </span>
                        );
                    })}
                </div>

                {failed && session.error_message && (
                    <div className="alert alert-danger mb-0" role="alert">
                        <i className="bi bi-x-octagon me-2" />
                        {session.error_message}
                    </div>
                )}

                {cancelled && (
                    <div className="alert alert-secondary mb-0" role="alert">
                        <i className="bi bi-slash-circle me-2" />
                        This research session was cancelled.
                    </div>
                )}

                {logEntries.length > 0 && (
                    <div>
                        <div className="fw-medium small mb-2">
                            <i className="bi bi-terminal me-2" />
                            Live Logs
                        </div>
                        <div className="qv-log" ref={logRef}>
                            {logEntries.map((entry, index) => (
                                <div key={index} className={entry.tone}>
                                    {entry.time && (
                                        <span className="qv-log-time">
                                            {entry.time}
                                        </span>
                                    )}
                                    {entry.text}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}
