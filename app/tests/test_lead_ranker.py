from datetime import datetime, timedelta, timezone

from app.ranking.lead_ranker import LeadRanker
from app.utils.recency import infer_date_from_recency_signal, recency_factor, resolve_reference_date


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
        ingested_at=now,
    )
    assert score > 0


def test_ranker_recency_decays_with_post_date() -> None:
    ranker = LeadRanker()
    ingested = datetime.now(timezone.utc)
    fresh_post = ingested - timedelta(days=2)
    old_post = ingested - timedelta(days=90)
    fresh = ranker.score(
        80, 70, 60, 50, "blog", "unknown", ingested, source_published_at=fresh_post
    )
    old = ranker.score(
        80, 70, 60, 50, "blog", "unknown", ingested, source_published_at=old_post
    )
    assert fresh > old


def test_ranker_uses_post_date_not_ingestion_when_available() -> None:
    ranker = LeadRanker()
    ingested = datetime.now(timezone.utc)
    old_post = ingested - timedelta(days=60)
    with_post = ranker.score(
        80, 70, 60, 50, "blog", "unknown", ingested, source_published_at=old_post
    )
    ingestion_only = ranker.score(80, 70, 60, 50, "blog", "unknown", ingested)
    assert with_post < ingestion_only


def test_ranker_platform_g2_beats_blog() -> None:
    ranker = LeadRanker()
    now = datetime.now(timezone.utc)
    g2 = ranker.score(80, 70, 60, 50, "OpenAI Web Research", "Mindbody", now, platform="g2")
    blog = ranker.score(80, 70, 60, 50, "OpenAI Web Research", "Mindbody", now, platform="other")
    assert g2 > blog


def test_ranker_recency_signal_aggressive_weights() -> None:
    ranker = LeadRanker()
    now = datetime.now(timezone.utc)
    post = now - timedelta(days=3)
    recent = ranker.score(
        80, 70, 60, 50, "web", "x", now, source_published_at=post, recency_signal="last_week"
    )
    older = ranker.score(
        80, 70, 60, 50, "web", "x", now, source_published_at=post, recency_signal="older"
    )
    assert recent > older
    assert recency_factor(3, "last_week") > recency_factor(3, "older")


def test_resolve_reference_date_prefers_source_published_at() -> None:
    ingested = datetime(2026, 7, 6, tzinfo=timezone.utc)
    published = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ref = resolve_reference_date(
        source_published_at=published,
        recency_signal="last_week",
        ingested_at=ingested,
    )
    assert ref == published


def test_infer_date_from_recency_signal() -> None:
    now = datetime(2026, 7, 6, tzinfo=timezone.utc)
    inferred = infer_date_from_recency_signal("last_month", now=now)
    assert inferred is not None
    assert (now - inferred).days == 20
