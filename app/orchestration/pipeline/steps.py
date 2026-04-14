from dataclasses import dataclass


@dataclass(frozen=True)
class FixedStepDefinition:
    step_key: str


FIXED_FLOW = [FixedStepDefinition(step_key="llm_generate_text")]
