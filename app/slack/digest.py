from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from slack_sdk.web.async_client import AsyncWebClient

from app.models.lead import Lead


@dataclass
class RunTelemetry:
    collected: int = 0
    deduped: int = 0
    gate1_passed: int = 0
    gate1_fail_dropped: int = 0
    gate1_fail_persisted: int = 0
    triage_skipped_low_relevance: int = 0
    enrich_skipped_stale: int = 0
    context_filtered: int = 0
    gate2_passed: int = 0
    enriched: int = 0
    new_leads: int = 0
    backfilled: int = 0
    api_calls: int = 0
    runtime_s: float = 0.0
    est_cost_usd: float = 0.0
    web_searches: int = 0


def _collector_health_footer(collectors: list[dict[str, Any]]) -> str | None:
    if not collectors:
        return None
    lines: list[str] = []
    for row in collectors:
        name = row.get("name", "?")
        if row.get("last_error"):
            lines.append(f"• *{name}*: ERROR — {row['last_error'][:80]}")
        else:
            ok_at = (row.get("last_success_at") or "never")[:19]
            lines.append(f"• *{name}*: {row.get('last_item_count', 0)} items @ {ok_at}")
    return " *Sources:*\n" + "\n".join(lines)


def _cost_footer(cost: dict[str, Any]) -> str | None:
    if not cost:
        return None
    usd = cost.get("est_cost_usd", 0)
    if not usd and not cost.get("web_searches"):
        return None
    return (
        f" *Cost est:* ~${usd:.3f} · {cost.get('web_searches', 0)} searches · "
        f"{cost.get('deep_extract_calls', 0)} extracts · {cost.get('chat_api_calls', 0)} chat calls · "
        f"~{(cost.get('est_input_tokens', 0) + cost.get('est_output_tokens', 0)):,} tokens"
    )


def filter_digest_leads(leads: list[Lead], min_rank_score: float) -> list[Lead]:
    """Slack digest: worth_responding leads meeting optional rank floor; Excel export stays unfiltered."""
    filtered = [
        lead
        for lead in leads
        if lead.worth_responding and (min_rank_score <= 0 or lead.rank_score >= min_rank_score)
    ]
    return sorted(filtered, key=lambda lead: (lead.rank_score, lead.intent_score), reverse=True)


def _telemetry_header(
    telemetry: RunTelemetry,
    report_date: date,
    *,
    collector_health: list[dict[str, Any]] | None = None,
    cost: dict[str, Any] | None = None,
) -> dict:
    text = (
        f"KramaAI · {report_date.isoformat()}\n"
        f"{telemetry.collected} collected → {telemetry.deduped} deduped → "
        f"{telemetry.gate1_passed} pain signal → {telemetry.gate2_passed} intent pass → "
        f"{telemetry.enriched} enriched → {telemetry.new_leads} new leads"
        f"{f' · {telemetry.gate1_fail_dropped} gate1-fail dropped' if telemetry.gate1_fail_dropped else ''}"
        f"{f' · {telemetry.context_filtered} context-filtered' if telemetry.context_filtered else ''}"
        f"{f' · {telemetry.triage_skipped_low_relevance} low-rel skip' if telemetry.triage_skipped_low_relevance else ''}"
        f"{f' · {telemetry.enrich_skipped_stale} stale skip' if telemetry.enrich_skipped_stale else ''}"
        f"{f' · {telemetry.backfilled} backfilled' if telemetry.backfilled else ''}\n"
        f"🔢 {telemetry.api_calls} OpenAI calls · ⏱ {telemetry.runtime_s}s"
    )
    health = _collector_health_footer(collector_health or [])
    if health:
        text += f"\n{health}"
    cost_line = _cost_footer(cost or {})
    if cost_line:
        text += f"\n{cost_line}"
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def build_digest_blocks(
    leads: list[Lead],
    telemetry: RunTelemetry | None = None,
    report_date: date | None = None,
    *,
    collector_health: list[dict[str, Any]] | None = None,
    cost: dict[str, Any] | None = None,
) -> list[dict]:
    blocks: list[dict] = [{"type": "header", "text": {"type": "plain_text", "text": "KramaAI Daily Lead Digest"}}]
    if telemetry and report_date:
        blocks.append(_telemetry_header(telemetry, report_date, collector_health=collector_health, cost=cost))
    if not leads:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "No new leads found today."}})
        return blocks

    grouped: dict[str, list[Lead]] = defaultdict(list)
    for lead in leads:
        grouped[f"{lead.intent_label.value} | {lead.competitor}"].append(lead)

    for key, items in grouped.items():
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{key}* ({len(items)})"}})
        for item in items[:20]:
            pain = ", ".join(item.detected_pain_points[:2]) or item.pain_category or "Unspecified pain"
            hook = (item.suggested_hook or "").strip()
            reply = (item.suggested_reply or "").strip()
            outreach = reply or hook
            text = (
                f"*<{item.source_url}|{item.platform or item.source}>* | score `{item.intent_score:.1f}` "
                f"| rank `{item.rank_score:.2f}`\n"
                f"Pain: {pain} | Recency: {item.recency_signal or 'unknown'}\n"
                f"Summary: {item.ai_summary}\n"
                f"{'Hook: ' + hook + chr(10) if hook and reply else ''}"
                f"Reply: {outreach}"
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
    return blocks


async def send_slack_digest(
    webhook_url: str,
    channel: str,
    leads: list[Lead],
    report_paths: list[Path] | None = None,
    telemetry: RunTelemetry | None = None,
    report_date: date | None = None,
    *,
    collector_health: list[dict[str, Any]] | None = None,
    cost: dict[str, Any] | None = None,
) -> None:
    payload = {
        "channel": channel,
        "blocks": build_digest_blocks(
            leads,
            telemetry=telemetry,
            report_date=report_date,
            collector_health=collector_health,
            cost=cost,
        ),
    }
    if report_paths:
        file_names = ", ".join(path.name for path in report_paths)
        payload["text"] = f"Daily reports generated: {file_names}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()


async def upload_report_to_slack(bot_token: str, channel_id: str, report_path: Path) -> None:
    client = AsyncWebClient(token=bot_token)
    await client.files_upload_v2(
        channel=channel_id,
        file=str(report_path),
        title=f"KramaAI Lead Report {report_path.stem}",
        initial_comment="Daily lead report file",
    )
