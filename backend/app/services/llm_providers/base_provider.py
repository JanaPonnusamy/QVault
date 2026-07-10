from app.models.llm_result import LLMResult


class BaseLLMProvider:
    """Provider interface. Every provider must return an LLMResult so the rest
    of the application stays provider-independent."""

    name = "base"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMResult:
        raise NotImplementedError
