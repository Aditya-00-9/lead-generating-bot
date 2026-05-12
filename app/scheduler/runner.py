import asyncio

import structlog

from app.config.settings import get_settings
from app.config.startup_validation import apply_ingestion_startup_validation
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.scheduler.ingestion_lock import release_ingestion_advisory_lock, try_acquire_ingestion_advisory_lock
from app.services.lead_pipeline import LeadPipelineService
from app.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


async def run_once() -> list[Lead]:
    settings = get_settings()
    configure_logging(settings.log_level)
    apply_ingestion_startup_validation(settings)
    async with SessionLocal() as session:
        if not await try_acquire_ingestion_advisory_lock(session):
            logger.warning("ingestion.skipped", reason="advisory_lock_busy")
            return []
        try:
            service = LeadPipelineService(settings, session)
            return await service.run_daily_ingestion()
        finally:
            try:
                await release_ingestion_advisory_lock(session)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ingestion.lock.release_failed", error=str(exc))


if __name__ == "__main__":
    asyncio.run(run_once())
