from collections import defaultdict
from pathlib import Path

import httpx
from slack_sdk.web.async_client import AsyncWebClient

from app.models.lead import Lead


def build_digest_blocks(leads: list[Lead]) -> list[dict]:
    blocks: list[dict] = [{"type": "header", "text": {"type": "plain_text", "text": "KramaAI Daily Lead Digest"}}]
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
                f"*<{item.source_url}|{item.source}>* | score `{item.intent_score:.1f}`\n"
                f"Pain: {pain}\nSummary: {item.ai_summary}\nReply: {item.suggested_reply}"
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
    return blocks


async def send_slack_digest(webhook_url: str, channel: str, leads: list[Lead], report_path: Path | None = None) -> None:
    payload = {"channel": channel, "blocks": build_digest_blocks(leads)}
    if report_path:
        payload["text"] = f"Daily report file generated: {report_path.name}"
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
