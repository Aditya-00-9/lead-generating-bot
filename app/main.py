import sentry_sdk
from fastapi import FastAPI

from app.api.cron import router as cron_router
from app.api.routes import router as api_router
from app.config.settings import get_settings
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.app_env)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(api_router)
app.include_router(cron_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
