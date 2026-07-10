import { KnowledgeEntity } from "../../types/knowledgeResearch";

interface Props {
    entities: KnowledgeEntity[];
}

export default function EntitiesTable({ entities }: Props) {

    if (!entities.length) {
        return (
            <div className="text-secondary">No entities extracted.</div>
        );
    }

    return (
        <div className="table-responsive">
            <table className="table table-sm table-hover align-top mb-0">
                <thead>
                    <tr className="text-secondary small">
                        <th>Entity</th>
                        <th>Type</th>
                        <th>Category</th>
                        <th>Confidence</th>
                        <th>Evidence</th>
                    </tr>
                </thead>

                <tbody>
                    {entities.map(entity => (
                        <tr key={entity.id}>
                            <td className="fw-medium text-nowrap">
                                {entity.entity_name}
                            </td>
                            <td>
                                <span className="badge text-bg-light border text-secondary">
                                    {entity.entity_type}
                                </span>
                            </td>
                            <td>{entity.category}</td>
                            <td>{(entity.confidence * 100).toFixed(0)}%</td>
                            <td
                                className="text-secondary small"
                                style={{ maxWidth: 360 }}
                            >
                                {entity.evidence}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
