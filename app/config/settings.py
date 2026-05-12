import os
from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.postgres_url import normalize_postgres_url


def _default_report_output_dir() -> str:
    return "/tmp/reports" if os.environ.get("VERCEL") else "reports"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kramaai-lead-monitor"
    app_env: str = "development"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    cron_secret: str = ""

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kramaai_leads"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kramaai_leads"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 25

    slack_webhook_url: str = ""
    slack_channel: str = "#kramaai-market-listening"
    slack_bot_token: str = ""
    slack_channel_id: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "kramaai-lead-monitor/1.0"
    reddit_subreddits: str = "smallbusiness,fitnessbusiness,martialarts"

    google_alert_rss_urls: str = ""
    keywords: str = ""
    max_items_per_query: int = 25

    duplicate_similarity_threshold: int = 90
    duplicate_window_days: int = 14
    enable_placeholder_sources: bool = True
    report_output_dir: str = Field(default_factory=_default_report_output_dir)
    scheduler_timezone: str = "Asia/Kolkata"
    scheduler_hour: int = 19
    scheduler_minute: int = 30

    competitors: List[str] = Field(
        default_factory=lambda: [
            "MyStudio",
            "Pike13",
            "iClassPro",
            "Zen Planner",
            "WellnessLiving",
            "Mindbody",
            "Jackrabbit",
            "Gymdesk",
            "Vagaro",
        ]
    )

    @property
    def keyword_list(self) -> List[str]:
        return [k.strip() for k in self.keywords.split(",") if k.strip()]

    @property
    def reddit_subreddit_list(self) -> List[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]

    @property
    def google_alert_url_list(self) -> List[str]:
        return [u.strip() for u in self.google_alert_rss_urls.split(",") if u.strip()]

    @model_validator(mode="after")
    def normalize_postgres_connection_urls(self) -> "Settings":
        object.__setattr__(self, "database_url", normalize_postgres_url(self.database_url))
        object.__setattr__(self, "sync_database_url", normalize_postgres_url(self.sync_database_url))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
