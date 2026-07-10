import hashlib
import json

from app.config.knowledge_config import KnowledgeConfig
from app.models.llm_result import LLMResult
from app.services.llm_providers.openai_provider import OpenAIProvider


class LLMService:
    """Single entrypoint for all LLM access. Business logic calls only
    ``LLMService.generate(...)`` / ``generate_json(...)`` and never touches a
    provider SDK. Add a new provider by registering it in ``_PROVIDERS``."""

    _PROVIDERS = {
        "openai": OpenAIProvider,
    }

    def __init__(self, provider=None):
        provider_name = provider or KnowledgeConfig.llm_provider()

        provider_cls = self._PROVIDERS.get(provider_name)

        if provider_cls is None:
            raise RuntimeError(
                f"Unknown LLM provider '{provider_name}'. "
                f"Available: {', '.join(self._PROVIDERS)}"
            )

        self.provider_name = provider_name
        self._provider = provider_cls()

    def generate(
        self,
        system_prompt,
        user_prompt,
        model=None,
        temperature=0.2,
        max_tokens=2000,
        json_mode=False,
    ) -> LLMResult:
        return self._provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    def generate_json(
        self,
        system_prompt,
        user_prompt,
        model=None,
        temperature=0.2,
        max_tokens=2000,
    ):
        """Returns ``(parsed_dict, LLMResult)``. Falls back to extracting the
        first JSON object from the response if the model wraps it in prose."""

        result = self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        parsed = self._parse_json(result.content)

        return parsed, result

    @staticmethod
    def _parse_json(content):
        content = (content or "").strip()

        if not content:
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        start = content.find("{")
        end = content.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass

        return {}

    @staticmethod
    def hash_text(text):
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
