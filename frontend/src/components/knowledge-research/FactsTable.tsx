import { KnowledgeFact } from "../../types/knowledgeResearch";

interface Props {
    facts: KnowledgeFact[];
}

export default function FactsTable({ facts }: Props) {

    if (!facts.length) {
        return (
            <div className="text-sm text-zinc-500">
                No facts extracted.
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-left text-zinc-400 border-b border-zinc-800">
                        <th className="py-2 pr-3">Category</th>
                        <th className="py-2 pr-3">Subcategory</th>
                        <th className="py-2 pr-3">Value</th>
                        <th className="py-2 pr-3">Confidence</th>
                        <th className="py-2 pr-3">Evidence</th>
                        <th className="py-2">Source</th>
                    </tr>
                </thead>

                <tbody>
                    {facts.map(fact => (
                        <tr
                            key={fact.id}
                            className="border-b border-zinc-800/60 align-top"
                        >
                            <td className="py-2 pr-3 whitespace-nowrap">
                                {fact.category}
                            </td>
                            <td className="py-2 pr-3">{fact.subcategory}</td>
                            <td className="py-2 pr-3">{fact.value}</td>
                            <td className="py-2 pr-3">
                                <span
                                    className={
                                        fact.confidence >= 0.8
                                            ? "text-emerald-400"
                                            : fact.confidence >= 0.5
                                                ? "text-amber-400"
                                                : "text-zinc-400"
                                    }
                                >
                                    {(fact.confidence * 100).toFixed(0)}%
                                </span>
                            </td>
                            <td className="py-2 pr-3 text-zinc-400 max-w-md">
                                {fact.evidence}
                            </td>
                            <td className="py-2 text-zinc-400 whitespace-nowrap">
                                {fact.source_document}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
