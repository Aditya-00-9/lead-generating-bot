from app.collectors.mention_mapper import mention_from_extracted
from app.models.schemas import ExtractedWebMention
from app.utils.platform import platform_from_url, resolve_platform


def test_platform_from_url_reddit() -> None:
    assert platform_from_url("https://www.reddit.com/r/smallbusiness/comments/abc") == "reddit"


def test_platform_from_url_capterra() -> None:
    assert platform_from_url("https://www.capterra.com/p/177467/MyStudio-App/reviews/") == "capterra"


def test_resolve_platform_prefers_model_when_specific() -> None:
    assert resolve_platform("g2", "https://example.com/page") == "g2"


def test_resolve_platform_falls_back_to_url() -> None:
    assert resolve_platform("web", "https://g2.com/products/x") == "g2"


def test_mention_from_extracted_maps_fields() -> None:
    item = ExtractedWebMention(
        title="Bad support",
        source_url="https://www.reddit.com/r/test/comments/1",
        excerpt="Thinking of switching from Pike13",
        relevance_score=85.0,
        platform="reddit",
        competitor_mentioned="Pike13",
        pain_category="support",
        author_handle="u/example",
        suggested_hook="Sorry you're dealing with Pike13 support issues.",
        recency_signal="last_week",
    )
    mention = mention_from_extracted(item, source="OpenAI Web Research")
    assert mention is not None
    assert mention.platform == "reddit"
    assert mention.author == "u/example"
    assert mention.competitor_mentioned == "Pike13"
    assert mention.pain_category == "support"
    assert mention.suggested_hook is not None
    assert mention.recency_signal == "last_week"
