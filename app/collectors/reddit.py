from typing import Any

import asyncio
import praw
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import NormalizedMention

logger = structlog.get_logger(__name__)


class RedditCollector(BaseCollector):
    name = "reddit"
    platform = "reddit"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = praw.Reddit(
            client_id=settings.reddit_client_id or None,
            client_secret=settings.reddit_client_secret or None,
            user_agent=settings.reddit_user_agent,
        )

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(3), reraise=True)
    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        mentions: list[NormalizedMention] = []
        subreddits = "+".join(self.settings.reddit_subreddit_list) or "all"

        for keyword in keywords:
            logger.info("collector.reddit.search_start", keyword=keyword, subreddits=subreddits)
            submissions = await asyncio.to_thread(
                lambda: list(self.client.subreddit(subreddits).search(keyword, sort="new", limit=limit))
            )
            for post in submissions:
                mentions.append(self._to_mention(post))
            logger.info("collector.reddit.search_complete", keyword=keyword, count=len(submissions))
        return mentions

    def _to_mention(self, post: Any) -> NormalizedMention:
        body = f"{post.title}\n\n{post.selftext or ''}".strip()
        return NormalizedMention(
            source="Reddit",
            source_url=f"https://www.reddit.com{post.permalink}",
            author=str(getattr(post, "author", "") or ""),
            platform=self.platform,
            title=post.title or "",
            raw_text=body,
            cleaned_text=body[:6000],
        )
