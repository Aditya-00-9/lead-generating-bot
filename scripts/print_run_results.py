"""Print ingestion results from DB and last-run snapshot."""
import asyncio
import json

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.observability.collector_health import get_last_run_snapshot
from app.storage.lead_repository import LeadRepository


async def main() -> None:
    get_settings.cache_clear()
    async with SessionLocal() as session:
        repo = LeadRepository(session)
        stats = await repo.stats()
        total, leads = await repo.list(page=1, page_size=10, sort="rank_score")

    snap = get_last_run_snapshot()
    print("=== STATS ===")
    print(json.dumps(stats, indent=2))
    print("\n=== LAST RUN TELEMETRY ===")
    print(json.dumps(snap.get("telemetry", {}), indent=2))
    print("\n=== COLLECTOR HEALTH ===")
    for row in snap.get("collectors", []):
        err = f" ERROR: {row.get('last_error', '')[:60]}" if row.get("last_error") else ""
        print(f"  {row.get('name')}: {row.get('last_item_count', 0)} items{err}")
    print("\n=== COST ESTIMATE ===")
    print(json.dumps(snap.get("cost", {}), indent=2))
    print(f"\n=== TOP {len(leads)} LEADS (by rank_score) ===")
    for lead in leads:
        print(
            f"\n[{lead.intent_label.value}] rank={lead.rank_score:.2f} intent={lead.intent_score:.0f} "
            f"| {lead.competitor} | {lead.platform}"
        )
        print(f"  URL: {lead.source_url[:90]}")
        print(f"  Pain: {', '.join(lead.detected_pain_points[:2]) or lead.pain_category or 'n/a'}")
        print(f"  Summary: {lead.ai_summary[:160]}...")
        if lead.worth_responding:
            print(f"  Reply: {(lead.suggested_reply or '')[:120]}...")


if __name__ == "__main__":
    asyncio.run(main())
