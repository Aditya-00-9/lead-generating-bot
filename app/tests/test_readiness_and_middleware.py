from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_id_header_round_trip() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "trace-abc-123"


def test_request_id_generated_when_missing() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) >= 8


def test_ready_returns_503_when_database_unavailable() -> None:
    class _FailingSession:
        async def __aenter__(self) -> None:
            raise ConnectionError("simulated db down")

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    with patch("app.main.SessionLocal", return_value=_FailingSession()):
        client = TestClient(app)
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "database_unavailable"
