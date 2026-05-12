"""Postgres advisory locks to avoid overlapping ingestion (GitHub Actions overlap, double cron)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fixed pair: product-wide lock namespace (avoid collisions with other apps on shared DB).
_INGESTION_LOCK_A = 781_002_101
_INGESTION_LOCK_B = 918_273_645


async def try_acquire_ingestion_advisory_lock(session: AsyncSession) -> bool:
    result = await session.execute(
        text("SELECT pg_try_advisory_lock(:a, :b)"),
        {"a": _INGESTION_LOCK_A, "b": _INGESTION_LOCK_B},
    )
    return bool(result.scalar_one())


async def release_ingestion_advisory_lock(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(:a, :b)"),
        {"a": _INGESTION_LOCK_A, "b": _INGESTION_LOCK_B},
    )
