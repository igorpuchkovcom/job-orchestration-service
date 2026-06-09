from dataclasses import dataclass
from typing import Any, Mapping

INFERENCE_NAMESPACE_KEY = "_inference"


class InvalidInferenceMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class InferenceMetadata:
    job_type: str | None = None
    model_id: str | None = None
    runtime: str | None = None
    resource_profile: str | None = None

    def as_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {}
        if self.job_type:
            payload["job_type"] = self.job_type
        if self.model_id:
            payload["model_id"] = self.model_id
        if self.runtime:
            payload["runtime"] = self.runtime
        if self.resource_profile:
            payload["resource_profile"] = self.resource_profile
        return payload

    def is_empty(self) -> bool:
        return not self.as_payload()


def extract_inference_metadata(input_payload: Mapping[str, Any]) -> InferenceMetadata:
    raw_metadata = input_payload.get(INFERENCE_NAMESPACE_KEY)
    if not isinstance(raw_metadata, dict):
        return InferenceMetadata()

    def _optional_text(value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return None

    return InferenceMetadata(
        job_type=_optional_text(raw_metadata.get("job_type")),
        model_id=_optional_text(raw_metadata.get("model_id")),
        runtime=_optional_text(raw_metadata.get("runtime")),
        resource_profile=_optional_text(raw_metadata.get("resource_profile")),
    )


def parse_inference_metadata(input_payload: Mapping[str, Any]) -> InferenceMetadata:
    raw_metadata = input_payload.get(INFERENCE_NAMESPACE_KEY)
    if raw_metadata is None:
        return InferenceMetadata()
    if not isinstance(raw_metadata, dict):
        raise InvalidInferenceMetadataError(
            "Invalid _inference metadata: expected an object."
        )

    def _required_text_or_none(field_name: str) -> str | None:
        value = raw_metadata.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise InvalidInferenceMetadataError(
                f"Invalid _inference.{field_name}: expected a non-empty string."
            )
        return value.strip()

    return InferenceMetadata(
        job_type=_required_text_or_none("job_type"),
        model_id=_required_text_or_none("model_id"),
        runtime=_required_text_or_none("runtime"),
        resource_profile=_required_text_or_none("resource_profile"),
    )


def with_inference_metadata(
    input_payload: Mapping[str, Any], metadata: InferenceMetadata
) -> dict[str, Any]:
    merged_payload: dict[str, Any] = dict(input_payload)
    metadata_payload = metadata.as_payload()
    if metadata_payload:
        existing_metadata = merged_payload.get(INFERENCE_NAMESPACE_KEY)
        if isinstance(existing_metadata, dict):
            merged_payload[INFERENCE_NAMESPACE_KEY] = {**existing_metadata, **metadata_payload}
        else:
            merged_payload[INFERENCE_NAMESPACE_KEY] = metadata_payload
    return merged_payload

