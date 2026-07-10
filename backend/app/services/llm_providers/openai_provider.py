import time

from openai import OpenAI

from app.config.knowledge_config import KnowledgeConfig
from app.models.llm_result import LLMResult
from app.services.llm_providers.base_provider import BaseLLMProvider


# Approximate USD per 1K tokens. Used only for reproducibility metadata; the
# provider works regardless of whether a model is listed here.
_PRICING = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "openai/gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "openai/gpt-4o": (0.0025, 0.01),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "openai/gpt-4.1-mini": (0.0004, 0.0016),
}


class OpenAICompatibleProvider(BaseLLMProvider):
    """Shared implementation for every provider that exposes an
    OpenAI-compatible chat-completions endpoint (OpenRouter, OpenAI, Anthropic,
    Google Gemini, Ollama). Subclasses only declare ``name``; key, base URL and
    default model come from the provider registry in KnowledgeConfig. Isolated
    here so business logic never touches the SDK."""

    name = "openai-compatible"

    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 2

    def __init__(self):
        spec = KnowledgeConfig.provider_spec(self.name)

        if spec is None:
            raise RuntimeError(f"Unknown provider '{self.name}'.")

        api_key = KnowledgeConfig.provider_api_key(self.name)

        if spec["requires_key"] and not api_key:
            raise RuntimeError(
                f"{spec['key_env']} is not configured. Set it in config/.env."
            )

        self._client = OpenAI(
            # The SDK requires a non-empty key even for keyless local
            # endpoints such as Ollama.
            api_key=api_key or "not-required",
            base_url=KnowledgeConfig.provider_base_url(self.name),
        )

    def list_models(self):
        """Model ids available on this provider's endpoint, sorted."""
        return sorted(model.id for model in self._client.models.list())

    def generate(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature,
        max_tokens,
        json_mode,
    ) -> LLMResult:

        model = model or KnowledgeConfig.provider_default_model(self.name)

        if not model:
            raise RuntimeError(
                f"No model specified and no default model configured for "
                f"provider '{self.name}'."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            started = time.time()

            try:
                response = self._client.chat.completions.create(**kwargs)

                latency_ms = int((time.time() - started) * 1000)

                content = response.choices[0].message.content or ""

                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(usage, "completion_tokens", 0) or 0

                return LLMResult(
                    content=content,
                    provider=self.name,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=self._estimate_cost(
                        model, input_tokens, output_tokens
                    ),
                    latency_ms=latency_ms,
                    status="SUCCESS",
                )

            except Exception as error:  # noqa: BLE001 - surfaced to caller below
                last_error = error

                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_BACKOFF_SECONDS * attempt)

        raise RuntimeError(
            f"LLM call failed after {self.MAX_RETRIES} attempts: {last_error}"
        )

    @staticmethod
    def _estimate_cost(model, input_tokens, output_tokens):
        rates = _PRICING.get(model)

        if not rates:
            return 0.0

        input_rate, output_rate = rates

        return round(
            (input_tokens / 1000.0) * input_rate
            + (output_tokens / 1000.0) * output_rate,
            6,
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"


class AnthropicProvider(OpenAICompatibleProvider):
    name = "anthropic"


class GoogleProvider(OpenAICompatibleProvider):
    name = "google"


class OllamaProvider(OpenAICompatibleProvider):
    name = "ollama"
