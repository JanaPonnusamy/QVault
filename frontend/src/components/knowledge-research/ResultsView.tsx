import { useState } from "react";

import { KnowledgeResults } from "../../types/knowledgeResearch";

import ConsensusPanel from "./ConsensusPanel";
import DocumentSummaries from "./DocumentSummaries";
import EntitiesTable from "./EntitiesTable";
import FactsTable from "./FactsTable";

const TABS = ["Report", "Consensus", "Documents", "Facts", "Entities"];

interface Props {
    results: KnowledgeResults;
}

export default function ResultsView({ results }: Props) {

    const [tab, setTab] = useState("Report");

    const report = results.report;

    return (
        <div className="space-y-4">

            <div className="flex gap-2 flex-wrap">
                {TABS.map(name => (
                    <button
                        key={name}
                        className={`px-3 py-1.5 rounded text-sm ${
                            tab === name
                                ? "bg-emerald-600 text-white"
                                : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                        }`}
                        onClick={() => setTab(name)}
                    >
                        {name}
                        {name === "Facts" && ` (${results.facts.length})`}
                        {name === "Entities" &&
                            ` (${results.entities.length})`}
                        {name === "Documents" &&
                            ` (${results.documents.length})`}
                    </button>
                ))}
            </div>

            <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/40">

                {tab === "Report" && (
                    <div className="space-y-6">
                        <div>
                            <h3 className="font-medium mb-2">
                                Executive Summary
                            </h3>
                            <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                                {report?.executive_summary ||
                                    "No summary available."}
                            </p>
                        </div>

                        {!!report?.recommendation?.steps?.length && (
                            <div>
                                <h3 className="font-medium mb-2">
                                    Recommendations
                                </h3>

                                {report.recommendation.summary && (
                                    <p className="text-sm text-zinc-300 mb-2">
                                        {report.recommendation.summary}
                                    </p>
                                )}

                                <ol className="list-decimal list-inside text-sm text-zinc-300 space-y-1">
                                    {report.recommendation.steps.map(
                                        (step, index) => (
                                            <li key={index}>{step}</li>
                                        )
                                    )}
                                </ol>
                            </div>
                        )}

                        {!!report?.timeline?.length && (
                            <div>
                                <h3 className="font-medium mb-2">Timeline</h3>

                                <ul className="text-sm text-zinc-300 space-y-1">
                                    {report.timeline.map((entry, index) => (
                                        <li key={index}>
                                            <span className="text-emerald-400">
                                                {entry.step}.
                                            </span>{" "}
                                            <span className="font-medium">
                                                {entry.label}
                                            </span>
                                            {entry.timing &&
                                                ` (${entry.timing})`}{" "}
                                            - {entry.detail}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {!!report?.conflicts?.length && (
                            <div>
                                <h3 className="font-medium mb-2">
                                    Conflicts
                                </h3>

                                <ul className="text-sm text-amber-400 space-y-1">
                                    {report.conflicts.map(
                                        (conflict, index) => (
                                            <li key={index}>
                                                {conflict.topic}:{" "}
                                                {conflict.conflict}
                                            </li>
                                        )
                                    )}
                                </ul>
                            </div>
                        )}
                    </div>
                )}

                {tab === "Consensus" && (
                    <ConsensusPanel consensus={results.consensus} />
                )}

                {tab === "Documents" && (
                    <DocumentSummaries documents={results.documents} />
                )}

                {tab === "Facts" && <FactsTable facts={results.facts} />}

                {tab === "Entities" && (
                    <EntitiesTable entities={results.entities} />
                )}

            </div>

        </div>
    );
}
