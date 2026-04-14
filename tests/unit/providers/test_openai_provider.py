from types import SimpleNamespace

import pytest

from app.providers.llm.openai_provider import OpenAIProvider


def test_openai_provider_returns_bounded_generation_result() -> None:
    response = SimpleNamespace(
        output_text="provider text",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_: response),
    )

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
    )

    result = provider.generate_text("demo prompt")

    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.content == "provider text"
    assert result.usage == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }


def test_openai_provider_raises_for_missing_api_key() -> None:
    with pytest.raises(ValueError, match="OpenAI API key must be configured"):
        OpenAIProvider(api_key=None, model="gpt-4o-mini")


def test_openai_provider_wraps_sdk_errors() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **_: (_ for _ in ()).throw(RuntimeError("sdk failure"))
        ),
    )

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
    )

    with pytest.raises(RuntimeError, match="OpenAI request failed: sdk failure"):
        provider.generate_text("demo prompt")


def test_openai_provider_falls_back_to_output_content_extraction() -> None:
    response = SimpleNamespace(
        output_text=None,
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(type="output_text", text="first"),
                    SimpleNamespace(type="output_text", text="second"),
                ],
            )
        ],
        usage=None,
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_: response),
    )

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
    )

    result = provider.generate_text("demo prompt")

    assert result.content == "first\nsecond"
    assert result.usage is None
