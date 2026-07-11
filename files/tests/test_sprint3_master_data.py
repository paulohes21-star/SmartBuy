from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": "admin@smartbuy.local",
            "password": "SmartBuy@123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_master_data_page_and_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sprint3.db")
    database.init_db()

    with TestClient(app) as client:
        _login(client)

        page = client.get("/master-data")
        assert page.status_code == 200
        assert "Cadastros mestres" in page.text

        created = client.post(
            "/master-data/manufacturers",
            data={"code": "WEC", "name": "WEC Cabos"},
            follow_redirects=True,
        )
        assert created.status_code == 200
        assert "WEC Cabos" in created.text


def test_warehouse_and_location(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "warehouse.db")
    database.init_db()

    with database.connect() as conn:
        company_id = conn.execute(
            "SELECT id FROM companies ORDER BY id LIMIT 1"
        ).fetchone()["id"]

    with TestClient(app) as client:
        _login(client)

        warehouse_response = client.post(
            "/master-data/warehouses",
            data={
                "company_id": company_id,
                "code": "CENTRAL",
                "name": "Depósito Central",
            },
            follow_redirects=True,
        )
        assert warehouse_response.status_code == 200
        assert "Depósito Central" in warehouse_response.text

        with database.connect() as conn:
            warehouse_id = conn.execute(
                "SELECT id FROM warehouses WHERE code = 'CENTRAL'"
            ).fetchone()["id"]

        location_response = client.post(
            "/master-data/locations",
            data={
                "warehouse_id": warehouse_id,
                "code": "A-01-01",
                "description": "Corredor A",
                "aisle": "A",
                "rack": "01",
                "level": "01",
                "bin": "01",
            },
            follow_redirects=True,
        )
        assert location_response.status_code == 200
        assert "A-01-01" in location_response.text
