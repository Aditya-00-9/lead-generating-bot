from app.models.schemas import NormalizedMention
from app.services.lead_pipeline import should_full_enrich


def _mention(text: str, recency: str | None = "last_month") -> NormalizedMention:
    return NormalizedMention(
        source="web",
        source_url="https://example.com/x",
        platform="reddit",
        raw_text=text,
        cleaned_text=text,
        recency_signal=recency,
    )


def test_should_full_enrich_requires_pain_signal() -> None:
    assert not should_full_enrich(_mention("Mindbody announced a new feature"))
    assert should_full_enrich(_mention("Switching from Mindbody due to terrible support"))


def test_should_full_enrich_blocks_older_recency() -> None:
    assert not should_full_enrich(
        _mention("Switching from Mindbody due to terrible support", recency="older")
    )
    assert should_full_enrich(
        _mention("Switching from Mindbody due to terrible support", recency="last_week")
    )
    assert should_full_enrich(
        _mention("Switching from Mindbody due to terrible support", recency=None)
    )


def test_triage_prompt_includes_competitors_and_platform() -> None:
    from app.classifiers.openai_enricher import _format_triage_user, _triage_system_prompt

    mention = _mention("Pike13 billing nightmare", "last_week")
    system = _triage_system_prompt("KramaAI studio software", ["Pike13", "Mindbody"])
    user = _format_triage_user(mention)
    assert "Pike13" in system
    assert "Mindbody" in system
    assert "KramaAI studio software" in system
    assert "platform=reddit" in user or "Platform: reddit" in user
    assert "```" in user
