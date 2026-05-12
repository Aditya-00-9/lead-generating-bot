import pytest
from unittest.mock import AsyncMock, MagicMock

from app.scheduler.ingestion_lock import try_acquire_ingestion_advisory_lock


@pytest.mark.asyncio
async def test_advisory_lock_queries_pg_try() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = True
    session.execute = AsyncMock(return_value=result)
    assert await try_acquire_ingestion_advisory_lock(session) is True
    session.execute.assert_called_once()
    result = MagicMock()
    result.scalar_one.return_value = True
    session.execute = AsyncMock(return_value=result)
    assert await try_acquire_ingestion_advisory_lock(session) is True
    session.execute.assert_called_once()
