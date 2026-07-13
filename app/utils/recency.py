"""Post-date resolution and recency weighting for lead ranking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

RECENCY_SIGNAL_MULTIPLIERS: dict[str, float] = {
    "last_week": 1.3,
    "last_month": 1.0,
    "last_90_days": 0.9,
    "older": 0.5,
    "unknown": 1.0,
}

_RECENCY_SIGNAL_OFFSET_DAYS: dict[str, int] = {
    "last_week": 5,
    "last_month": 20,
    "last_90_days": 60,
    "older": 180,
}


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def infer_date_from_recency_signal(signal: str | None, *, now: datetime | None = None) -> datetime | None:
    days = _RECENCY_SIGNAL_OFFSET_DAYS.get((signal or "").strip().lower())
    if days is None:
        return None
    anchor = utc_datetime(now or datetime.now(timezone.utc))
    return anchor - timedelta(days=days)


def resolve_reference_date(
    *,
    source_published_at: datetime | None,
    recency_signal: str | None,
    ingested_at: datetime,
) -> datetime:
    if source_published_at is not None:
        return utc_datetime(source_published_at)
    inferred = infer_date_from_recency_signal(recency_signal)
    if inferred is not None:
        return inferred
    return utc_datetime(ingested_at)


def recency_factor(age_days: int, recency_signal: str | None) -> float:
    age_days = max(0, age_days)
    age_mult = 1 / (1 + 0.08 * age_days)
    signal_mult = RECENCY_SIGNAL_MULTIPLIERS.get((recency_signal or "unknown").lower(), 1.0)
    return age_mult * signal_mult


def datetime_from_utc_timestamp(timestamp: float | int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)


def datetime_from_feedparser_struct(time_struct: object | None) -> datetime | None:
    if not time_struct:
        return None
    try:
        parts = tuple(time_struct)[:6]
        return datetime(*parts, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
