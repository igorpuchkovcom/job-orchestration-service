from types import SimpleNamespace

import pytest

import app.providers.llm.openai_provider as openai_provider_module
from app.core.config import Settings
from app.orchestration.services.orchestration_service import (
    InferenceConfigurationError,
    create_default_provider,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "openai_api_key": "test-key",
        "openai_model": "gpt-4o-mini",
        "openai_timeout_seconds": 30.0,
        "openai_max_retries": 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_create_default_provider_uses_openai_compatible_local_runtime(monkeypatch) -> None:
    response = SimpleNamespace(output_text="local response", usage=None)
    captured_kwargs: dict[str, object] = {}

    class FakeOpenAIClient:
        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)
            self.responses = SimpleNamespace(create=lambda **_: response)

    monkeypatch.setattr(openai_provider_module, "OpenAI", FakeOpenAIClient)

    provider = create_default_provider(
        _settings(
            llm_runtime="openai_compatible_local",
            openai_base_url="http://127.0.0.1:11434/v1",
            openai_api_key=None,
        )
    )
    result = provider.generate_text("demo prompt")

    assert result.provider == "openai_compatible_local"
    assert result.model == "gpt-4o-mini"
    assert captured_kwargs == {
        "api_key": "local-dev-key",
        "timeout": 30.0,
        "base_url": "http://127.0.0.1:11434/v1",
    }


def test_create_default_provider_raises_for_unknown_model_id() -> None:
    with pytest.raises(InferenceConfigurationError, match="Unknown model_id"):
        create_default_provider(_settings(), model_id="unknown:model")


def test_create_default_provider_marks_vllm_stub_as_unsupported() -> None:
    with pytest.raises(InferenceConfigurationError, match="intentionally unsupported"):
        create_default_provider(_settings(llm_runtime="vllm_compatible_stub"))

