import { KnowledgeEntity } from "../../types/knowledgeResearch";

interface Props {
    entities: KnowledgeEntity[];
}

export default function EntitiesTable({ entities }: Props) {

    if (!entities.length) {
        return (
            <div className="text-sm text-zinc-500">
                No entities extracted.
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-left text-zinc-400 border-b border-zinc-800">
                        <th className="py-2 pr-3">Entity</th>
                        <th className="py-2 pr-3">Type</th>
                        <th className="py-2 pr-3">Category</th>
                        <th className="py-2 pr-3">Confidence</th>
                        <th className="py-2">Evidence</th>
                    </tr>
                </thead>

                <tbody>
                    {entities.map(entity => (
                        <tr
                            key={entity.id}
                            className="border-b border-zinc-800/60 align-top"
                        >
                            <td className="py-2 pr-3 font-medium whitespace-nowrap">
                                {entity.entity_name}
                            </td>
                            <td className="py-2 pr-3">
                                <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-xs">
                                    {entity.entity_type}
                                </span>
                            </td>
                            <td className="py-2 pr-3">{entity.category}</td>
                            <td className="py-2 pr-3">
                                {(entity.confidence * 100).toFixed(0)}%
                            </td>
                            <td className="py-2 text-zinc-400 max-w-md">
                                {entity.evidence}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
