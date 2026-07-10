import { KnowledgeDocument } from "../../types/knowledgeResearch";

import { statusBadgeClass } from "./format";

interface Props {
    documents: KnowledgeDocument[];
}

export default function DocumentSummaries({ documents }: Props) {

    if (!documents.length) {
        return <div className="text-secondary">No documents.</div>;
    }

    return (
        <div className="d-flex flex-column gap-3">
            {documents.map((document, index) => (
                <div key={document.id} className="qv-history-item">
                    <div className="d-flex align-items-center justify-content-between gap-3">
                        <div className="fw-medium">
                            Source {index + 1}: {document.title}
                        </div>

                        <span
                            className={`badge ${statusBadgeClass(
                                document.status
                            )}`}
                        >
                            {document.status}
                        </span>
                    </div>

                    <a
                        className="small d-inline-block text-break mt-1"
                        href={document.url}
                        target="_blank"
                        rel="noreferrer"
                    >
                        {document.url}
                    </a>

                    {document.status === "FAILED" &&
                        document.error_message && (
                            <div className="alert alert-danger py-2 small mt-2 mb-0">
                                {document.error_message}
                            </div>
                        )}

                    {document.analysis?.summary && (
                        <p className="mt-2 mb-0">
                            {document.analysis.summary}
                        </p>
                    )}

                    {!!document.analysis?.recommendations?.length && (
                        <div className="mt-2">
                            <span className="fw-medium small">
                                Recommendations:
                            </span>

                            <ul className="mb-0 small">
                                {document.analysis.recommendations.map(
                                    (recommendation, recommendationIndex) => (
                                        <li key={recommendationIndex}>
                                            {recommendation}
                                        </li>
                                    )
                                )}
                            </ul>
                        </div>
                    )}

                    {!!document.analysis?.warnings?.length && (
                        <div className="small text-warning-emphasis mt-2">
                            <i className="bi bi-exclamation-triangle me-1" />
                            {document.analysis.warnings.join("; ")}
                        </div>
                    )}

                    <div className="small text-secondary mt-2">
                        {document.word_count.toLocaleString()} words
                        {document.duration ? ` · ${document.duration}s` : ""}
                        {document.language ? ` · ${document.language}` : ""}
                    </div>
                </div>
            ))}
        </div>
    );
}
