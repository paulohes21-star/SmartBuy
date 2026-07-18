from datetime import date, timedelta
from pathlib import Path

from app import database
from app.purchasing_engine import calculate_recommendations


def _prepare(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sprint5.db")
    database.init_db()

    with database.connect() as conn:
        company_id = conn.execute(
            "SELECT id FROM companies ORDER BY id LIMIT 1"
        ).fetchone()["id"]
        unit_id = conn.execute(
            "SELECT id FROM units WHERE code='UN'"
        ).fetchone()["id"]
        product_id = conn.execute(
            """
            INSERT INTO products(internal_code, description, unit_id)
            VALUES('DROP001', 'Cabo Drop 1FO', ?)
            """,
            (unit_id,),
        ).lastrowid
        conn.execute(
            """
            INSERT INTO product_company_settings(
                product_id, company_id, current_stock, reserved_stock,
                average_cost, lead_time_days, analysis_months,
                safety_days, coverage_days, on_order_stock
            ) VALUES(?, ?, 20, 5, 100, 10, 1, 5, 30, 0)
            """,
            (product_id, company_id),
        )
        movement_date = (date.today() - timedelta(days=10)).isoformat()
        conn.execute(
            """
            INSERT INTO stock_movements(
                product_id, company_id, movement_type,
                quantity, movement_date
            ) VALUES(?, ?, 'CONSUMPTION', 60, ?)
            """,
            (product_id, company_id, movement_date),
        )
        conn.commit()
    return product_id, company_id


def test_reorder_calculation(tmp_path, monkeypatch):
    _, company_id = _prepare(tmp_path, monkeypatch)
    items = calculate_recommendations(company_id=company_id)
    assert len(items) == 1
    item = items[0]
    assert item.average_daily_consumption == 2
    assert item.reorder_point == 30
    assert item.available_stock == 15
    assert item.suggested_quantity == 55


def test_abc_assignment(tmp_path, monkeypatch):
    _, company_id = _prepare(tmp_path, monkeypatch)
    items = calculate_recommendations(company_id=company_id)
    assert items[0].abc_class in {"A", "B", "C"}


def test_schema_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "idempotent.db")
    database.init_db()
    database.init_db()
    with database.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "stock_movements" in tables
    assert "product_cost_history" in tables
    assert "supplier_quotes" in tables
    assert "inventory_snapshots" in tables
