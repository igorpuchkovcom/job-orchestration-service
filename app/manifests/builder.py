from typing import Any, TypedDict

from app.persistence.models import Job


class ResultSummary(TypedDict):
    content: str
    provider: str
    model: str


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

    return {
        "content": content.strip(),
        "provider": provider.strip(),
        "model": model.strip(),
    }
