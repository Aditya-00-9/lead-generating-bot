from datetime import datetime, timezone

from app.utils.recency import recency_factor, resolve_reference_date

SOURCE_WEIGHTS = {
    "g2": 1.5,
    "capterra": 1.4,
    "linkedin": 1.3,
    "reddit": 1.2,
    "trustpilot": 1.15,
    "hackernews": 1.1,
    "twitter": 0.8,
    "blog": 0.6,
}

COMPETITOR_WEIGHTS = {
    "mindbody": 1.35,
    "pike13": 1.2,
    "mystudio": 1.2,
    "glofox": 1.1,
}


class LeadRanker:
    def score(
        self,
        intent: float,
        urgency: float,
        engagement: float,
        source_quality: float,
        source: str,
        competitor: str,
        ingested_at: datetime,
        platform: str | None = None,
        recency_signal: str | None = None,
        source_published_at: datetime | None = None,
    ) -> float:
        reference = resolve_reference_date(
            source_published_at=source_published_at,
            recency_signal=recency_signal,
            ingested_at=ingested_at,
        )
        age_days = (datetime.now(timezone.utc) - reference).days
        recency = recency_factor(age_days, recency_signal)
        source_key = f"{platform or ''} {source}".lower()
        source_w = 1.0
        for key, weight in SOURCE_WEIGHTS.items():
            if key in source_key:
                source_w = weight
                break
        competitor_w = COMPETITOR_WEIGHTS.get(competitor.lower(), 1.0)
        base = 0.45 * intent + 0.30 * urgency + 0.15 * engagement + 0.10 * source_quality
        return round(base * recency * source_w * competitor_w, 4)
