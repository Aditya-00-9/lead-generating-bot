import pytest

from app.collectors.openai_url_scrape import OpenAIUrlScrapeCollector
from app.collectors.openai_web_research import OpenAIWebResearchCollector
from app.config.settings import Settings
from app.models.schemas import ExtractedWebMentionsBatch


def test_extracted_web_mentions_batch_parses_minimal() -> None:
    b = ExtractedWebMentionsBatch.model_validate(
        {
            "items": [
                {"title": "t", "source_url": "https://example.com/thread", "excerpt": "body", "relevance_score": 80.0}
            ]
        }
    )
    assert len(b.items) == 1
    assert b.items[0].source_url.startswith("https://")
    assert b.items[0].platform == "other"
    assert b.items[0].pain_category == "other"


def test_extracted_web_mentions_batch_parses_phase2_fields() -> None:
    b = ExtractedWebMentionsBatch.model_validate(
        {
            "items": [
                {
                    "title": "Switching",
                    "source_url": "https://www.g2.com/products/x/reviews",
                    "excerpt": "Too expensive",
                    "relevance_score": 90.0,
                    "platform": "g2",
                    "competitor_mentioned": "Mindbody",
                    "pain_category": "pricing",
                    "author_handle": "Reviewer1",
                    "suggested_hook": "Pricing pain with Mindbody is rough.",
                    "recency_signal": "last_month",
                }
            ]
        }
    )
    item = b.items[0]
    assert item.platform == "g2"
    assert item.competitor_mentioned == "Mindbody"
    assert item.suggested_hook.startswith("Pricing")


@pytest.mark.asyncio
async def test_url_scrape_collect_empty_without_urls() -> None:
    s = Settings(
        openai_scraper_urls="",
        openai_api_key="sk-test",
        keywords="a,b",
        database_url="postgresql+psycopg://u:p@localhost/db",
        sync_database_url="postgresql+psycopg://u:p@localhost/db",
    )
    c = OpenAIUrlScrapeCollector(s)
    assert await c.collect(["a"], 10) == []


@pytest.mark.asyncio
async def test_web_research_collect_empty_without_keywords() -> None:
    s = Settings(
        enable_openai_web_research=True,
        openai_api_key="sk-test",
        keywords="",
        database_url="postgresql+psycopg://u:p@localhost/db",
        sync_database_url="postgresql+psycopg://u:p@localhost/db",
    )
    c = OpenAIWebResearchCollector(s)
    assert await c.collect([], 5) == []
