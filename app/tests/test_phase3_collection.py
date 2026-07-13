from app.dedupe.engine import DedupeEngine
from app.models.schemas import ExtractedWebMention, NormalizedMention
from app.prompts.collection_signals import (
    blend_source_quality,
    passes_competitor_context,
    select_urls_for_deep_extract,
    text_has_pain_signal,
)


def test_search_templates_no_stale_year() -> None:
    from app.prompts.collection_signals import SEARCH_QUERY_TEMPLATES

    assert all("2024" not in tpl for tpl in SEARCH_QUERY_TEMPLATES)
    assert any("gymowners" in tpl for tpl in SEARCH_QUERY_TEMPLATES)
    assert any("alternative" in tpl and "2024" not in tpl for tpl in SEARCH_QUERY_TEMPLATES)


def test_passes_competitor_context_mindbody_requires_studio_context() -> None:
    assert not passes_competitor_context("I love mindbody meditation apps", ["Mindbody"], "Mindbody")
    assert passes_competitor_context(
        "Our yoga studio hates Mindbody billing", ["Mindbody"], "Mindbody"
    )


def test_passes_competitor_context_multiword_brand() -> None:
    assert passes_competitor_context("Zen Planner is too expensive", ["Zen Planner"], "Zen Planner")


def test_blend_source_quality() -> None:
    assert blend_source_quality(80.0, None) == 80.0
    assert blend_source_quality(80.0, 60.0) == round(0.55 * 80 + 0.45 * 60, 2)


def test_select_urls_for_deep_extract_prioritizes_reddit_and_skips_rich_excerpt() -> None:
    items = [
        ExtractedWebMention(
            title="listicle",
            source_url="https://medium.com/best-alternatives",
            excerpt="generic",
            relevance_score=99.0,
        ),
        ExtractedWebMention(
            title="thin",
            source_url="https://www.linkedin.com/posts/someone_complaint",
            excerpt="short blurb",
            relevance_score=50.0,
        ),
        ExtractedWebMention(
            title="rich pain",
            source_url="https://www.trustpilot.com/reviews/abc123",
            excerpt="We are switching from Mindbody because support is terrible",
            relevance_score=40.0,
        ),
        ExtractedWebMention(
            title="reddit thread",
            source_url="https://www.reddit.com/r/gymowners/comments/abc",
            excerpt="brief",
            relevance_score=70.0,
        ),
        ExtractedWebMention(
            title="g2 blocked",
            source_url="https://www.g2.com/products/x/reviews/1",
            excerpt="short",
            relevance_score=95.0,
        ),
    ]
    urls = select_urls_for_deep_extract(items, limit=2)
    assert "medium.com" not in urls[0]
    assert any("reddit.com" in u for u in urls)
    assert not any("trustpilot.com" in u for u in urls)
    assert not any("g2.com" in u for u in urls)


def test_is_near_duplicate_in_batch_same_competitor() -> None:
    engine = DedupeEngine(similarity_threshold=85, window_days=14)
    a = NormalizedMention(
        source="Reddit",
        source_url="https://reddit.com/a",
        platform="reddit",
        raw_text="Switching from Mindbody due to terrible support",
        cleaned_text="Switching from Mindbody due to terrible support",
        competitor_mentioned="Mindbody",
    )
    b = NormalizedMention(
        source="Reddit",
        source_url="https://reddit.com/b",
        platform="reddit",
        raw_text="Switching from Mindbody because of terrible support",
        cleaned_text="Switching from Mindbody because of terrible support",
        competitor_mentioned="Mindbody",
    )
    c = NormalizedMention(
        source="Reddit",
        source_url="https://reddit.com/c",
        platform="reddit",
        raw_text="Switching from Pike13 due to terrible support",
        cleaned_text="Switching from Pike13 due to terrible support",
        competitor_mentioned="Pike13",
    )
    batch = [a]
    assert engine.is_near_duplicate_in_batch(b, batch)
    assert not engine.is_near_duplicate_in_batch(c, batch)


def test_text_has_pain_signal_still_works() -> None:
    assert text_has_pain_signal("billing nightmare with Pike13")
