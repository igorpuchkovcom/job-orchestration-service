from types import SimpleNamespace

import pytest

import app.providers.llm.openai_provider as openai_provider_module
from app.providers.llm.openai_provider import OpenAIProvider


class FakeTransientError(Exception):
    def __init__(self, message: str = "transient failure", status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(Exception):
    pass


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


def test_openai_provider_applies_timeout_when_creating_client(monkeypatch) -> None:
    response = SimpleNamespace(output_text="provider text", usage=None)
    captured_kwargs: dict[str, object] = {}

    class FakeOpenAIClient:
        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)
            self.responses = SimpleNamespace(create=lambda **_: response)

    monkeypatch.setattr(openai_provider_module, "OpenAI", FakeOpenAIClient)

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        timeout_seconds=12.5,
    )

    result = provider.generate_text("demo prompt")

    assert result.content == "provider text"
    assert captured_kwargs == {"api_key": "test-key", "timeout": 12.5}


def test_openai_provider_raises_for_missing_api_key() -> None:
    with pytest.raises(ValueError, match="OpenAI API key must be configured"):
        OpenAIProvider(api_key=None, model="gpt-4o-mini")


def test_openai_provider_rejects_invalid_retry_settings() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be greater than zero"):
        OpenAIProvider(api_key="test-key", model="gpt-4o-mini", timeout_seconds=0)

    with pytest.raises(ValueError, match="max_retries must be zero or greater"):
        OpenAIProvider(api_key="test-key", model="gpt-4o-mini", max_retries=-1)


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


def test_openai_provider_retries_transient_errors_up_to_max_retries() -> None:
    calls = {"count": 0}
    sleep_calls: list[float] = []

    def failing_create(**_):
        calls["count"] += 1
        raise FakeTransientError("retry me", status_code=503)

    client = SimpleNamespace(
        responses=SimpleNamespace(create=failing_create),
    )
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
        max_retries=2,
        sleep_fn=sleep_calls.append,
    )

    with pytest.raises(RuntimeError, match="OpenAI request failed: retry me"):
        provider.generate_text("demo prompt")

    assert calls["count"] == 3
    assert sleep_calls == [0.25, 0.5]


def test_openai_provider_does_not_retry_non_transient_errors() -> None:
    calls = {"count": 0}
    sleep_calls: list[float] = []

    def failing_create(**_):
        calls["count"] += 1
        raise AuthenticationError("bad api key")

    client = SimpleNamespace(
        responses=SimpleNamespace(create=failing_create),
    )
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
        max_retries=3,
        sleep_fn=sleep_calls.append,
    )

    with pytest.raises(RuntimeError, match="OpenAI request failed: bad api key"):
        provider.generate_text("demo prompt")

    assert calls["count"] == 1
    assert sleep_calls == []


def test_openai_provider_returns_successful_response_after_retry() -> None:
    calls = {"count": 0}
    sleep_calls: list[float] = []
    successful_response = SimpleNamespace(
        output_text="recovered response",
        usage=SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3),
    )

    def create_with_one_failure(**_):
        calls["count"] += 1
        if calls["count"] == 1:
            raise FakeTransientError("temporary failure", status_code=429)
        return successful_response

    client = SimpleNamespace(
        responses=SimpleNamespace(create=create_with_one_failure),
    )
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-4o-mini",
        client=client,
        max_retries=2,
        sleep_fn=sleep_calls.append,
    )

    result = provider.generate_text("demo prompt")

    assert calls["count"] == 2
    assert sleep_calls == [0.25]
    assert result.content == "recovered response"
    assert result.usage == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
    }


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
