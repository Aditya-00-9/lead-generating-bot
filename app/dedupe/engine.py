from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlparse

from app.prompts.collection_signals import is_near_duplicate_text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.schemas import NormalizedMention


@dataclass
class DedupeDecision:
    is_duplicate: bool
    duplicate_hash: str
    reason: str


class DedupeEngine:
    def __init__(self, similarity_threshold: int, window_days: int, candidate_window: int = 200) -> None:
        self.similarity_threshold = similarity_threshold
        self.window_days = window_days
        self.candidate_window = candidate_window

    def compute_hash(self, mention: NormalizedMention) -> str:
        normalized = " ".join(mention.cleaned_text.lower().split())
        seed = f"{self._canonicalize_url(mention.source_url)}|{normalized[:1000]}"
        return sha256(seed.encode("utf-8")).hexdigest()

    def _canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _mention_competitor_key(self, mention: NormalizedMention) -> str:
        return (mention.competitor_mentioned or "").lower()

    def is_near_duplicate_in_batch(self, mention: NormalizedMention, batch: list[NormalizedMention]) -> bool:
        new_text = mention.cleaned_text
        new_comp = self._mention_competitor_key(mention)
        for existing in batch:
            if is_near_duplicate_text(
                new_text,
                existing.cleaned_text,
                threshold=self.similarity_threshold,
                competitor_a=new_comp or None,
                competitor_b=self._mention_competitor_key(existing) or None,
            ):
                return True
        return False

    async def check(self, session: AsyncSession, mention: NormalizedMention) -> DedupeDecision:
        duplicate_hash = self.compute_hash(mention)
        window_start = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        canonical_url = self._canonicalize_url(mention.source_url)
        exact = await session.scalar(
            select(Lead.id).where(Lead.source_url.in_([mention.source_url, canonical_url])).limit(1)
        )
        if exact:
            return DedupeDecision(True, duplicate_hash, "url_match")

        # Hash-level dedupe.
        hash_match = await session.scalar(
            select(Lead.id).where(Lead.duplicate_hash == duplicate_hash, Lead.created_at >= window_start).limit(1)
        )
        if hash_match:
            return DedupeDecision(True, duplicate_hash, "hash_match")

        # Fuzzy dedupe against recent content (same competitor when known).
        mention_comp = self._mention_competitor_key(mention)
        recent = await session.execute(
            select(Lead.cleaned_text, Lead.competitor, Lead.competitor_mentioned).where(
                Lead.created_at >= window_start
            ).limit(self.candidate_window)
        )
        new_text = mention.cleaned_text
        for existing_text, competitor, competitor_mentioned in recent:
            lead_comp = (competitor_mentioned or competitor or "").lower()
            if mention_comp and lead_comp and mention_comp != lead_comp:
                continue
            if is_near_duplicate_text(
                new_text,
                existing_text or "",
                threshold=self.similarity_threshold,
                competitor_a=mention_comp or None,
                competitor_b=lead_comp or None,
            ):
                return DedupeDecision(True, duplicate_hash, "fuzzy_match")

        return DedupeDecision(False, duplicate_hash, "unique")
