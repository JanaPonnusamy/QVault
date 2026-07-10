import { useEffect, useMemo, useRef, useState } from "react";

import { getProviderModels } from "../../services/knowledgeResearchApi";

import {
    KnowledgeProviders,
    SessionCreateRequest,
} from "../../types/knowledgeResearch";

const SOURCE_TYPE_LABELS: Record<string, string> = {
    all: "All Sources",
    youtube: "YouTube",
    instagram: "Instagram",
    pdf: "PDF",
    ncert: "NCERT",
    images: "Images",
};

const SOURCE_MARKS = [1, 3, 5, 10];

function sourceTypeLabel(type: string) {
    return (
        SOURCE_TYPE_LABELS[type] ||
        type.charAt(0).toUpperCase() + type.slice(1)
    );
}

interface ModelsState {
    loading: boolean;
    list: string[];
    error: string;
}

interface Props {
    providers: KnowledgeProviders | null;
    submitting: boolean;
    prefill?: Partial<SessionCreateRequest>;
    onStart: (request: SessionCreateRequest) => void;
    onOpenSettings: () => void;
}

export default function ResearchForm({
    providers,
    submitting,
    prefill,
    onStart,
    onOpenSettings,
}: Props) {

    const [mode, setMode] = useState(prefill?.mode || "TOPIC");
    const [inputValue, setInputValue] = useState(prefill?.input_value || "");
    const [sourceCount, setSourceCount] = useState(prefill?.source_count || 5);
    const [sourceType, setSourceType] = useState(prefill?.source_type || "");
    const [aiProvider, setAiProvider] = useState(prefill?.ai_provider || "");
    const [aiModel, setAiModel] = useState(prefill?.ai_model || "");
    const [temperature, setTemperature] = useState(
        prefill?.temperature ?? 0.2
    );
    const [maxTokens, setMaxTokens] = useState(prefill?.max_tokens ?? 4000);
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const [modelFilter, setModelFilter] = useState("");

    const [models, setModels] = useState<ModelsState>({
        loading: false,
        list: [],
        error: "",
    });

    const modelsCache = useRef<Record<string, string[]>>({});

    /* Apply backend defaults once the provider catalog arrives. */
    useEffect(() => {
        if (!providers) {
            return;
        }

        setAiProvider(current => current || providers.default_provider);
        setSourceType(current => current || providers.source_types[0] || "");
        setTemperature(current =>
            prefill?.temperature !== undefined
                ? current
                : providers.default_temperature ?? current
        );
        setMaxTokens(current =>
            prefill?.max_tokens !== undefined
                ? current
                : providers.default_max_tokens ?? current
        );
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [providers]);

    const providerInfo = useMemo(
        () => providers?.providers.find(p => p.name === aiProvider) || null,
        [providers, aiProvider]
    );

    /* Load the model catalog whenever the provider changes. */
    useEffect(() => {
        if (!aiProvider || !providerInfo?.configured) {
            setModels({ loading: false, list: [], error: "" });
            return;
        }

        const cached = modelsCache.current[aiProvider];

        if (cached) {
            setModels({ loading: false, list: cached, error: "" });
            return;
        }

        let stale = false;

        setModels({ loading: true, list: [], error: "" });

        getProviderModels(aiProvider)
            .then(list => {
                modelsCache.current[aiProvider] = list;

                if (!stale) {
                    setModels({ loading: false, list, error: "" });
                }
            })
            .catch(loadError => {
                if (!stale) {
                    setModels({
                        loading: false,
                        list: [],
                        error:
                            loadError?.response?.data?.detail ||
                            "Could not load models from the provider.",
                    });
                }
            });

        return () => {
            stale = true;
        };
    }, [aiProvider, providerInfo?.configured]);

    /* Pick a sensible model when the provider or its catalog changes. */
    useEffect(() => {
        if (!providerInfo) {
            return;
        }

        setAiModel(current => {
            if (current && (models.list.length === 0 || models.list.includes(current))) {
                return current;
            }

            if (
                providerInfo.default_model &&
                (models.list.length === 0 ||
                    models.list.includes(providerInfo.default_model))
            ) {
                return providerInfo.default_model;
            }

            return models.list[0] || current;
        });
    }, [providerInfo, models.list]);

    const filteredModels = useMemo(() => {
        const query = modelFilter.trim().toLowerCase();

        if (!query) {
            return models.list;
        }

        return models.list.filter(id => id.toLowerCase().includes(query));
    }, [models.list, modelFilter]);

    const inputReady = Boolean(inputValue.trim());
    const providerReady = Boolean(providerInfo?.configured);
    const modelReady = Boolean(aiModel.trim());
    const canStart =
        !submitting && inputReady && providerReady && modelReady;

    function handleProviderChange(name: string) {
        setAiProvider(name);
        setAiModel("");
        setModelFilter("");
    }

    function handleSubmit() {
        if (!canStart) {
            return;
        }

        onStart({
            mode,
            input_value: inputValue.trim(),
            source_count: sourceCount,
            source_type: sourceType,
            ai_provider: aiProvider,
            ai_model: aiModel.trim(),
            temperature,
            max_tokens: maxTokens,
        });
    }

    if (!providers) {
        return (
            <div className="card">
                <div className="card-body d-flex align-items-center gap-3 py-4">
                    <div
                        className="spinner-border spinner-border-sm text-primary"
                        role="status"
                    />
                    <span className="text-secondary">
                        Loading research configuration…
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className="d-flex flex-column gap-4">

            {/* Card 1 — Research Type */}
            <div className="card">
                <div className="card-header d-flex align-items-center gap-2">
                    <span className="qv-step-badge">1</span>
                    <span className="fw-semibold">Research Type</span>
                </div>

                <div className="card-body">
                    <div className="row g-3">
                        {[
                            {
                                value: "TOPIC",
                                icon: "bi-lightbulb",
                                title: "Topic Research",
                                text: "Search multiple sources for a topic and build a consensus report.",
                            },
                            {
                                value: "URL",
                                icon: "bi-link-45deg",
                                title: "Single URL",
                                text: "Analyze one specific source in depth.",
                            },
                        ].map(option => (
                            <div className="col-12 col-md-6" key={option.value}>
                                <label
                                    className={`qv-choice ${
                                        mode === option.value ? "active" : ""
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        className="form-check-input"
                                        name="research-mode"
                                        checked={mode === option.value}
                                        onChange={() => setMode(option.value)}
                                    />
                                    <span>
                                        <span className="d-block fw-semibold">
                                            <i className={`bi ${option.icon} me-2 text-primary`} />
                                            {option.title}
                                        </span>
                                        <span className="d-block small text-secondary mt-1">
                                            {option.text}
                                        </span>
                                    </span>
                                </label>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Card 2 — Research Details */}
            <div className="card">
                <div className="card-header d-flex align-items-center gap-2">
                    <span className="qv-step-badge">2</span>
                    <span className="fw-semibold">Research Details</span>
                </div>

                <div className="card-body d-flex flex-column gap-4">
                    <div>
                        <label className="form-label fw-medium">
                            {mode === "TOPIC" ? "Topic" : "Source URL"}
                        </label>
                        <input
                            className="form-control"
                            placeholder={
                                mode === "TOPIC"
                                    ? "e.g. Tomato cultivation best practices"
                                    : "https://www.youtube.com/watch?v=…"
                            }
                            value={inputValue}
                            onChange={event => setInputValue(event.target.value)}
                        />
                    </div>

                    {mode === "TOPIC" && (
                        <div>
                            <label className="form-label fw-medium d-flex justify-content-between">
                                <span>Sources</span>
                                <span className="badge text-bg-primary rounded-pill">
                                    {sourceCount}
                                </span>
                            </label>
                            <input
                                type="range"
                                className="form-range"
                                min={1}
                                max={10}
                                step={1}
                                value={sourceCount}
                                onChange={event =>
                                    setSourceCount(Number(event.target.value))
                                }
                            />
                            <div className="qv-range-marks">
                                {SOURCE_MARKS.map(mark => (
                                    <span
                                        key={mark}
                                        style={{
                                            left: `${((mark - 1) / 9) * 100}%`,
                                        }}
                                    >
                                        {mark}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    <div>
                        <label className="form-label fw-medium d-block">
                            Source Type
                        </label>
                        <div
                            className="btn-group flex-wrap"
                            role="group"
                            aria-label="Source type"
                        >
                            {providers.source_types.map(type => (
                                <button
                                    key={type}
                                    type="button"
                                    className={`btn btn-sm ${
                                        sourceType === type
                                            ? "btn-primary"
                                            : "btn-outline-secondary"
                                    }`}
                                    onClick={() => setSourceType(type)}
                                >
                                    {sourceTypeLabel(type)}
                                </button>
                            ))}
                        </div>
                        {providers.source_types.length === 1 && (
                            <div className="form-text">
                                More source types will appear here as their
                                search providers are enabled on the backend.
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Card 3 — AI Configuration */}
            <div className="card">
                <div className="card-header d-flex align-items-center gap-2">
                    <span className="qv-step-badge">3</span>
                    <span className="fw-semibold">AI Configuration</span>
                </div>

                <div className="card-body d-flex flex-column gap-3">
                    <div className="row g-3">
                        <div className="col-12 col-md-5">
                            <label className="form-label fw-medium">
                                Provider
                            </label>
                            <select
                                className="form-select"
                                value={aiProvider}
                                onChange={event =>
                                    handleProviderChange(event.target.value)
                                }
                            >
                                {providers.providers.map(provider => (
                                    <option
                                        key={provider.name}
                                        value={provider.name}
                                    >
                                        {provider.label}
                                        {provider.name ===
                                        providers.default_provider
                                            ? " (default)"
                                            : ""}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="col-12 col-md-7">
                            <label className="form-label fw-medium d-flex justify-content-between align-items-center">
                                <span>Model</span>
                                {models.loading && (
                                    <span className="spinner-border spinner-border-sm text-primary" />
                                )}
                            </label>

                            {models.list.length > 0 ? (
                                <>
                                    {models.list.length > 25 && (
                                        <input
                                            className="form-control form-control-sm mb-2"
                                            placeholder="Filter models…"
                                            value={modelFilter}
                                            onChange={event =>
                                                setModelFilter(
                                                    event.target.value
                                                )
                                            }
                                        />
                                    )}
                                    <select
                                        className="form-select"
                                        value={aiModel}
                                        onChange={event =>
                                            setAiModel(event.target.value)
                                        }
                                    >
                                        {aiModel &&
                                            !filteredModels.includes(
                                                aiModel
                                            ) && (
                                                <option value={aiModel}>
                                                    {aiModel}
                                                </option>
                                            )}
                                        {filteredModels.map(id => (
                                            <option key={id} value={id}>
                                                {id}
                                            </option>
                                        ))}
                                    </select>
                                </>
                            ) : (
                                <input
                                    className="form-control"
                                    placeholder={
                                        models.loading
                                            ? "Loading models…"
                                            : "Model id"
                                    }
                                    value={aiModel}
                                    onChange={event =>
                                        setAiModel(event.target.value)
                                    }
                                    disabled={models.loading}
                                />
                            )}

                            {models.error && (
                                <div className="form-text text-warning-emphasis">
                                    <i className="bi bi-exclamation-triangle me-1" />
                                    {models.error} You can type a model id
                                    manually.
                                </div>
                            )}
                        </div>
                    </div>

                    {providerInfo && !providerInfo.configured && (
                        <div className="alert alert-warning d-flex align-items-center justify-content-between gap-3 mb-0">
                            <div>
                                <i className="bi bi-key me-2" />
                                No API key configured for{" "}
                                <strong>{providerInfo.label}</strong>. Research
                                cannot start until{" "}
                                <code>{providerInfo.key_env}</code> is set on
                                the server.
                            </div>
                            <button
                                type="button"
                                className="btn btn-sm btn-warning flex-shrink-0"
                                onClick={onOpenSettings}
                            >
                                Configure
                            </button>
                        </div>
                    )}

                    <div>
                        <button
                            type="button"
                            className="btn btn-link btn-sm px-0 text-decoration-none"
                            onClick={() => setAdvancedOpen(open => !open)}
                        >
                            <i
                                className={`bi me-1 ${
                                    advancedOpen
                                        ? "bi-chevron-down"
                                        : "bi-chevron-right"
                                }`}
                            />
                            Advanced Settings
                        </button>

                        {advancedOpen && (
                            <div className="row g-3 mt-0 pt-2 border-top">
                                <div className="col-12 col-md-6">
                                    <label className="form-label fw-medium d-flex justify-content-between">
                                        <span>Temperature</span>
                                        <span className="badge text-bg-light border">
                                            {temperature.toFixed(2)}
                                        </span>
                                    </label>
                                    <input
                                        type="range"
                                        className="form-range"
                                        min={0}
                                        max={1}
                                        step={0.05}
                                        value={temperature}
                                        onChange={event =>
                                            setTemperature(
                                                Number(event.target.value)
                                            )
                                        }
                                    />
                                    <div className="d-flex justify-content-between small text-secondary">
                                        <span>Precise</span>
                                        <span>Creative</span>
                                    </div>
                                </div>

                                <div className="col-12 col-md-6">
                                    <label className="form-label fw-medium">
                                        Max Tokens
                                    </label>
                                    <input
                                        type="number"
                                        className="form-control"
                                        min={256}
                                        max={16000}
                                        step={256}
                                        value={maxTokens}
                                        onChange={event =>
                                            setMaxTokens(
                                                Number(event.target.value)
                                            )
                                        }
                                    />
                                    <div className="form-text">
                                        Per LLM call. Default 4000.
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Sticky primary action */}
            <div className="qv-sticky-actions">
                <button
                    className="btn btn-primary btn-lg px-5 shadow-sm"
                    disabled={!canStart}
                    onClick={handleSubmit}
                >
                    {submitting ? (
                        <>
                            <span className="spinner-border spinner-border-sm me-2" />
                            Starting…
                        </>
                    ) : (
                        <>
                            <i className="bi bi-stars me-2" />
                            Start Research
                        </>
                    )}
                </button>
            </div>

        </div>
    );
}
