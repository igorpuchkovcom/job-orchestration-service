from app.core.config import Settings


def test_settings_defaults(monkeypatch) -> None:
    # BaseSettings still reads os.environ when _env_file=None; isolate from CI/local env.
    for key in (
        "APP_NAME",
        "ENVIRONMENT",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "REDIS_URL",
        "REDIS_START_GUARD_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "Job Orchestration Service"
    assert settings.environment == "development"
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.redis_url is None
    assert settings.redis_start_guard_ttl_seconds == 30


def test_settings_reads_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "job-orchestration-service-test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini-test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("REDIS_START_GUARD_TTL_SECONDS", "45")

    settings = Settings(_env_file=None)

    assert settings.app_name == "job-orchestration-service-test"
    assert settings.environment == "test"
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4o-mini-test"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.redis_start_guard_ttl_seconds == 45
