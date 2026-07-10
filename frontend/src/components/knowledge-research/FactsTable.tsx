import { KnowledgeFact } from "../../types/knowledgeResearch";

interface Props {
    facts: KnowledgeFact[];
}

function confidenceClass(confidence: number) {
    if (confidence >= 0.8) {
        return "text-success";
    }

    if (confidence >= 0.5) {
        return "text-warning-emphasis";
    }

    return "text-secondary";
}

export default function FactsTable({ facts }: Props) {

    if (!facts.length) {
        return (
            <div className="text-secondary">No facts extracted.</div>
        );
    }

    return (
        <div className="table-responsive">
            <table className="table table-sm table-hover align-top mb-0">
                <thead>
                    <tr className="text-secondary small">
                        <th>Category</th>
                        <th>Subcategory</th>
                        <th>Value</th>
                        <th>Confidence</th>
                        <th>Evidence</th>
                        <th>Source</th>
                    </tr>
                </thead>

                <tbody>
                    {facts.map(fact => (
                        <tr key={fact.id}>
                            <td className="text-nowrap">{fact.category}</td>
                            <td>{fact.subcategory}</td>
                            <td>{fact.value}</td>
                            <td>
                                <span
                                    className={`fw-medium ${confidenceClass(
                                        fact.confidence
                                    )}`}
                                >
                                    {(fact.confidence * 100).toFixed(0)}%
                                </span>
                            </td>
                            <td
                                className="text-secondary small"
                                style={{ maxWidth: 320 }}
                            >
                                {fact.evidence}
                            </td>
                            <td className="text-secondary small text-nowrap">
                                {fact.source_document}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
