import pytest

from app.config.settings import get_settings
from app.config.startup_validation import (
    StartupValidationError,
    apply_ingestion_startup_validation,
    validate_settings_for_ingestion,
)


def test_validate_ingestion_flags_empty_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYWORDS", "")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    s = get_settings()
    problems = validate_settings_for_ingestion(s)
    assert any("KEYWORDS" in p for p in problems)


def test_apply_ingestion_raises_in_production_when_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYWORDS", "")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    with pytest.raises(StartupValidationError):
        apply_ingestion_startup_validation(get_settings())
