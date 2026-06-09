import pytest

from app.model_registry.registry import resolve_model
from app.providers.llm.runtimes import LLMRuntime


def test_model_registry_resolves_known_model_id() -> None:
    model = resolve_model("openai:gpt-4o-mini")

    assert model.model_id == "openai:gpt-4o-mini"
    assert model.runtime == LLMRuntime.OPENAI_API
    assert model.provider_model == "gpt-4o-mini"


def test_model_registry_raises_for_unknown_model_id() -> None:
    with pytest.raises(ValueError, match="Unknown model_id"):
        resolve_model("unknown:model")

