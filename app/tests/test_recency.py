from datetime import datetime, timezone

from app.utils.recency import datetime_from_feedparser_struct, datetime_from_utc_timestamp, recency_factor


def test_datetime_from_utc_timestamp() -> None:
    dt = datetime_from_utc_timestamp(1_700_000_000)
    assert dt is not None
    assert dt.tzinfo == timezone.utc


def test_datetime_from_feedparser_struct() -> None:
    dt = datetime_from_feedparser_struct((2026, 6, 15, 12, 0, 0))
    assert dt == datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_recency_factor_signal_multipliers() -> None:
    assert recency_factor(10, "last_week") > recency_factor(10, "last_month")
    assert recency_factor(10, "last_month") > recency_factor(10, "older")
