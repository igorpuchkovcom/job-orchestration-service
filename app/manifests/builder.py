from typing import Any, TypedDict

from app.persistence.models import Job


class ResultSummary(TypedDict):
    content: str
    provider: str
    model: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    total_tokens: int
    model_id: str
    runtime: str


def build_result_summary(job: Job) -> ResultSummary | None:
    if job.status != "completed":
        return None

    for step in job.steps:
        if step.step_key != "llm_generate_text":
            continue
        if step.status != "completed":
            continue
        if step.output_payload is None:
            return None

        return _build_summary_from_payload(step.output_payload)

    return None


def _build_summary_from_payload(payload: dict[str, Any]) -> ResultSummary | None:
    content = payload.get("content")
    provider = payload.get("provider")
    model = payload.get("model")

    if not isinstance(content, str) or not content.strip():
        return None
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(model, str) or not model.strip():
        return None

    summary: ResultSummary = {
        "content": content.strip(),
        "provider": provider.strip(),
        "model": model.strip(),
    }
    _set_optional_int(summary, "latency_ms", payload.get("latency_ms"))
    _set_optional_int(summary, "tokens_in", payload.get("tokens_in"))
    _set_optional_int(summary, "tokens_out", payload.get("tokens_out"))
    _set_optional_int(summary, "total_tokens", payload.get("total_tokens"))
    _set_optional_text(summary, "model_id", payload.get("model_id"))
    _set_optional_text(summary, "runtime", payload.get("runtime"))
    return summary


def _set_optional_int(summary: ResultSummary, field_name: str, value: object) -> None:
    if isinstance(value, int):
        summary[field_name] = value


def _set_optional_text(summary: ResultSummary, field_name: str, value: object) -> None:
    if isinstance(value, str) and value.strip():
        summary[field_name] = value.strip()
