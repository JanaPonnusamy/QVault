import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listSessions } from "../services/knowledgeResearchApi";

import {
    HistoryFilters,
    KnowledgeSession,
} from "../types/knowledgeResearch";

const STATUSES = ["", "RUNNING", "COMPLETED", "FAILED", "QUEUED"];

const EMPTY_FILTERS: HistoryFilters = {
    status: "",
    topic: "",
    date_from: "",
    date_to: "",
    provider: "",
    source_type: "",
};

export default function KnowledgeResearchHistoryPage() {

    const [filters, setFilters] = useState<HistoryFilters>(EMPTY_FILTERS);
    const [sessions, setSessions] = useState<KnowledgeSession[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

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

    return (
        <div className="p-6 space-y-6">

            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">Research History</h1>

                    <p className="text-zinc-500 mt-2">
                        Past knowledge research sessions
                    </p>
                </div>

                <Link
                    className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm"
                    to="/research"
                >
                    New Research
                </Link>
            </div>

            <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/40 grid grid-cols-2 md:grid-cols-6 gap-3">

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        Status
                    </label>

                    <select
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
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

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        Topic
                    </label>

                    <input
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
                        placeholder="contains..."
                        value={filters.topic}
                        onChange={event =>
                            update("topic", event.target.value)
                        }
                    />
                </div>

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        From
                    </label>

                    <input
                        type="date"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
                        value={filters.date_from}
                        onChange={event =>
                            update("date_from", event.target.value)
                        }
                    />
                </div>

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        To
                    </label>

                    <input
                        type="date"
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
                        value={filters.date_to}
                        onChange={event =>
                            update("date_to", event.target.value)
                        }
                    />
                </div>

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        Provider
                    </label>

                    <input
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
                        placeholder="e.g. openai"
                        value={filters.provider}
                        onChange={event =>
                            update("provider", event.target.value)
                        }
                    />
                </div>

                <div>
                    <label className="block text-xs text-zinc-400 mb-1">
                        Source Type
                    </label>

                    <input
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm"
                        placeholder="e.g. youtube"
                        value={filters.source_type}
                        onChange={event =>
                            update("source_type", event.target.value)
                        }
                    />
                </div>

                <div className="col-span-2 md:col-span-6 flex gap-2">
                    <button
                        className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm"
                        onClick={() => load(filters)}
                    >
                        Apply Filters
                    </button>

                    <button
                        className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-sm"
                        onClick={() => {
                            setFilters(EMPTY_FILTERS);
                            load(EMPTY_FILTERS);
                        }}
                    >
                        Reset
                    </button>
                </div>

            </div>

            {error && (
                <div className="text-sm text-red-400 border border-red-900 rounded p-3 bg-red-950/30">
                    {error}
                </div>
            )}

            <div className="border border-zinc-800 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-left text-zinc-400 bg-zinc-900/60 border-b border-zinc-800">
                            <th className="p-3">#</th>
                            <th className="p-3">Mode</th>
                            <th className="p-3">Input</th>
                            <th className="p-3">Sources</th>
                            <th className="p-3">Provider / Model</th>
                            <th className="p-3">Status</th>
                            <th className="p-3">Created</th>
                        </tr>
                    </thead>

                    <tbody>
                        {loading && (
                            <tr>
                                <td
                                    className="p-3 text-zinc-500"
                                    colSpan={7}
                                >
                                    Loading...
                                </td>
                            </tr>
                        )}

                        {!loading && !sessions.length && (
                            <tr>
                                <td
                                    className="p-3 text-zinc-500"
                                    colSpan={7}
                                >
                                    No sessions found.
                                </td>
                            </tr>
                        )}

                        {!loading &&
                            sessions.map(session => (
                                <tr
                                    key={session.id}
                                    className="border-b border-zinc-800/60 hover:bg-zinc-900/40"
                                >
                                    <td className="p-3">
                                        <Link
                                            className="text-sky-400 hover:underline"
                                            to={`/research/${session.id}`}
                                        >
                                            {session.id}
                                        </Link>
                                    </td>
                                    <td className="p-3">{session.mode}</td>
                                    <td className="p-3 max-w-sm truncate">
                                        {session.input_value}
                                    </td>
                                    <td className="p-3">
                                        {session.source_count_requested}
                                    </td>
                                    <td className="p-3">
                                        {session.ai_provider} /{" "}
                                        {session.ai_model}
                                    </td>
                                    <td className="p-3">
                                        <span
                                            className={`px-2 py-0.5 rounded text-xs ${
                                                session.status === "COMPLETED"
                                                    ? "bg-emerald-900/60 text-emerald-300"
                                                    : session.status === "FAILED"
                                                        ? "bg-red-900/60 text-red-300"
                                                        : "bg-amber-900/60 text-amber-300"
                                            }`}
                                        >
                                            {session.status}
                                            {session.status === "RUNNING" &&
                                                ` ${session.progress}%`}
                                        </span>
                                    </td>
                                    <td className="p-3 text-zinc-400 whitespace-nowrap">
                                        {session.created_at}
                                    </td>
                                </tr>
                            ))}
                    </tbody>
                </table>
            </div>

        </div>
    );
}
