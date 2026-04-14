from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.app_name == "Job Orchestration Service"
    assert settings.environment == "development"
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.redis_url is None
    assert settings.redis_start_guard_ttl_seconds == 30


def test_settings_reads_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("SHOWCASE_APP_NAME", "showcase-python-test")
    monkeypatch.setenv("SHOWCASE_ENVIRONMENT", "test")
    monkeypatch.setenv("SHOWCASE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SHOWCASE_OPENAI_MODEL", "gpt-4o-mini-test")
    monkeypatch.setenv("SHOWCASE_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("SHOWCASE_REDIS_START_GUARD_TTL_SECONDS", "45")

    settings = Settings()

    assert settings.app_name == "showcase-python-test"
    assert settings.environment == "test"
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4o-mini-test"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.redis_start_guard_ttl_seconds == 45
