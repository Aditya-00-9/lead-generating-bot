from datetime import date

from app.collectors.openai_web_research import merge_extracted_batches
from app.models.schemas import ExtractedWebMention, ExtractedWebMentionsBatch
from app.prompts.collection_signals import (
    build_search_queries,
    format_seen_urls_block,
    is_deep_extract_denied,
    is_weak_listing_url,
    rotate_competitors,
    select_urls_for_deep_extract,
)


def test_build_search_queries_interleaves_competitors() -> None:
    queries = build_search_queries(
        ["Alpha", "Beta"],
        ["fallback kw"],
        max_searches=4,
        competitors_per_run=2,
        on_date=date(2026, 1, 1),
    )
    assert len(queries) == 4
    assert queries[0].startswith('site:reddit.com "Alpha"')
    assert queries[1].startswith('site:reddit.com "Beta"')
    assert "Alpha" in queries[2]
    assert "Beta" in queries[3]


def test_build_search_queries_uses_keywords_when_no_competitors() -> None:
    queries = build_search_queries([], ["kw one", "kw two"], max_searches=2, competitors_per_run=3)
    assert queries == ["kw one", "kw two"]


def test_rotate_competitors_by_day() -> None:
    brands = ["A", "B", "C", "D", "E", "F"]
    day1 = rotate_competitors(brands, competitors_per_run=4, on_date=date(2026, 1, 1))
    day2 = rotate_competitors(brands, competitors_per_run=4, on_date=date(2026, 1, 2))
    assert len(day1) == 4
    assert len(day2) == 4
    assert day1 != day2
    assert day1[0] == "A"
    assert day2[0] == "B"


def test_build_search_queries_rotates_subset() -> None:
    brands = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    q1 = build_search_queries(brands, [], max_searches=8, competitors_per_run=4, on_date=date(2026, 1, 1))
    q2 = build_search_queries(brands, [], max_searches=8, competitors_per_run=4, on_date=date(2026, 1, 5))
    assert any('"A"' in q for q in q1)
    assert not any('"E"' in q for q in q1)  # only first 4 of rotated slice
    assert any('"E"' in q for q in q2)


def test_is_weak_listing_url() -> None:
    assert is_weak_listing_url("https://www.g2.com/products/mindbody/reviews")
    assert is_weak_listing_url("https://www.g2.com/products/mindbody/reviews?qs=pros-and-cons")
    assert not is_weak_listing_url("https://www.g2.com/products/mindbody/reviews/12345-abc")
    assert is_weak_listing_url("https://www.capterra.com/p/134351/Zen-Planner/reviews/")
    assert is_weak_listing_url("https://www.trustpilot.com/review/wellnessliving.com")
    assert not is_weak_listing_url("https://www.trustpilot.com/reviews/64abc123def")
    assert not is_weak_listing_url("https://www.reddit.com/r/gymowners/comments/abc/thread/")


def test_deep_extract_denies_g2_and_capterra() -> None:
    assert is_deep_extract_denied("https://www.g2.com/products/x/reviews/1")
    assert is_deep_extract_denied("https://www.capterra.com/p/1/X/reviews/")
    assert not is_deep_extract_denied("https://www.reddit.com/r/x/comments/abc")


def test_select_urls_skips_g2_prefers_reddit() -> None:
    items = [
        ExtractedWebMention(
            title="g2",
            source_url="https://www.g2.com/products/x/reviews/1",
            excerpt="short",
            relevance_score=99.0,
        ),
        ExtractedWebMention(
            title="reddit",
            source_url="https://www.reddit.com/r/gymowners/comments/abc",
            excerpt="brief",
            relevance_score=50.0,
        ),
    ]
    urls = select_urls_for_deep_extract(items, limit=2)
    assert urls == ["https://www.reddit.com/r/gymowners/comments/abc"]


def test_format_seen_urls_block() -> None:
    block = format_seen_urls_block(["https://a.com/1", "https://b.com/2"], max_urls=10)
    assert "Already collected" in block
    assert "https://a.com/1" in block


def test_merge_extracted_batches_keeps_highest_score() -> None:
    a = ExtractedWebMentionsBatch(
        items=[
            ExtractedWebMention(
                title="low",
                source_url="https://reddit.com/r/x/comments/abc/thread/",
                excerpt="a",
                relevance_score=40.0,
            )
        ]
    )
    b = ExtractedWebMentionsBatch(
        items=[
            ExtractedWebMention(
                title="high",
                source_url="https://reddit.com/r/x/comments/abc/thread",
                excerpt="b",
                relevance_score=90.0,
            )
        ]
    )
    merged = merge_extracted_batches([a, b])
    assert len(merged.items) == 1
    assert merged.items[0].relevance_score == 90.0
    assert merged.items[0].title == "high"
