from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.integration.cache import get_cache, purge_expired, set_cache
from app.integration.contracts import ConnectorCapability
from app.integration.registry import (
    descriptors,
    get_connector,
    validate_version,
)
from app.main import app


def login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": "admin@smartbuy.local",
            "password": "SmartBuy@123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_semver_and_registry():
    validate_version("1.0.0")
    connector = get_connector("CSV")
    assert connector.connector_type == "CSV"
    assert connector.version == "1.0.0"


def test_eip_schema_and_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "eip.db")
    database.init_db()

    set_cache(
        namespace="test",
        cache_key="one",
        payload={"ok": True},
        ttl_seconds=60,
    )
    assert get_cache(namespace="test", cache_key="one") == {"ok": True}
    assert purge_expired() >= 0

    with database.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "integration_health_snapshots" in tables
    assert "integration_cache_entries" in tables
    assert "integration_events" in tables


def test_connector_api(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "api.db")
    database.init_db()

    with TestClient(app) as client:
        login(client)
        response = client.get("/integration-core/api/connectors")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"]
        csv_item = next(
            item for item in payload["items"]
            if item["connector_type"] == "CSV"
        )
        assert "preview" in csv_item["capabilities"]


def test_existing_routes_are_preserved(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "routes.db")
    database.init_db()

    with TestClient(app) as client:
        login(client)
        assert client.get("/integration-core").status_code == 200
        assert client.get("/purchasing-intelligence").status_code == 200
