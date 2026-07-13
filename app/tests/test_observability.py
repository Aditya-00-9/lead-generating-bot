from app.observability.collector_health import (
    get_last_run_snapshot,
    record_collector_run,
    reset_collector_health_for_tests,
    set_last_run_snapshot,
)
from app.observability.cost_estimate import estimate_run_cost
from app.services.quality_feedback import QualityCombo, build_quality_feedback_report
from app.slack.digest import _collector_health_footer, _cost_footer


def setup_function() -> None:
    reset_collector_health_for_tests()


def test_record_collector_run_success_and_error() -> None:
    record_collector_run("reddit", item_count=5, duration_s=1.2)
    row = record_collector_run("reddit", error="auth failed", duration_s=0.5)
    assert row.last_error == "auth failed"
    assert row.last_item_count == 0

    record_collector_run("google_alerts", item_count=3, duration_s=0.8)
    footer = _collector_health_footer(
        [
            {"name": "google_alerts", "last_item_count": 3, "last_success_at": "2026-07-06T12:00:00+00:00"},
            {"name": "reddit", "last_error": "auth failed"},
        ]
    )
    assert footer is not None
    assert "google_alerts" in footer
    assert "ERROR" in footer


def test_estimate_run_cost_positive_with_searches() -> None:
    cost = estimate_run_cost(
        web_searches=12,
        deep_extract_calls=8,
        chat_api_calls=20,
        triage_chars=40_000,
        enrich_chars=10_000,
        extract_chars=80_000,
        responses_model="gpt-4o",
        chat_model="gpt-4o-mini",
        extract_model="gpt-4o-mini",
    )
    assert cost.web_searches == 12
    assert cost.est_cost_usd > 0
    footer = _cost_footer(cost.to_dict())
    assert footer is not None
    assert "$" in footer


def test_last_run_snapshot_roundtrip() -> None:
    record_collector_run("openai_web_research", item_count=10, duration_s=2.0)
    set_last_run_snapshot(telemetry={"new_leads": 3}, cost={"est_cost_usd": 0.42})
    snap = get_last_run_snapshot()
    assert snap["telemetry"]["new_leads"] == 3
    assert snap["cost"]["est_cost_usd"] == 0.42
    assert snap["collectors"]


def test_build_quality_feedback_report() -> None:
    report = build_quality_feedback_report(
        [
            QualityCombo(
                platform="reddit",
                competitor="Mindbody",
                pain_category="pricing",
                avg_human_score=4.5,
                sample_count=3,
            )
        ]
    )
    assert report["high_quality_combos"][0]["competitor"] == "Mindbody"
    assert "Manual periodic review" in report["review_note"]
