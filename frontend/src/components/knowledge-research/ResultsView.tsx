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

    function tabLabel(name: string) {
        switch (name) {
            case "Facts":
                return `Facts (${results.facts.length})`;
            case "Entities":
                return `Entities (${results.entities.length})`;
            case "Documents":
                return `Documents (${results.documents.length})`;
            default:
                return name;
        }
    }

    return (
        <div className="card">

            <div className="card-header pb-0">
                <ul className="nav nav-tabs card-header-tabs flex-nowrap overflow-auto">
                    {TABS.map(name => (
                        <li className="nav-item" key={name}>
                            <button
                                className={`nav-link text-nowrap ${
                                    tab === name ? "active" : ""
                                }`}
                                onClick={() => setTab(name)}
                            >
                                {tabLabel(name)}
                            </button>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="card-body">

                {tab === "Report" && (
                    <div className="d-flex flex-column gap-4">
                        <div>
                            <h5 className="fw-semibold mb-2">
                                Executive Summary
                            </h5>
                            <p
                                className="mb-0"
                                style={{ whiteSpace: "pre-wrap" }}
                            >
                                {report?.executive_summary ||
                                    "No summary available."}
                            </p>
                        </div>

                        {!!report?.recommendation?.steps?.length && (
                            <div>
                                <h5 className="fw-semibold mb-2">
                                    Recommendations
                                </h5>

                                {report.recommendation.summary && (
                                    <p className="mb-2">
                                        {report.recommendation.summary}
                                    </p>
                                )}

                                <ol className="mb-0">
                                    {report.recommendation.steps.map(
                                        (step, index) => (
                                            <li key={index} className="mb-1">
                                                {step}
                                            </li>
                                        )
                                    )}
                                </ol>
                            </div>
                        )}

                        {!!report?.timeline?.length && (
                            <div>
                                <h5 className="fw-semibold mb-2">Timeline</h5>

                                <ul className="list-unstyled mb-0">
                                    {report.timeline.map((entry, index) => (
                                        <li key={index} className="mb-1">
                                            <span className="badge text-bg-primary me-2">
                                                {entry.step}
                                            </span>
                                            <span className="fw-medium">
                                                {entry.label}
                                            </span>
                                            {entry.timing && (
                                                <span className="text-secondary">
                                                    {" "}
                                                    ({entry.timing})
                                                </span>
                                            )}{" "}
                                            — {entry.detail}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {!!report?.conflicts?.length && (
                            <div>
                                <h5 className="fw-semibold mb-2">Conflicts</h5>

                                <ul className="mb-0">
                                    {report.conflicts.map(
                                        (conflict, index) => (
                                            <li
                                                key={index}
                                                className="text-warning-emphasis mb-1"
                                            >
                                                <strong>
                                                    {conflict.topic}:
                                                </strong>{" "}
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
