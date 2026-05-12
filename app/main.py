import uuid
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import text

from app.api.cron import router as cron_router
from app.api.routes import router as api_router
from app.config.settings import get_settings
from app.config.startup_validation import StartupValidationError, apply_api_startup_validation
from app.db.session import SessionLocal
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.app_env)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail fast in strict mode; otherwise warn and continue (local dev friendly)."""
    try:
        apply_api_startup_validation(get_settings())
    except StartupValidationError as exc:
        raise RuntimeError(str(exc)) from exc
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        structlog.contextvars.clear_contextvars()


app.include_router(api_router)
app.include_router(cron_router)


@app.get("/health")
async def health() -> dict:
    """Liveness: process is up (no external dependencies)."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    """Readiness: PostgreSQL reachable with current pool configuration."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001 — surface as 503 without leaking connection secrets
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
