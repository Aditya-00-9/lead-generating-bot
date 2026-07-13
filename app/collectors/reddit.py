from typing import Any

import asyncio
import praw
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.collectors.base import BaseCollector
from app.config.settings import Settings
from app.models.schemas import NormalizedMention
from app.prompts.collection_signals import passes_competitor_context, text_has_pain_signal
from app.utils.recency import datetime_from_utc_timestamp

logger = structlog.get_logger(__name__)

_MAX_COMMENTS_PER_POST = 15


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
    async def collect(
        self,
        keywords: list[str],
        limit: int,
        exclude_urls: list[str] | None = None,
    ) -> list[NormalizedMention]:
        exclude = {u.strip().rstrip("/").lower() for u in (exclude_urls or []) if u.strip()}
        mentions: list[NormalizedMention] = []
        subreddits = "+".join(self.settings.reddit_subreddit_list) or "all"

        for keyword in keywords:
            logger.info("collector.reddit.search_start", keyword=keyword, subreddits=subreddits)
            submissions = await asyncio.to_thread(
                lambda kw=keyword: list(
                    self.client.subreddit(subreddits).search(kw, sort="new", limit=limit)
                )
            )
            for post in submissions:
                post_mentions = await asyncio.to_thread(self._mentions_from_post, post)
                if exclude:
                    post_mentions = [
                        m
                        for m in post_mentions
                        if m.source_url.strip().rstrip("/").lower() not in exclude
                    ]
                mentions.extend(post_mentions)
            logger.info("collector.reddit.search_complete", keyword=keyword, count=len(submissions))
        return mentions

    def _mentions_from_post(self, post: Any) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        body = f"{post.title}\n\n{post.selftext or ''}".strip()
        if not text_has_pain_signal(body):
            return out
        if not passes_competitor_context(body, self.settings.competitors, None):
            return out
        out.append(self._to_mention(post, body))
        out.extend(self._comment_mentions(post))
        return out

    def _comment_mentions(self, post: Any) -> list[NormalizedMention]:
        out: list[NormalizedMention] = []
        try:
            post.comments.replace_more(limit=0)
            for comment in post.comments.list()[:_MAX_COMMENTS_PER_POST]:
                body = (getattr(comment, "body", "") or "").strip()
                if not body or not text_has_pain_signal(body):
                    continue
                if not passes_competitor_context(body, self.settings.competitors, None):
                    continue
                out.append(
                    NormalizedMention(
                        source="Reddit",
                        source_url=f"https://www.reddit.com{comment.permalink}",
                        author=str(getattr(comment, "author", "") or ""),
                        platform=self.platform,
                        title=post.title or "",
                        raw_text=body,
                        cleaned_text=body[:6000],
                        source_published_at=datetime_from_utc_timestamp(getattr(comment, "created_utc", None)),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("collector.reddit.comments_failed", permalink=getattr(post, "permalink", ""), error=str(exc))
        return out

    def _to_mention(self, post: Any, body: str | None = None) -> NormalizedMention:
        text = body if body is not None else f"{post.title}\n\n{post.selftext or ''}".strip()
        return NormalizedMention(
            source="Reddit",
            source_url=f"https://www.reddit.com{post.permalink}",
            author=str(getattr(post, "author", "") or ""),
            platform=self.platform,
            title=post.title or "",
            raw_text=text,
            cleaned_text=text[:6000],
            source_published_at=datetime_from_utc_timestamp(getattr(post, "created_utc", None)),
        )
