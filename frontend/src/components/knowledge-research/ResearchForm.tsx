import { useState } from "react";

import { KnowledgeProviders } from "../../types/knowledgeResearch";

interface Props {
    providers: KnowledgeProviders | null;
    submitting: boolean;
    onStart: (request: {
        mode: string;
        input_value: string;
        source_count: number;
        source_type: string;
        ai_provider: string;
        ai_model: string;
    }) => void;
}

export default function ResearchForm({ providers, submitting, onStart }: Props) {

    const [mode, setMode] = useState("TOPIC");
    const [inputValue, setInputValue] = useState("");
    const [sourceCount, setSourceCount] = useState(5);
    const [sourceType, setSourceType] = useState("youtube");
    const [aiProvider, setAiProvider] = useState("");
    const [aiModel, setAiModel] = useState("");

    function handleSubmit() {
        if (!inputValue.trim()) {
            return;
        }

        onStart({
            mode,
            input_value: inputValue.trim(),
            source_count: sourceCount,
            source_type: sourceType,
            ai_provider: aiProvider || providers?.default_provider || "",
            ai_model: aiModel || providers?.default_model || "",
        });
    }

    return (
        <div className="border border-zinc-800 rounded-lg p-4 space-y-4 bg-zinc-900/40">

            <div className="flex gap-2">
                <button
                    className={`px-3 py-1.5 rounded text-sm ${
                        mode === "TOPIC"
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                    }`}
                    onClick={() => setMode("TOPIC")}
                >
                    Topic Research
                </button>

                <button
                    className={`px-3 py-1.5 rounded text-sm ${
                        mode === "URL"
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                    }`}
                    onClick={() => setMode("URL")}
                >
                    Single URL
                </button>
            </div>

            <div>
                <label className="block text-sm text-zinc-400 mb-1">
                    {mode === "TOPIC" ? "Topic" : "Source URL"}
                </label>

                <input
                    className="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm"
                    placeholder={
                        mode === "TOPIC"
                            ? "e.g. Tomato Cultivation"
                            : "https://www.youtube.com/watch?v=..."
                    }
                    value={inputValue}
                    onChange={event => setInputValue(event.target.value)}
                />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

                {mode === "TOPIC" && (
                    <div>
                        <label className="block text-sm text-zinc-400 mb-1">
                            Sources
                        </label>

                        <select
                            className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-2 text-sm"
                            value={sourceCount}
                            onChange={event =>
                                setSourceCount(Number(event.target.value))
                            }
                        >
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                        </select>
                    </div>
                )}

                <div>
                    <label className="block text-sm text-zinc-400 mb-1">
                        Source Type
                    </label>

                    <select
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-2 text-sm"
                        value={sourceType}
                        onChange={event => setSourceType(event.target.value)}
                    >
                        {(providers?.source_types || ["youtube"]).map(type => (
                            <option key={type} value={type}>
                                {type}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-sm text-zinc-400 mb-1">
                        AI Provider
                    </label>

                    <select
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-2 text-sm"
                        value={aiProvider || providers?.default_provider || ""}
                        onChange={event => setAiProvider(event.target.value)}
                    >
                        {(providers?.llm_providers || []).map(provider => (
                            <option key={provider} value={provider}>
                                {provider}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-sm text-zinc-400 mb-1">
                        AI Model
                    </label>

                    <input
                        className="w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-2 text-sm"
                        placeholder={providers?.default_model || "model id"}
                        value={aiModel}
                        onChange={event => setAiModel(event.target.value)}
                    />
                </div>

            </div>

            <button
                className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-sm disabled:opacity-50"
                disabled={submitting || !inputValue.trim()}
                onClick={handleSubmit}
            >
                {submitting ? "Starting..." : "Start Research"}
            </button>

        </div>
    );
}
