from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

from app import database
from app.integration.connectors import connector_registry, load_secrets
from app.integration.mapper import (
    normalize_record,
    record_hash,
    source_key,
    validate_mapping,
)
from app.integration.quality import evaluate


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def execute_sync(
    *,
    source_id: int,
    mapping_id: int,
    user_id: int,
    mode: str = "INCREMENTAL",
    limit: int = 10000,
) -> int:
    started = time.perf_counter()
    with database.connect() as conn:
        source = conn.execute(
            "SELECT * FROM integration_sources WHERE id=? AND active=1",
            (source_id,),
        ).fetchone()
        mapping_row = conn.execute(
            """
            SELECT * FROM integration_mappings
            WHERE id=? AND source_id=? AND active=1
            """,
            (mapping_id, source_id),
        ).fetchone()
        if not source or not mapping_row:
            raise ValueError("Fonte ou mapeamento inexistente/inativo")

        config = json.loads(source["config_json"])
        mapping = json.loads(mapping_row["mapping_json"])
        errors = validate_mapping(source["entity_type"], mapping)
        if errors:
            raise ValueError("; ".join(errors))

        cursor_row = conn.execute(
            """
            SELECT cursor_value FROM integration_sync_state
            WHERE source_id=? AND entity_type=?
            """,
            (source_id, source["entity_type"]),
        ).fetchone()
        cursor_value = (
            cursor_row["cursor_value"]
            if cursor_row and mode.upper() == "INCREMENTAL"
            else None
        )

        run_id = conn.execute(
            """
            INSERT INTO integration_sync_runs(
                source_id, mapping_id, mode, status, created_by
            ) VALUES(?, ?, ?, 'RUNNING', ?)
            """,
            (source_id, mapping_id, mode.upper(), user_id),
        ).lastrowid
        conn.commit()

    try:
        connector = connector_registry[source["connector_type"]]
        result = connector.read(
            config,
            load_secrets(source["secret_env_prefix"]),
            cursor=cursor_value,
            limit=limit,
        )

        counters = {
            "read": len(result.rows),
            "staged": 0,
            "valid": 0,
            "invalid": 0,
            "errors": 0,
            "warnings": len(result.warnings),
        }

        with database.connect() as conn:
            for source_record in result.rows:
                canonical = normalize_record(
                    source["entity_type"],
                    source_record,
                    mapping,
                )
                issues = evaluate(source["entity_type"], canonical)
                quality_status = (
                    "INVALID"
                    if any(i["severity"] == "ERROR" for i in issues)
                    else "VALID"
                )
                digest = record_hash(
                    source_id,
                    source["entity_type"],
                    source_record,
                )
                key = source_key(source["entity_type"], canonical)

                existing = conn.execute(
                    """
                    SELECT id FROM integration_staging_records
                    WHERE source_id=? AND entity_type=? AND source_hash=?
                    """,
                    (source_id, source["entity_type"], digest),
                ).fetchone()
                if existing:
                    continue

                staging_id = conn.execute(
                    """
                    INSERT INTO integration_staging_records(
                        run_id, source_id, entity_type, source_key,
                        source_hash, source_payload_json,
                        canonical_payload_json, quality_status
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        source_id,
                        source["entity_type"],
                        key,
                        digest,
                        _json(source_record),
                        _json(canonical),
                        quality_status,
                    ),
                ).lastrowid
                counters["staged"] += 1
                counters["valid" if quality_status == "VALID" else "invalid"] += 1

                for issue in issues:
                    conn.execute(
                        """
                        INSERT INTO integration_quality_issues(
                            staging_record_id, run_id, severity,
                            rule_code, field_name, message
                        ) VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (
                            staging_id,
                            run_id,
                            issue["severity"],
                            issue["rule_code"],
                            issue["field_name"],
                            issue["message"],
                        ),
                    )
                    counters[
                        "errors"
                        if issue["severity"] == "ERROR"
                        else "warnings"
                    ] += 1

            duration = int((time.perf_counter() - started) * 1000)
            conn.execute(
                """
                UPDATE integration_sync_runs
                SET status='STAGED',
                    finished_at=CURRENT_TIMESTAMP,
                    duration_ms=?,
                    rows_read=?,
                    rows_staged=?,
                    rows_valid=?,
                    rows_invalid=?,
                    errors_count=?,
                    warnings_count=?,
                    cursor_value=?
                WHERE id=?
                """,
                (
                    duration,
                    counters["read"],
                    counters["staged"],
                    counters["valid"],
                    counters["invalid"],
                    counters["errors"],
                    counters["warnings"],
                    result.next_cursor,
                    run_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO integration_sync_state(
                    source_id, entity_type, cursor_value,
                    last_successful_run_id, updated_at
                ) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_id, entity_type) DO UPDATE SET
                    cursor_value=excluded.cursor_value,
                    last_successful_run_id=excluded.last_successful_run_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    source_id,
                    source["entity_type"],
                    result.next_cursor,
                    run_id,
                ),
            )
            conn.commit()
        return run_id
    except Exception as exc:
        duration = int((time.perf_counter() - started) * 1000)
        with database.connect() as conn:
            conn.execute(
                """
                UPDATE integration_sync_runs
                SET status='FAILED',
                    finished_at=CURRENT_TIMESTAMP,
                    duration_ms=?,
                    error_message=?,
                    errors_count=errors_count+1
                WHERE id=?
                """,
                (duration, str(exc), run_id),
            )
            conn.commit()
        raise


def _product_id(conn, product_code: str) -> int | None:
    row = conn.execute(
        """
        SELECT id FROM products
        WHERE internal_code=? COLLATE NOCASE
           OR erp_code=? COLLATE NOCASE
        """,
        (product_code, product_code),
    ).fetchone()
    return row["id"] if row else None


def _company_id(conn, company_code: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM companies WHERE code=? COLLATE NOCASE",
        (company_code,),
    ).fetchone()
    return row["id"] if row else None


def promote_run(run_id: int, user_id: int) -> dict[str, int]:
    promoted = 0
    skipped = 0
    with database.connect() as conn:
        run = conn.execute(
            "SELECT * FROM integration_sync_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if not run or run["status"] not in {"STAGED", "PARTIAL"}:
            raise ValueError("Execução não está disponível para promoção")

        records = conn.execute(
            """
            SELECT * FROM integration_staging_records
            WHERE run_id=?
              AND quality_status='VALID'
              AND promotion_status='PENDING'
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()

        try:
            conn.execute("BEGIN")
            for record in records:
                payload = json.loads(record["canonical_payload_json"])
                entity = record["entity_type"]
                entity_id = None

                if entity == "PRODUCT":
                    unit = conn.execute(
                        "SELECT id FROM units WHERE code=? COLLATE NOCASE",
                        (payload["unit_code"],),
                    ).fetchone()
                    if not unit:
                        skipped += 1
                        continue
                    existing = conn.execute(
                        """
                        SELECT id FROM products
                        WHERE internal_code=? COLLATE NOCASE
                        """,
                        (payload["internal_code"],),
                    ).fetchone()
                    if existing:
                        entity_id = existing["id"]
                        conn.execute(
                            """
                            UPDATE products
                            SET description=?, unit_id=?,
                                ncm=COALESCE(?, ncm),
                                erp_code=COALESCE(?, erp_code),
                                updated_at=CURRENT_TIMESTAMP
                            WHERE id=?
                            """,
                            (
                                payload["description"],
                                unit["id"],
                                payload.get("ncm"),
                                payload.get("erp_code"),
                                entity_id,
                            ),
                        )
                    else:
                        entity_id = conn.execute(
                            """
                            INSERT INTO products(
                                internal_code, description, unit_id,
                                ncm, erp_code, active
                            ) VALUES(?, ?, ?, ?, ?, 1)
                            """,
                            (
                                payload["internal_code"],
                                payload["description"],
                                unit["id"],
                                payload.get("ncm"),
                                payload.get("erp_code"),
                            ),
                        ).lastrowid

                elif entity in {"INVENTORY", "OPEN_ORDER"}:
                    product_id = _product_id(conn, payload["product_code"])
                    company_id = _company_id(conn, payload["company_code"])
                    if not product_id or not company_id:
                        skipped += 1
                        continue
                    values = {
                        "current_stock": float(payload.get("current_stock") or 0),
                        "reserved_stock": float(payload.get("reserved_stock") or 0),
                        "on_order_stock": float(payload.get("on_order_stock") or 0),
                    }
                    if entity == "OPEN_ORDER":
                        values["on_order_stock"] = float(
                            payload.get("quantity") or 0
                        )
                    conn.execute(
                        """
                        INSERT INTO product_company_settings(
                            product_id, company_id, current_stock,
                            reserved_stock, on_order_stock, updated_at
                        ) VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(product_id, company_id) DO UPDATE SET
                            current_stock=CASE
                                WHEN ?='INVENTORY'
                                THEN excluded.current_stock
                                ELSE current_stock END,
                            reserved_stock=CASE
                                WHEN ?='INVENTORY'
                                THEN excluded.reserved_stock
                                ELSE reserved_stock END,
                            on_order_stock=excluded.on_order_stock,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (
                            product_id,
                            company_id,
                            values["current_stock"],
                            values["reserved_stock"],
                            values["on_order_stock"],
                            entity,
                            entity,
                        ),
                    )
                    entity_id = product_id

                elif entity == "CONSUMPTION":
                    product_id = _product_id(conn, payload["product_code"])
                    company_id = _company_id(conn, payload["company_code"])
                    if not product_id or not company_id:
                        skipped += 1
                        continue
                    duplicate = conn.execute(
                        """
                        SELECT id FROM stock_movements
                        WHERE product_id=? AND company_id=?
                          AND movement_type='CONSUMPTION'
                          AND movement_date=?
                          AND COALESCE(reference_number,'')=?
                          AND quantity=?
                        """,
                        (
                            product_id,
                            company_id,
                            str(payload["movement_date"])[:10],
                            str(payload.get("reference_number") or ""),
                            float(payload["quantity"]),
                        ),
                    ).fetchone()
                    if duplicate:
                        entity_id = duplicate["id"]
                    else:
                        entity_id = conn.execute(
                            """
                            INSERT INTO stock_movements(
                                product_id, company_id, movement_type,
                                quantity, movement_date, reference_number,
                                created_by
                            ) VALUES(?, ?, 'CONSUMPTION', ?, ?, ?, ?)
                            """,
                            (
                                product_id,
                                company_id,
                                float(payload["quantity"]),
                                str(payload["movement_date"])[:10],
                                payload.get("reference_number"),
                                user_id,
                            ),
                        ).lastrowid

                elif entity == "PURCHASE":
                    product_id = _product_id(conn, payload["product_code"])
                    company_id = _company_id(conn, payload["company_code"])
                    if not product_id or not company_id:
                        skipped += 1
                        continue
                    entity_id = conn.execute(
                        """
                        INSERT INTO product_cost_history(
                            product_id, company_id, unit_cost,
                            quantity, total_cost, cost_date,
                            reference_number, created_by
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            product_id,
                            company_id,
                            float(payload["unit_cost"]),
                            float(payload.get("quantity") or 0),
                            float(payload["unit_cost"])
                            * float(payload.get("quantity") or 0),
                            str(payload["purchase_date"])[:10],
                            payload.get("reference_number"),
                            user_id,
                        ),
                    ).lastrowid

                elif entity == "SUPPLIER":
                    existing = conn.execute(
                        """
                        SELECT id FROM suppliers
                        WHERE code=? COLLATE NOCASE
                        """,
                        (payload["supplier_code"],),
                    ).fetchone()
                    if existing:
                        entity_id = existing["id"]
                        conn.execute(
                            """
                            UPDATE suppliers
                            SET legal_name=?,
                                trade_name=COALESCE(?, trade_name),
                                tax_id=COALESCE(?, tax_id),
                                updated_at=CURRENT_TIMESTAMP
                            WHERE id=?
                            """,
                            (
                                payload["legal_name"],
                                payload.get("trade_name"),
                                payload.get("tax_id"),
                                entity_id,
                            ),
                        )
                    else:
                        entity_id = conn.execute(
                            """
                            INSERT INTO suppliers(
                                code, legal_name, trade_name, tax_id, active
                            ) VALUES(?, ?, ?, ?, 1)
                            """,
                            (
                                payload["supplier_code"],
                                payload["legal_name"],
                                payload.get("trade_name"),
                                payload.get("tax_id"),
                            ),
                        ).lastrowid

                if entity_id is None:
                    skipped += 1
                    continue

                conn.execute(
                    """
                    UPDATE integration_staging_records
                    SET promotion_status='PROMOTED',
                        promoted_entity_id=?,
                        promoted_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (entity_id, record["id"]),
                )
                promoted += 1

            final_status = "PROMOTED" if skipped == 0 else "PARTIAL"
            conn.execute(
                """
                UPDATE integration_sync_runs
                SET status=?, rows_promoted=?
                WHERE id=?
                """,
                (final_status, promoted, run_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"promoted": promoted, "skipped": skipped}
