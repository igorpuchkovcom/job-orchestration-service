from app.providers.llm.openai_provider import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        if not base_url:
            raise ValueError(
                "openai_compatible_local runtime requires a base_url for the local endpoint."
            )
        super().__init__(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            base_url=base_url,
            provider_name="openai_compatible_local",
        )

