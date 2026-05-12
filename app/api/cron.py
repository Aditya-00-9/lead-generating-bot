import structlog
from fastapi import APIRouter, Header, HTTPException

from app.config.settings import get_settings
from app.scheduler.runner import run_once

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["cron"])


@router.get(
    "/cron/daily-ingestion",
    summary="Vercel / manual cron: run daily lead ingestion",
    include_in_schema=False,
)
async def cron_daily_ingestion(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    settings = get_settings()
    secret = settings.cron_secret.strip()
    if not secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    leads = await run_once()
    n = len(leads)
    logger.info("cron.ingestion.complete", lead_count=n)
    return {"status": "ok", "leads_created": n}
