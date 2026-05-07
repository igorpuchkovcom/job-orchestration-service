import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from openai import OpenAI

TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
TRANSIENT_ERROR_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "RateLimitError",
    "ServiceUnavailableError",
}
NON_TRANSIENT_ERROR_NAMES = {
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "NotFoundError",
    "PermissionDeniedError",
    "UnprocessableEntityError",
}


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
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: OpenAI | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key must be configured for provider-backed execution.")
        if not model:
            raise ValueError("OpenAI model must be configured for provider-backed execution.")
        if timeout_seconds <= 0:
            raise ValueError("OpenAI timeout_seconds must be greater than zero.")
        if max_retries < 0:
            raise ValueError("OpenAI max_retries must be zero or greater.")

        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client = client or OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._sleep = sleep_fn or time.sleep

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        if not prompt.strip():
            raise ValueError("Provider prompt must not be empty.")

        retries = 0
        while True:
            try:
                response = self.client.responses.create(model=self.model, input=prompt)
                break
            except Exception as error:
                if retries >= self.max_retries or not self._is_transient_error(error):
                    raise RuntimeError(f"OpenAI request failed: {error}") from error

                retries += 1
                self._sleep(self._retry_backoff_seconds(retries))

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

    @staticmethod
    def _retry_backoff_seconds(retry_number: int) -> float:
        # Keep retry waits bounded and short for this synchronous flow.
        return min(0.25 * (2 ** (retry_number - 1)), 2.0)

    @staticmethod
    def _is_transient_error(error: Exception) -> bool:
        error_name = type(error).__name__
        if error_name in NON_TRANSIENT_ERROR_NAMES:
            return False
        if error_name in TRANSIENT_ERROR_NAMES:
            return True

        status_code = getattr(error, "status_code", None)
        if isinstance(status_code, int):
            return status_code in TRANSIENT_STATUS_CODES

        return isinstance(error, (ConnectionError, OSError, TimeoutError))
