from app.dedupe.engine import DedupeEngine
from app.models.schemas import NormalizedMention


def test_dedupe_hash_stable() -> None:
    engine = DedupeEngine(similarity_threshold=90, window_days=14)
    mention = NormalizedMention(
        source="Reddit",
        source_url="https://reddit.com/r/test/1",
        author="a",
        platform="reddit",
        raw_text="Need alternative to MyStudio",
        cleaned_text="Need alternative to MyStudio",
    )
    assert engine.compute_hash(mention) == engine.compute_hash(mention)
