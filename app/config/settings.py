import os
from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.postgres_url import normalize_postgres_url


def _is_placeholder_google_feed(url: str) -> bool:
    u = url.lower()
    return "feeds/0000" in u or "feeds/00000000" in u or "/0000/" in u


def _default_report_output_dir() -> str:
    return "/tmp/reports" if os.environ.get("VERCEL") else "reports"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "kramaai-lead-monitor"
    app_env: str = "development"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    cron_secret: str = ""
    strict_startup_validation: bool = False

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kramaai_leads"
    sync_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kramaai_leads"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_triage_model: str = ""
    openai_timeout_seconds: int = 25
    min_enrich_score: float = 50.0
    reply_context: str = ""
    # OpenAI web discovery: on by default; set ENABLE_OPENAI_WEB_RESEARCH=false to disable (saves API cost).
    enable_openai_web_research: bool = True
    openai_responses_model: str = ""
    openai_web_research_max_tool_calls: int = 5
    openai_collection_timeout_seconds: int = 120
    openai_scraper_urls: str = ""
    openai_collection_model: str = ""
    openai_collection_min_relevance: float = 35.0

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

    duplicate_similarity_threshold: int = 85
    duplicate_window_days: int = 21
    dedupe_candidate_window: int = 200
    enable_placeholder_sources: bool = False
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

    @property
    def openai_scraper_url_list(self) -> List[str]:
        return [u.strip() for u in self.openai_scraper_urls.split(",") if u.strip()]

    @property
    def reddit_configured(self) -> bool:
        return bool(self.reddit_client_id.strip() and self.reddit_client_secret.strip())

    @property
    def google_alerts_configured(self) -> bool:
        urls = self.google_alert_url_list
        if not urls:
            return False
        return any(not _is_placeholder_google_feed(u) for u in urls)

    @property
    def openai_discovery_enabled(self) -> bool:
        return self.enable_openai_web_research and bool(self.openai_api_key.strip())

    @property
    def openai_triage_model_name(self) -> str:
        return (self.openai_triage_model or self.openai_model).strip()

    @model_validator(mode="after")
    def normalize_postgres_connection_urls(self) -> "Settings":
        object.__setattr__(self, "database_url", normalize_postgres_url(self.database_url))
        object.__setattr__(self, "sync_database_url", normalize_postgres_url(self.sync_database_url))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
