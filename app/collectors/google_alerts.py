import structlog
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import NormalizedMention

logger = structlog.get_logger(__name__)


class GoogleAlertsCollector(BaseCollector):
    name = "google_alerts"
    platform = "web"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(3), reraise=True)
    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        mentions: list[NormalizedMention] = []
        for url in self.settings.google_alert_url_list:
            logger.info("collector.google_alerts.feed_start", feed_url=url)
            feed = feedparser.parse(url)
            entries = feed.entries[:limit]
            for entry in entries:
                text = f"{entry.get('title', '')}\n\n{entry.get('summary', '')}".strip()
                mentions.append(
                    NormalizedMention(
                        source="Google Alerts",
                        source_url=entry.get("link", ""),
                        author=None,
                        platform=self.platform,
                        title=entry.get("title", ""),
                        raw_text=text,
                        cleaned_text=text[:6000],
                    )
                )
            logger.info("collector.google_alerts.feed_complete", feed_url=url, count=len(entries))
        return mentions
