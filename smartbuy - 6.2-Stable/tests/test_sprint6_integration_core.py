import csv
import json
from pathlib import Path

from app import database
from app.integration.connectors import CSVConnector
from app.integration.mapper import normalize_record, validate_mapping
from app.integration.sync_engine import execute_sync, promote_run


def _init(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sprint6.db")
    database.init_db()


def test_csv_connector_reads_records(tmp_path):
    path = tmp_path / "inventory.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["COD_PRODUTO", "COD_EMPRESA", "ESTOQUE"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerow(
            {
                "COD_PRODUTO": "DROP001",
                "COD_EMPRESA": "1",
                "ESTOQUE": "100",
            }
        )
    connector = CSVConnector()
    test = connector.test_connection(
        {"path": str(path), "delimiter": ";"},
        {},
    )
    assert test.ok
    result = connector.read(
        {"path": str(path), "delimiter": ";"},
        {},
    )
    assert result.rows[0]["COD_PRODUTO"] == "DROP001"


def test_mapping_and_normalization():
    mapping = {
        "product_code": "COD_PRODUTO",
        "company_code": "EMPRESA",
        "current_stock": "SALDO",
    }
    assert validate_mapping("INVENTORY", mapping) == []
    record = normalize_record(
        "INVENTORY",
        {"COD_PRODUTO": " drop001 ", "EMPRESA": "1", "SALDO": "25"},
        mapping,
    )
    assert record["product_code"] == "DROP001"
    assert record["current_stock"] == 25.0


def test_sync_staging_and_promotion(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    csv_path = tmp_path / "products.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["CODIGO", "DESCRICAO", "UNIDADE"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerow(
            {
                "CODIGO": "TESTE001",
                "DESCRICAO": "Produto integrado",
                "UNIDADE": "UN",
            }
        )

    with database.connect() as conn:
        user_id = conn.execute(
            "SELECT id FROM users ORDER BY id LIMIT 1"
        ).fetchone()["id"]
        source_id = conn.execute(
            """
            INSERT INTO integration_sources(
                name, connector_type, entity_type,
                config_json, created_by
            ) VALUES('CSV Produtos', 'CSV', 'PRODUCT', ?, ?)
            """,
            (
                json.dumps(
                    {"path": str(csv_path), "delimiter": ";"}
                ),
                user_id,
            ),
        ).lastrowid
        mapping_id = conn.execute(
            """
            INSERT INTO integration_mappings(
                source_id, name, entity_type, mapping_json, created_by
            ) VALUES(?, 'Principal', 'PRODUCT', ?, ?)
            """,
            (
                source_id,
                json.dumps(
                    {
                        "internal_code": "CODIGO",
                        "description": "DESCRICAO",
                        "unit_code": "UNIDADE",
                    }
                ),
                user_id,
            ),
        ).lastrowid
        conn.commit()

    run_id = execute_sync(
        source_id=source_id,
        mapping_id=mapping_id,
        user_id=user_id,
    )
    result = promote_run(run_id, user_id)
    assert result["promoted"] == 1

    with database.connect() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE internal_code='TESTE001'"
        ).fetchone()
        assert product is not None


def test_schema_idempotent(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    database.init_db()
    with database.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "integration_sources" in tables
    assert "integration_staging_records" in tables
    assert "integration_quality_issues" in tables
