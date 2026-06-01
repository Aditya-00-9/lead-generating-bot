from datetime import datetime, timezone

SOURCE_WEIGHTS = {
    "g2": 1.5,
    "capterra": 1.4,
    "linkedin": 1.3,
    "reddit": 1.2,
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
        created_at: datetime,
    ) -> float:
        age_days = (datetime.now(timezone.utc) - created_at).days
        recency = 1 / (1 + 0.1 * age_days)
        source_key = source.lower()
        source_w = 1.0
        for key, weight in SOURCE_WEIGHTS.items():
            if key in source_key:
                source_w = weight
                break
        competitor_w = COMPETITOR_WEIGHTS.get(competitor.lower(), 1.0)
        base = 0.45 * intent + 0.30 * urgency + 0.15 * engagement + 0.10 * source_quality
        return round(base * recency * source_w * competitor_w, 4)
