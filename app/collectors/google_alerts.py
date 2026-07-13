import structlog
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import NormalizedMention
from app.utils.platform import platform_from_url
from app.utils.recency import datetime_from_feedparser_struct

logger = structlog.get_logger(__name__)


class GoogleAlertsCollector(BaseCollector):
    name = "google_alerts"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(3), reraise=True)
    async def collect(
        self,
        keywords: list[str],
        limit: int,
        exclude_urls: list[str] | None = None,
    ) -> list[NormalizedMention]:
        exclude = {u.strip().rstrip("/").lower() for u in (exclude_urls or []) if u.strip()}
        mentions: list[NormalizedMention] = []
        for url in self.settings.google_alert_url_list:
            logger.info("collector.google_alerts.feed_start", feed_url=url)
            feed = feedparser.parse(url)
            entries = feed.entries[:limit]
            for entry in entries:
                text = f"{entry.get('title', '')}\n\n{entry.get('summary', '')}".strip()
                link = entry.get("link", "")
                if exclude and link.strip().rstrip("/").lower() in exclude:
                    continue
                published = datetime_from_feedparser_struct(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                )
                mentions.append(
                    NormalizedMention(
                        source="Google Alerts",
                        source_url=link,
                        author=None,
                        platform=platform_from_url(link),
                        title=entry.get("title", ""),
                        raw_text=text,
                        cleaned_text=text[:6000],
                        source_published_at=published,
                    )
                )
            logger.info("collector.google_alerts.feed_complete", feed_url=url, count=len(entries))
        return mentions
