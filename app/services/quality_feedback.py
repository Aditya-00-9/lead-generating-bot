"""Human-score feedback aggregation for periodic template/ranker review."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead


@dataclass
class QualityCombo:
    platform: str
    competitor: str
    pain_category: str
    avg_human_score: float
    sample_count: int


async def aggregate_high_quality_combos(
    session: AsyncSession,
    *,
    min_avg_score: float = 4.0,
    min_samples: int = 2,
) -> list[QualityCombo]:
    pain_expr = func.coalesce(Lead.pain_category, "other")
    rows = await session.execute(
        select(
            Lead.platform,
            Lead.competitor,
            pain_expr.label("pain_category"),
            func.avg(Lead.human_score).label("avg_score"),
            func.count(Lead.id).label("sample_count"),
        )
        .where(Lead.human_score.isnot(None))
        .group_by(Lead.platform, Lead.competitor, pain_expr)
        .having(func.avg(Lead.human_score) >= min_avg_score, func.count(Lead.id) >= min_samples)
        .order_by(func.avg(Lead.human_score).desc(), func.count(Lead.id).desc())
    )
    return [
        QualityCombo(
            platform=str(platform or "other"),
            competitor=str(competitor),
            pain_category=str(pain_category or "other"),
            avg_human_score=round(float(avg_score or 0), 2),
            sample_count=int(sample_count),
        )
        for platform, competitor, pain_category, avg_score, sample_count in rows.all()
    ]


def build_quality_feedback_report(combos: list[QualityCombo], *, report_date: date | None = None) -> dict:
    report_date = report_date or datetime.now(timezone.utc).date()
    return {
        "report_date": report_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_note": (
            "Manual periodic review: bias search templates in collection_signals.py and "
            "ranker weights toward these high-scoring (platform, competitor, pain_category) combos. "
            "Do not auto-mutate prompts from this report."
        ),
        "high_quality_combos": [asdict(combo) for combo in combos],
    }


def export_quality_feedback_report(
    combos: list[QualityCombo],
    output_dir: str,
    *,
    report_date: date | None = None,
) -> Path:
    payload = build_quality_feedback_report(combos, report_date=report_date)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"quality_feedback_{payload['report_date']}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
