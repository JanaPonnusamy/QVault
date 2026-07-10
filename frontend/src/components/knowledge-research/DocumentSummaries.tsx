import { KnowledgeDocument } from "../../types/knowledgeResearch";

interface Props {
    documents: KnowledgeDocument[];
}

export default function DocumentSummaries({ documents }: Props) {

    if (!documents.length) {
        return (
            <div className="text-sm text-zinc-500">No documents.</div>
        );
    }

    return (
        <div className="space-y-4">
            {documents.map((document, index) => (
                <div
                    key={document.id}
                    className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/40 space-y-2"
                >
                    <div className="flex items-center justify-between gap-3">
                        <div className="font-medium">
                            Source {index + 1}: {document.title}
                        </div>

                        <span
                            className={`px-2 py-0.5 rounded text-xs ${
                                document.status === "COMPLETED"
                                    ? "bg-emerald-900/60 text-emerald-300"
                                    : document.status === "FAILED"
                                        ? "bg-red-900/60 text-red-300"
                                        : "bg-zinc-800 text-zinc-400"
                            }`}
                        >
                            {document.status}
                        </span>
                    </div>

                    <a
                        className="text-xs text-sky-400 hover:underline break-all"
                        href={document.url}
                        target="_blank"
                        rel="noreferrer"
                    >
                        {document.url}
                    </a>

                    {document.status === "FAILED" &&
                        document.error_message && (
                            <div className="text-sm text-red-400">
                                {document.error_message}
                            </div>
                        )}

                    {document.analysis?.summary && (
                        <p className="text-sm text-zinc-300">
                            {document.analysis.summary}
                        </p>
                    )}

                    {!!document.analysis?.recommendations?.length && (
                        <div className="text-sm">
                            <span className="text-zinc-400">
                                Recommendations:
                            </span>

                            <ul className="list-disc list-inside text-zinc-300 mt-1">
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
                        <div className="text-sm text-amber-400">
                            Warnings: {document.analysis.warnings.join("; ")}
                        </div>
                    )}

                    <div className="text-xs text-zinc-500">
                        {document.word_count} words
                        {document.duration
                            ? ` - ${document.duration}s`
                            : ""}
                        {document.language
                            ? ` - ${document.language}`
                            : ""}
                    </div>
                </div>
            ))}
        </div>
    );
}
