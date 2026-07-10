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


class KnowledgeConfig:

    @staticmethod
    def llm_provider():
        return os.environ.get("LLM_PROVIDER", "openai")

    @staticmethod
    def openai_api_key():
        return os.environ.get("OPENAI_API_KEY", "")

    @staticmethod
    def openai_base_url():
        return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @staticmethod
    def default_model():
        return os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")

    @staticmethod
    def storage_root():
        return os.environ.get("KNOWLEDGE_STORAGE_ROOT", "storage/knowledge")
