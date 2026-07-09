import pytest

from app.config import Settings


def test_settings_load_from_env_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://host:6379/1")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert settings.redis_url == "redis://host:6379/1"


def test_missing_openai_api_key_does_not_raise_at_import_time():
    settings = Settings(_env_file=None, openai_api_key=None)
    assert settings.openai_api_key is None


def test_missing_openai_api_key_raises_only_when_llm_call_attempted():
    settings = Settings(_env_file=None, openai_api_key=None)

    with pytest.raises(RuntimeError):
        settings.require_openai_api_key()
