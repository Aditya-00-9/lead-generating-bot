from datetime import datetime, timedelta, timezone

from app.ranking.lead_ranker import LeadRanker


def test_ranker_weights_reddit_and_mindbody() -> None:
    ranker = LeadRanker()
    now = datetime.now(timezone.utc)
    score = ranker.score(
        intent=80,
        urgency=70,
        engagement=60,
        source_quality=50,
        source="Reddit",
        competitor="Mindbody",
        created_at=now,
    )
    assert score > 0


def test_ranker_recency_decays() -> None:
    ranker = LeadRanker()
    now = datetime.now(timezone.utc)
    fresh = ranker.score(80, 70, 60, 50, "blog", "unknown", now)
    old = ranker.score(80, 70, 60, 50, "blog", "unknown", now - timedelta(days=30))
    assert fresh > old
