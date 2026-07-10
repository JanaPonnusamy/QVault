import { KnowledgeConsensus } from "../../types/knowledgeResearch";

interface Props {
    consensus: KnowledgeConsensus | null;
}

export default function ConsensusPanel({ consensus }: Props) {

    if (!consensus) {
        return (
            <div className="text-sm text-zinc-500">
                No consensus available. Consensus is generated for topic
                research with two or more successful sources.
            </div>
        );
    }

    return (
        <div className="space-y-6">

            <div className="text-sm text-zinc-400">
                Overall confidence:{" "}
                <span className="text-emerald-400 font-medium">
                    {(consensus.confidence * 100).toFixed(0)}%
                </span>
            </div>

            {!!consensus.common_practices?.length && (
                <div>
                    <h3 className="font-medium mb-2">Common Practices</h3>

                    <ul className="space-y-2">
                        {consensus.common_practices.map((practice, index) => (
                            <li
                                key={index}
                                className="text-sm border border-zinc-800 rounded p-3 bg-zinc-900/40"
                            >
                                <div>{practice.practice}</div>
                                <div className="text-xs text-zinc-500 mt-1">
                                    {(practice.confidence * 100).toFixed(0)}% -{" "}
                                    {practice.supported_by?.join(", ")}
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {!!consensus.differences?.length && (
                <div>
                    <h3 className="font-medium mb-2">Differences</h3>

                    <ul className="space-y-2">
                        {consensus.differences.map((difference, index) => (
                            <li
                                key={index}
                                className="text-sm border border-zinc-800 rounded p-3 bg-zinc-900/40"
                            >
                                <div className="font-medium">
                                    {difference.aspect}
                                </div>

                                <ul className="mt-1 space-y-1">
                                    {difference.positions?.map(
                                        (position, positionIndex) => (
                                            <li
                                                key={positionIndex}
                                                className="text-zinc-400"
                                            >
                                                <span className="text-zinc-300">
                                                    {position.source}:
                                                </span>{" "}
                                                {position.position}
                                            </li>
                                        )
                                    )}
                                </ul>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {!!consensus.conflicting_advice?.length && (
                <div>
                    <h3 className="font-medium mb-2">Conflicting Advice</h3>

                    <ul className="space-y-2">
                        {consensus.conflicting_advice.map((conflict, index) => (
                            <li
                                key={index}
                                className="text-sm border border-amber-900/60 rounded p-3 bg-amber-950/20"
                            >
                                <div className="font-medium">
                                    {conflict.topic}
                                </div>
                                <div className="text-zinc-400 mt-1">
                                    {conflict.conflict}
                                </div>
                                <div className="text-xs text-zinc-500 mt-1">
                                    {conflict.sources?.join(", ")}
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {consensus.recommendation && (
                <div>
                    <h3 className="font-medium mb-2">Final Recommendation</h3>

                    <div className="text-sm border border-emerald-900/60 rounded p-3 bg-emerald-950/20 space-y-2">
                        <div>{consensus.recommendation.summary}</div>

                        {!!consensus.recommendation.steps?.length && (
                            <ol className="list-decimal list-inside space-y-1 text-zinc-300">
                                {consensus.recommendation.steps.map(
                                    (step, index) => (
                                        <li key={index}>{step}</li>
                                    )
                                )}
                            </ol>
                        )}

                        {consensus.recommendation.rationale && (
                            <div className="text-xs text-zinc-500">
                                {consensus.recommendation.rationale}
                            </div>
                        )}
                    </div>
                </div>
            )}

        </div>
    );
}
