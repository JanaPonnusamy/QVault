import { KnowledgeConsensus } from "../../types/knowledgeResearch";

interface Props {
    consensus: KnowledgeConsensus | null;
}

export default function ConsensusPanel({ consensus }: Props) {

    if (!consensus) {
        return (
            <div className="text-secondary">
                No consensus available. Consensus is generated for topic
                research with two or more successful sources.
            </div>
        );
    }

    return (
        <div className="d-flex flex-column gap-4">

            <div className="text-secondary">
                Overall confidence:{" "}
                <span className="fw-semibold text-success">
                    {(consensus.confidence * 100).toFixed(0)}%
                </span>
            </div>

            {!!consensus.common_practices?.length && (
                <div>
                    <h5 className="fw-semibold mb-2">Common Practices</h5>

                    <div className="d-flex flex-column gap-2">
                        {consensus.common_practices.map((practice, index) => (
                            <div key={index} className="qv-history-item">
                                <div>{practice.practice}</div>
                                <div className="small text-secondary mt-1">
                                    {(practice.confidence * 100).toFixed(0)}%
                                    confidence
                                    {practice.supported_by?.length
                                        ? ` — ${practice.supported_by.join(", ")}`
                                        : ""}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {!!consensus.differences?.length && (
                <div>
                    <h5 className="fw-semibold mb-2">Differences</h5>

                    <div className="d-flex flex-column gap-2">
                        {consensus.differences.map((difference, index) => (
                            <div key={index} className="qv-history-item">
                                <div className="fw-medium">
                                    {difference.aspect}
                                </div>

                                <ul className="mb-0 mt-1 small">
                                    {difference.positions?.map(
                                        (position, positionIndex) => (
                                            <li key={positionIndex}>
                                                <span className="fw-medium">
                                                    {position.source}:
                                                </span>{" "}
                                                <span className="text-secondary">
                                                    {position.position}
                                                </span>
                                            </li>
                                        )
                                    )}
                                </ul>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {!!consensus.conflicting_advice?.length && (
                <div>
                    <h5 className="fw-semibold mb-2">Conflicting Advice</h5>

                    <div className="d-flex flex-column gap-2">
                        {consensus.conflicting_advice.map(
                            (conflict, index) => (
                                <div
                                    key={index}
                                    className="alert alert-warning mb-0"
                                >
                                    <div className="fw-medium">
                                        {conflict.topic}
                                    </div>
                                    <div className="mt-1">
                                        {conflict.conflict}
                                    </div>
                                    {!!conflict.sources?.length && (
                                        <div className="small text-secondary mt-1">
                                            {conflict.sources.join(", ")}
                                        </div>
                                    )}
                                </div>
                            )
                        )}
                    </div>
                </div>
            )}

            {consensus.recommendation && (
                <div>
                    <h5 className="fw-semibold mb-2">Final Recommendation</h5>

                    <div className="alert alert-success mb-0">
                        <div>{consensus.recommendation.summary}</div>

                        {!!consensus.recommendation.steps?.length && (
                            <ol className="mb-0 mt-2">
                                {consensus.recommendation.steps.map(
                                    (step, index) => (
                                        <li key={index} className="mb-1">
                                            {step}
                                        </li>
                                    )
                                )}
                            </ol>
                        )}

                        {consensus.recommendation.rationale && (
                            <div className="small text-secondary mt-2">
                                {consensus.recommendation.rationale}
                            </div>
                        )}
                    </div>
                </div>
            )}

        </div>
    );
}
