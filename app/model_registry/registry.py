from dataclasses import dataclass

from app.providers.llm.runtimes import LLMRuntime


@dataclass(frozen=True)
class ModelRegistryEntry:
    model_id: str
    runtime: LLMRuntime
    provider_model: str
    base_url: str | None = None


_MODEL_REGISTRY: dict[str, ModelRegistryEntry] = {
    "openai:gpt-4o-mini": ModelRegistryEntry(
        model_id="openai:gpt-4o-mini",
        runtime=LLMRuntime.OPENAI_API,
        provider_model="gpt-4o-mini",
    ),
    "local:demo-openai-compatible": ModelRegistryEntry(
        model_id="local:demo-openai-compatible",
        runtime=LLMRuntime.OPENAI_COMPATIBLE_LOCAL,
        provider_model="local-demo-model",
    ),
}


def resolve_model(model_id: str) -> ModelRegistryEntry:
    entry = _MODEL_REGISTRY.get(model_id)
    if entry is None:
        raise ValueError(f"Unknown model_id: {model_id}")
    return entry

