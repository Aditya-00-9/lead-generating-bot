from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlparse

from rapidfuzz.fuzz import ratio
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
    def __init__(self, similarity_threshold: int, window_days: int) -> None:
        self.similarity_threshold = similarity_threshold
        self.window_days = window_days

    def compute_hash(self, mention: NormalizedMention) -> str:
        normalized = " ".join(mention.cleaned_text.lower().split())
        seed = f"{self._canonicalize_url(mention.source_url)}|{normalized[:1000]}"
        return sha256(seed.encode("utf-8")).hexdigest()

    def _canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    async def check(self, session: AsyncSession, mention: NormalizedMention) -> DedupeDecision:
        duplicate_hash = self.compute_hash(mention)
        window_start = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        # URL-level dedupe.
        exact = await session.scalar(select(Lead.id).where(Lead.source_url == mention.source_url).limit(1))
        if exact:
            return DedupeDecision(True, duplicate_hash, "url_match")

        # Hash-level dedupe.
        hash_match = await session.scalar(
            select(Lead.id).where(Lead.duplicate_hash == duplicate_hash, Lead.created_at >= window_start).limit(1)
        )
        if hash_match:
            return DedupeDecision(True, duplicate_hash, "hash_match")

        # Fuzzy dedupe against recent content only.
        recent = await session.execute(select(Lead.cleaned_text).where(Lead.created_at >= window_start).limit(500))
        new_text = mention.cleaned_text[:1000]
        for (existing_text,) in recent:
            if ratio(new_text, (existing_text or "")[:1000]) >= self.similarity_threshold:
                return DedupeDecision(True, duplicate_hash, "fuzzy_match")

        return DedupeDecision(False, duplicate_hash, "unique")
