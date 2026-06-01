from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
from slack_sdk.web.async_client import AsyncWebClient

from app.models.lead import Lead


@dataclass
class RunTelemetry:
    collected: int = 0
    deduped: int = 0
    gate1_passed: int = 0
    gate2_passed: int = 0
    enriched: int = 0
    new_leads: int = 0
    api_calls: int = 0
    runtime_s: float = 0.0


def _telemetry_header(telemetry: RunTelemetry, report_date: date) -> dict:
    text = (
        f"KramaAI · {report_date.isoformat()}\n"
        f"{telemetry.collected} collected → {telemetry.deduped} deduped → "
        f"{telemetry.gate1_passed} pain signal → {telemetry.gate2_passed} intent≥50 → "
        f"{telemetry.enriched} enriched → {telemetry.new_leads} new leads\n"
        f"🔢 {telemetry.api_calls} OpenAI calls · ⏱ {telemetry.runtime_s}s"
    )
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def build_digest_blocks(
    leads: list[Lead], telemetry: RunTelemetry | None = None, report_date: date | None = None
) -> list[dict]:
    blocks: list[dict] = [{"type": "header", "text": {"type": "plain_text", "text": "KramaAI Daily Lead Digest"}}]
    if telemetry and report_date:
        blocks.append(_telemetry_header(telemetry, report_date))
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
            pain = ", ".join(item.detected_pain_points[:2]) or "Unspecified pain"
            text = (
                f"*<{item.source_url}|{item.source}>* | score `{item.intent_score:.1f}` "
                f"| rank `{item.rank_score:.2f}`\n"
                f"Pain: {pain}\nSummary: {item.ai_summary}\nReply: {item.suggested_reply}"
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
) -> None:
    payload = {
        "channel": channel,
        "blocks": build_digest_blocks(leads, telemetry=telemetry, report_date=report_date),
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
