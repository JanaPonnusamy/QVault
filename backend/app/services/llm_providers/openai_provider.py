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
}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider. Works with OpenAI and any OpenAI-compatible
    endpoint (OpenRouter, Azure OpenAI proxies, local servers) by pointing the
    base URL at the target. Isolated here so business logic never touches the SDK."""

    name = "openai"

    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 2

    def __init__(self):
        api_key = KnowledgeConfig.openai_api_key()
        base_url = KnowledgeConfig.openai_base_url()

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in config/.env."
            )

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature,
        max_tokens,
        json_mode,
    ) -> LLMResult:

        model = model or KnowledgeConfig.default_model()

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
