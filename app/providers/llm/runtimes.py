from enum import Enum


class LLMRuntime(str, Enum):
    OPENAI_API = "openai_api"
    OPENAI_COMPATIBLE_LOCAL = "openai_compatible_local"
    VLLM_COMPATIBLE_STUB = "vllm_compatible_stub"

