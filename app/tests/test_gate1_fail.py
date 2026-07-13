from app.models.lead import IntentLabel, Lead
from app.models.schemas import NormalizedMention
from app.services.lead_pipeline import should_persist_gate1_fail
from app.slack.digest import filter_digest_leads


def _mention(relevance: float | None, text: str = "generic mention") -> NormalizedMention:
    return NormalizedMention(
        source="OpenAI Web Research",
        source_url=f"https://example.com/{relevance}",
        platform="web",
        raw_text=text,
        cleaned_text=text,
        collection_relevance_score=relevance,
    )


def test_should_persist_gate1_fail_only_high_relevance() -> None:
    batch = [
        _mention(75.0),
        _mention(60.0),
        _mention(59.9),
        _mention(45.0),
        _mention(None),
    ]
    persisted = [m for m in batch if should_persist_gate1_fail(m, min_relevance=60.0)]
    assert len(persisted) == 2
    assert all(m.collection_relevance_score is not None and m.collection_relevance_score >= 60 for m in persisted)


def test_filter_digest_leads_worth_responding_and_rank_floor() -> None:
    leads = [
        Lead(
            source="x",
            source_url="https://a",
            platform="reddit",
            raw_text="t",
            cleaned_text="t",
            competitor="Mindbody",
            detected_pain_points=[],
            intent_score=70,
            intent_label=IntentLabel.high,
            worth_responding=True,
            ai_summary="s",
            suggested_reply="r",
            sentiment="negative",
            urgency_score=50,
            engagement_score=50,
            duplicate_hash="h1",
            rank_score=25.0,
        ),
        Lead(
            source="x",
            source_url="https://b",
            platform="reddit",
            raw_text="t",
            cleaned_text="t",
            competitor="Pike13",
            detected_pain_points=[],
            intent_score=30,
            intent_label=IntentLabel.low,
            worth_responding=False,
            ai_summary="s",
            suggested_reply="r",
            sentiment="neutral",
            urgency_score=0,
            engagement_score=0,
            duplicate_hash="h2",
            rank_score=80.0,
        ),
        Lead(
            source="x",
            source_url="https://c",
            platform="g2",
            raw_text="t",
            cleaned_text="t",
            competitor="MyStudio",
            detected_pain_points=[],
            intent_score=65,
            intent_label=IntentLabel.medium,
            worth_responding=True,
            ai_summary="s",
            suggested_reply="r",
            sentiment="negative",
            urgency_score=40,
            engagement_score=40,
            duplicate_hash="h3",
            rank_score=5.0,
        ),
    ]
    assert len(filter_digest_leads(leads, min_rank_score=0.0)) == 2
    filtered = filter_digest_leads(leads, min_rank_score=20.0)
    assert len(filtered) == 1
    assert filtered[0].source_url == "https://a"
