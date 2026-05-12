import asyncio

from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.services.lead_pipeline import LeadPipelineService
from app.utils.logging import configure_logging


async def run_once() -> list[Lead]:
    settings = get_settings()
    configure_logging(settings.log_level)
    async with SessionLocal() as session:
        service = LeadPipelineService(settings, session)
        return await service.run_daily_ingestion()


if __name__ == "__main__":
    asyncio.run(run_once())
