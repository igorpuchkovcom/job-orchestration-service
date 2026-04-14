from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI


@dataclass(frozen=True)
class LLMGenerationResult:
    provider: str
    model: str
    content: str
    usage: dict[str, int] | None = None


class LLMProvider(Protocol):
    def generate_text(self, prompt: str) -> LLMGenerationResult:
        """Generate bounded text output for the orchestration flow."""


class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key must be configured for provider-backed execution.")
        if not model:
            raise ValueError("OpenAI model must be configured for provider-backed execution.")

        self.model = model
        self.client = client or OpenAI(api_key=api_key)

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        if not prompt.strip():
            raise ValueError("Provider prompt must not be empty.")

        try:
            response = self.client.responses.create(model=self.model, input=prompt)
        except Exception as error:
            raise RuntimeError(f"OpenAI request failed: {error}") from error

        content = self._extract_content(response)
        if not content:
            raise RuntimeError("OpenAI returned empty text output.")

        return LLMGenerationResult(
            provider="openai",
            model=self.model,
            content=content,
            usage=self._extract_usage(response),
        )

    @staticmethod
    def _extract_content(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        texts: list[str] = []
        for output in getattr(response, "output", []) or []:
            if getattr(output, "type", None) != "message":
                continue

            for content in getattr(output, "content", []) or []:
                if getattr(content, "type", None) != "output_text":
                    continue

                text = getattr(content, "text", None)
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())

        return "\n".join(texts).strip()

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None

        usage_payload: dict[str, int] = {}
        for field_name in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, field_name, None)
            if isinstance(value, int):
                usage_payload[field_name] = value

        return usage_payload or None
