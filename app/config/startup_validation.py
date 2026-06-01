from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from app.config.settings import Settings

log = structlog.get_logger(__name__)


class StartupValidationError(RuntimeError):
    """Raised when startup checks fail."""


def _parse_database_url(database_url: str) -> None:
    if not database_url or not database_url.strip():
        raise ValueError("DATABASE_URL is empty")
    make_url(database_url)


def _common_ingestion_checks(settings: Settings) -> list[str]:
    problems: list[str] = []
    try:
        _parse_database_url(settings.database_url)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"Invalid DATABASE_URL: {exc}")

    key = settings.openai_api_key.strip()
    if not key:
        problems.append("OPENAI_API_KEY is required for ingestion")
    elif not key.startswith("sk-"):
        problems.append("OPENAI_API_KEY must start with sk-")

    if not settings.keyword_list:
        problems.append("KEYWORDS must contain at least one phrase for ingestion")

    webhook = settings.slack_webhook_url.strip()
    if webhook and "hooks.slack.com" not in webhook:
        problems.append("SLACK_WEBHOOK_URL must contain hooks.slack.com when set")

    db_url = settings.database_url.lower()
    if "neon.tech" in db_url and "ssl=require" not in db_url and "sslmode=require" not in db_url:
        problems.append("DATABASE_URL for neon.tech must include ssl=require or sslmode=require")

    if settings.strict_startup_validation and not settings.google_alert_url_list:
        problems.append("GOOGLE_ALERT_RSS_URLS is empty (strict mode)")
    if settings.strict_startup_validation and (
        not settings.reddit_client_id.strip() or not settings.reddit_client_secret.strip()
    ):
        problems.append("Reddit credentials missing (strict mode)")

    return problems


def validate_settings_for_api(settings: Settings) -> list[str]:
    problems: list[str] = []
    try:
        _parse_database_url(settings.database_url)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"Invalid DATABASE_URL: {exc}")
    if settings.app_env == "production" and not settings.openai_api_key.strip():
        problems.append("OPENAI_API_KEY is required when APP_ENV=production")
    return problems


def validate_settings_for_ingestion(settings: Settings) -> list[str]:
    return _common_ingestion_checks(settings)


def apply_api_startup_validation(settings: Settings) -> None:
    problems = validate_settings_for_api(settings)
    if not problems:
        return
    if settings.strict_startup_validation:
        raise StartupValidationError("; ".join(problems))
    for p in problems:
        log.warning("startup.validation.warning", problem=p)


def apply_ingestion_startup_validation(settings: Settings) -> None:
    problems = validate_settings_for_ingestion(settings)
    if problems:
        raise StartupValidationError("; ".join(problems))
