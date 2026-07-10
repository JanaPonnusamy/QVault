import { KnowledgeProviders } from "../../types/knowledgeResearch";

interface Props {
    open: boolean;
    providers: KnowledgeProviders | null;
    onClose: () => void;
}

export default function SettingsDrawer({ open, providers, onClose }: Props) {

    if (!open) {
        return null;
    }

    return (
        <>
            <div className="qv-drawer-backdrop" onClick={onClose} />

            <div
                className="qv-drawer"
                role="dialog"
                aria-label="Research settings"
            >
                <div className="qv-drawer-header">
                    <i className="bi bi-gear text-primary" />
                    <span className="fw-semibold flex-grow-1">
                        AI Provider Settings
                    </span>
                    <button
                        className="btn btn-sm btn-light"
                        aria-label="Close"
                        onClick={onClose}
                    >
                        <i className="bi bi-x-lg" />
                    </button>
                </div>

                <div className="qv-drawer-body">

                    <p className="small text-secondary">
                        API keys are stored on the server in{" "}
                        <code>config/.env</code> and are never sent to the
                        browser. To enable a provider, add its key to that file
                        and restart the backend.
                    </p>

                    {!providers && (
                        <div className="d-flex align-items-center gap-2 text-secondary py-3">
                            <span className="spinner-border spinner-border-sm" />
                            Loading…
                        </div>
                    )}

                    {providers?.providers.map(provider => (
                        <div
                            key={provider.name}
                            className="qv-history-item"
                        >
                            <div className="d-flex align-items-center justify-content-between gap-2">
                                <span className="fw-medium">
                                    {provider.label}
                                    {provider.name ===
                                        providers.default_provider && (
                                        <span className="badge text-bg-primary ms-2">
                                            default
                                        </span>
                                    )}
                                </span>

                                {provider.configured ? (
                                    <span className="badge text-bg-success">
                                        <i className="bi bi-check-circle me-1" />
                                        Configured
                                    </span>
                                ) : (
                                    <span className="badge text-bg-warning">
                                        <i className="bi bi-key me-1" />
                                        No API key
                                    </span>
                                )}
                            </div>

                            <div className="small text-secondary mt-2">
                                {provider.requires_key ? (
                                    <>
                                        Key variable:{" "}
                                        <code>{provider.key_env}</code>
                                    </>
                                ) : (
                                    "Runs locally — no API key required."
                                )}
                                {provider.default_model && (
                                    <div>
                                        Default model:{" "}
                                        <code>{provider.default_model}</code>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                </div>
            </div>
        </>
    );
}
