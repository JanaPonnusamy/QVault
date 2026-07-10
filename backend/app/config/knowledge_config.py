import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

ENV_PATH = ROOT / "config" / ".env"

PIPELINE_VERSION = "1.0.0"


def _load_env_file():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


# Every provider speaks the OpenAI chat-completions protocol (natively or via
# a compatibility endpoint), so configuration is just: which env var holds the
# key, where the endpoint lives, and which env var names the default model.
PROVIDER_SPECS = {
    "openrouter": {
        "label": "OpenRouter",
        "key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "model_env": "OPENROUTER_DEFAULT_MODEL",
        "requires_key": True,
    },
    "openai": {
        "label": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1",
        "model_env": "OPENAI_DEFAULT_MODEL",
        "requires_key": True,
    },
    "anthropic": {
        "label": "Anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com/v1/",
        "model_env": "ANTHROPIC_DEFAULT_MODEL",
        "requires_key": True,
    },
    "google": {
        "label": "Google Gemini",
        "key_env": "GOOGLE_API_KEY",
        "base_url_env": "GOOGLE_BASE_URL",
        "default_base_url": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
        "model_env": "GOOGLE_DEFAULT_MODEL",
        "requires_key": True,
    },
    "ollama": {
        "label": "Ollama (local)",
        "key_env": "OLLAMA_API_KEY",
        "base_url_env": "OLLAMA_BASE_URL",
        "default_base_url": "http://localhost:11434/v1",
        "model_env": "OLLAMA_DEFAULT_MODEL",
        "requires_key": False,
    },
}

DEFAULT_PROVIDER = "openrouter"


class KnowledgeConfig:

    @staticmethod
    def llm_provider():
        provider = os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)

        # Legacy configs said LLM_PROVIDER=openai while actually pointing the
        # OpenAI base URL at OpenRouter. Treat those as OpenRouter.
        if provider == "openai" and "openrouter" in os.environ.get(
            "OPENAI_BASE_URL", ""
        ):
            return "openrouter"

        return provider

    @staticmethod
    def provider_spec(provider):
        return PROVIDER_SPECS.get(provider)

    @classmethod
    def provider_api_key(cls, provider):
        spec = cls.provider_spec(provider)

        if not spec:
            return ""

        key = os.environ.get(spec["key_env"], "")

        # Legacy fallback: OpenRouter keys used to live in OPENAI_API_KEY with
        # OPENAI_BASE_URL pointing at openrouter.ai.
        if not key and provider == "openrouter" and "openrouter" in os.environ.get(
            "OPENAI_BASE_URL", ""
        ):
            key = os.environ.get("OPENAI_API_KEY", "")

        return key

    @classmethod
    def provider_base_url(cls, provider):
        spec = cls.provider_spec(provider)

        if not spec:
            return ""

        return os.environ.get(spec["base_url_env"], spec["default_base_url"])

    @classmethod
    def provider_default_model(cls, provider):
        spec = cls.provider_spec(provider)

        if not spec:
            return ""

        return os.environ.get(spec["model_env"], "")

    @classmethod
    def provider_configured(cls, provider):
        spec = cls.provider_spec(provider)

        if not spec:
            return False

        if not spec["requires_key"]:
            return True

        return bool(cls.provider_api_key(provider))

    @classmethod
    def default_model(cls):
        return cls.provider_default_model(cls.llm_provider())

    # Kept for callers that predate the provider registry.
    @staticmethod
    def openai_api_key():
        return os.environ.get("OPENAI_API_KEY", "")

    @staticmethod
    def openai_base_url():
        return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @staticmethod
    def storage_root():
        return os.environ.get("KNOWLEDGE_STORAGE_ROOT", "storage/knowledge")
