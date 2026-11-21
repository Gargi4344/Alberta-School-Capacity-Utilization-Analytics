from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine


@pytest.fixture
def client_without_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Point at a port where nothing listens, so the test never needs a database.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:x@127.0.0.1:1/none")
    get_settings.cache_clear()
    get_engine.cache_clear()
    from app.main import app

    yield TestClient(app)
    get_settings.cache_clear()
    get_engine.cache_clear()


def test_health_reports_degraded_when_database_is_down(client_without_db: TestClient) -> None:
    resp = client_without_db.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "down"


def test_unknown_route_uses_standard_error_format(client_without_db: TestClient) -> None:
    resp = client_without_db.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_openapi_docs_available(client_without_db: TestClient) -> None:
    assert client_without_db.get("/docs").status_code == 200
    assert "/api/v1/health" in client_without_db.get("/openapi.json").json()["paths"]
