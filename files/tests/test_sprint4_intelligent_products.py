from pathlib import Path

from fastapi.testclient import TestClient

from app import database
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


def test_schema_and_intelligent_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sprint4.db")
    database.init_db()

    with database.connect() as conn:
        unit_id = conn.execute(
            "SELECT id FROM units WHERE code='UN'"
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO products(
                internal_code, description, unit_id,
                manufacturer_reference
            ) VALUES('DROP001', 'Cabo Drop 1FO', ?, 'REF-WEC-01')
            """,
            (unit_id,),
        )
        conn.commit()

    with TestClient(app) as client:
        login(client)
        result = client.get(
            "/products/intelligent/search",
            params={"term": "REF-WEC"},
        )
        assert result.status_code == 200
        assert result.json()["results"][0]["internal_code"] == "DROP001"


def test_duplicate_check(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "duplicate.db")
    database.init_db()

    with database.connect() as conn:
        unit_id = conn.execute(
            "SELECT id FROM units WHERE code='UN'"
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO products(
                internal_code, description, unit_id, barcode
            ) VALUES('AX2S', 'Roteador AX2S', ?, '789000000001')
            """,
            (unit_id,),
        )
        conn.commit()

    with TestClient(app) as client:
        login(client)
        result = client.get(
            "/products/intelligent/duplicates",
            params={"barcode": "789000000001"},
        )
        assert result.status_code == 200
        assert result.json()["duplicate"] is True


def test_external_code_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "external.db")
    database.init_db()

    with database.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "product_external_codes" in tables
    assert "product_import_batches" in tables
    assert "product_import_rows" in tables
