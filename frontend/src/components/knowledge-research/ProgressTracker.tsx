import { KnowledgeSession } from "../../types/knowledgeResearch";

const STAGES = [
    "QUEUED",
    "SEARCHING",
    "DOWNLOADING",
    "EXTRACTING",
    "TRANSCRIBING",
    "OCR",
    "ANALYZING",
    "COMPARING",
    "GENERATING",
    "COMPLETED",
];

interface Props {
    session: KnowledgeSession;
}

export default function ProgressTracker({ session }: Props) {

    const failed = session.status === "FAILED";
    const currentIndex = STAGES.indexOf(session.current_stage);

    return (
        <div className="border border-zinc-800 rounded-lg p-4 space-y-4 bg-zinc-900/40">

            <div className="flex items-center justify-between">
                <div className="text-sm text-zinc-400">
                    Session #{session.id} - {session.mode} -{" "}
                    {session.input_value.length > 60
                        ? session.input_value.slice(0, 60) + "..."
                        : session.input_value}
                </div>

                <div
                    className={`text-sm font-medium ${
                        failed
                            ? "text-red-400"
                            : session.status === "COMPLETED"
                                ? "text-emerald-400"
                                : "text-amber-400"
                    }`}
                >
                    {failed ? "FAILED" : session.current_stage}
                </div>
            </div>

            <div className="w-full bg-zinc-800 rounded h-2 overflow-hidden">
                <div
                    className={`h-2 transition-all ${
                        failed ? "bg-red-500" : "bg-emerald-500"
                    }`}
                    style={{ width: `${session.progress}%` }}
                />
            </div>

            <div className="flex flex-wrap gap-2">
                {STAGES.map((stage, index) => {
                    const reached =
                        currentIndex >= 0 && index <= currentIndex;

                    return (
                        <span
                            key={stage}
                            className={`px-2 py-0.5 rounded text-xs ${
                                reached && !failed
                                    ? "bg-emerald-900/60 text-emerald-300"
                                    : "bg-zinc-800 text-zinc-500"
                            }`}
                        >
                            {stage}
                        </span>
                    );
                })}
            </div>

            {failed && session.error_message && (
                <div className="text-sm text-red-400 border border-red-900 rounded p-3 bg-red-950/30">
                    {session.error_message}
                </div>
            )}

        </div>
    );
}
