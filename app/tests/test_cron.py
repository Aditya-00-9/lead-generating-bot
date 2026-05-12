from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_cron_rejects_when_secret_not_configured(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CRON_SECRET", "")
    get_settings.cache_clear()
    response = client.get("/api/cron/daily-ingestion")
    assert response.status_code == 503


def test_cron_rejects_bad_token(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CRON_SECRET", "expected")
    get_settings.cache_clear()
    response = client.get("/api/cron/daily-ingestion", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


def test_cron_runs_pipeline_when_authorized(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CRON_SECRET", "expected")
    get_settings.cache_clear()
    with patch("app.api.cron.run_once", new=AsyncMock(return_value=[])) as mocked:
        response = client.get("/api/cron/daily-ingestion", headers={"Authorization": "Bearer expected"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "leads_created": 0}
    mocked.assert_awaited_once()
