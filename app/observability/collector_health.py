"""Per-collector health records and last ingestion run snapshot."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CollectorHealth:
    name: str
    last_success_at: str | None = None
    last_item_count: int = 0
    last_error: str | None = None
    last_duration_s: float = 0.0


@dataclass
class LastRunSnapshot:
    finished_at: str | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)
    collectors: list[dict[str, Any]] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)


_health_by_name: dict[str, CollectorHealth] = {}
_last_run = LastRunSnapshot()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_collector_run(
    name: str,
    *,
    item_count: int = 0,
    error: str | None = None,
    duration_s: float = 0.0,
) -> CollectorHealth:
    row = _health_by_name.get(name) or CollectorHealth(name=name)
    row.last_duration_s = round(duration_s, 2)
    row.last_item_count = item_count
    if error:
        row.last_error = error[:500]
    else:
        row.last_success_at = _now_iso()
        row.last_error = None
    _health_by_name[name] = row
    return row


def all_collector_health() -> list[CollectorHealth]:
    return sorted(_health_by_name.values(), key=lambda row: row.name)


def set_last_run_snapshot(
    *,
    telemetry: dict[str, Any],
    collectors: list[CollectorHealth] | None = None,
    cost: dict[str, Any] | None = None,
) -> LastRunSnapshot:
    _last_run.finished_at = _now_iso()
    _last_run.telemetry = telemetry
    _last_run.collectors = [asdict(row) for row in (collectors or all_collector_health())]
    _last_run.cost = cost or {}
    return _last_run


def get_last_run_snapshot() -> dict[str, Any]:
    return asdict(_last_run)


def reset_collector_health_for_tests() -> None:
    _health_by_name.clear()
    global _last_run
    _last_run = LastRunSnapshot()
