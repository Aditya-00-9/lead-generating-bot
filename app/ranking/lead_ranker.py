from app.models.schemas import AIEnrichmentResult


class LeadRanker:
    """Consolidates weighted signals into an operational rank score."""

    def score(self, enrichment: AIEnrichmentResult) -> float:
        return round(
            enrichment.intent_score * 0.5 + enrichment.urgency_score * 0.3 + enrichment.engagement_score * 0.2, 2
        )
