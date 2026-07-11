from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import ceil
from typing import Any

from app import database


@dataclass(frozen=True)
class PurchasingRecommendation:
    product_id: int
    company_id: int
    internal_code: str
    description: str
    current_stock: float
    reserved_stock: float
    on_order_stock: float
    available_stock: float
    average_daily_consumption: float
    analysis_days: int
    lead_time_days: int
    safety_days: int
    coverage_days: int
    safety_stock: float
    reorder_point: float
    target_stock: float
    suggested_quantity: float
    days_of_cover: float | None
    rupture_date: str | None
    annual_consumption_quantity: float
    annual_consumption_value: float
    average_cost: float
    turnover: float
    abc_class: str = "C"
    preferred_supplier_id: int | None = None
    preferred_supplier_name: str | None = None
    best_quote_supplier_id: int | None = None
    best_quote_supplier_name: str | None = None
    best_quote_landed_unit_cost: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _date_days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _safe_float(value: Any) -> float:
    return float(value or 0)


def _best_quote(conn, company_id: int, product_id: int) -> dict | None:
    rows = conn.execute(
        """
        SELECT
            q.supplier_id,
            s.code supplier_code,
            COALESCE(s.trade_name, s.legal_name) supplier_name,
            q.unit_price,
            q.quantity,
            q.freight_total,
            q.taxes_total,
            q.discount_total,
            q.lead_time_days,
            ps.preferred,
            ps.supplier_score
        FROM supplier_quotes q
        JOIN suppliers s ON s.id=q.supplier_id
        LEFT JOIN product_suppliers ps
          ON ps.product_id=q.product_id
         AND ps.supplier_id=q.supplier_id
        WHERE q.company_id=?
          AND q.product_id=?
          AND q.status='VALID'
          AND (q.valid_until IS NULL OR q.valid_until >= date('now'))
        ORDER BY q.created_at DESC
        """,
        (company_id, product_id),
    ).fetchall()

    ranked = []
    for row in rows:
        quantity = max(_safe_float(row["quantity"]), 1)
        landed = (
            _safe_float(row["unit_price"])
            + (
                _safe_float(row["freight_total"])
                + _safe_float(row["taxes_total"])
                - _safe_float(row["discount_total"])
            ) / quantity
        )
        # Custo final é dominante. O prazo e o score apenas desempatem.
        score = (
            landed
            + max(int(row["lead_time_days"] or 0), 0) * 0.001
            - _safe_float(row["supplier_score"]) * 0.0001
            - (0.0001 if row["preferred"] else 0)
        )
        ranked.append((score, landed, row))

    if not ranked:
        return None

    _, landed, row = min(ranked, key=lambda item: item[0])
    return {
        "supplier_id": row["supplier_id"],
        "supplier_name": row["supplier_name"],
        "landed_unit_cost": round(landed, 4),
    }


def calculate_recommendations(
    *,
    company_id: int | None = None,
    analysis_months_override: int | None = None,
) -> list[PurchasingRecommendation]:
    with database.connect() as conn:
        filters = ["p.active=1", "c.active=1"]
        params: list[Any] = []
        if company_id:
            filters.append("pcs.company_id=?")
            params.append(company_id)

        settings = conn.execute(
            f"""
            SELECT
                pcs.*,
                p.internal_code,
                p.description,
                c.code company_code,
                COALESCE(c.trade_name, c.legal_name) company_name
            FROM product_company_settings pcs
            JOIN products p ON p.id=pcs.product_id
            JOIN companies c ON c.id=pcs.company_id
            WHERE {' AND '.join(filters)}
            ORDER BY c.code, p.internal_code
            """,
            params,
        ).fetchall()

        recommendations: list[PurchasingRecommendation] = []
        for row in settings:
            months = max(
                int(
                    analysis_months_override
                    or row["analysis_months"]
                    or 3
                ),
                1,
            )
            analysis_days = max(months * 30, 1)
            start_date = _date_days_ago(analysis_days)

            consumption = conn.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) total
                FROM stock_movements
                WHERE product_id=?
                  AND company_id=?
                  AND movement_type IN ('OUT', 'CONSUMPTION', 'SALE')
                  AND movement_date>=?
                """,
                (row["product_id"], row["company_id"], start_date),
            ).fetchone()["total"]

            annual_start = _date_days_ago(365)
            annual_consumption = conn.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) total
                FROM stock_movements
                WHERE product_id=?
                  AND company_id=?
                  AND movement_type IN ('OUT', 'CONSUMPTION', 'SALE')
                  AND movement_date>=?
                """,
                (
                    row["product_id"],
                    row["company_id"],
                    annual_start,
                ),
            ).fetchone()["total"]

            average_daily = _safe_float(consumption) / analysis_days
            lead_time = max(int(row["lead_time_days"] or 0), 0)
            safety_days = max(int(row["safety_days"] or 0), 0)
            coverage_days = max(int(row["coverage_days"] or 0), 1)

            current = _safe_float(row["current_stock"])
            reserved = _safe_float(row["reserved_stock"])
            on_order = _safe_float(row["on_order_stock"])
            available = current - reserved + on_order

            safety_stock = average_daily * safety_days
            reorder_point = average_daily * lead_time + safety_stock
            target_stock = average_daily * coverage_days + safety_stock

            should_buy = available <= reorder_point
            suggested = (
                max(target_stock - available, 0) if should_buy else 0
            )
            suggested = float(ceil(suggested))

            days_cover = (
                max(available, 0) / average_daily
                if average_daily > 0
                else None
            )
            rupture_date = (
                (date.today() + timedelta(days=int(days_cover))).isoformat()
                if days_cover is not None
                else None
            )

            average_cost = _safe_float(row["average_cost"])
            if average_cost <= 0:
                cost_row = conn.execute(
                    """
                    SELECT unit_cost
                    FROM product_cost_history
                    WHERE product_id=? AND company_id=?
                    ORDER BY cost_date DESC, id DESC LIMIT 1
                    """,
                    (row["product_id"], row["company_id"]),
                ).fetchone()
                average_cost = (
                    _safe_float(cost_row["unit_cost"]) if cost_row else 0
                )

            average_inventory_row = conn.execute(
                """
                SELECT AVG(current_stock) average_inventory
                FROM inventory_snapshots
                WHERE product_id=? AND company_id=?
                  AND snapshot_date>=?
                """,
                (
                    row["product_id"],
                    row["company_id"],
                    annual_start,
                ),
            ).fetchone()
            average_inventory = _safe_float(
                average_inventory_row["average_inventory"]
            )
            if average_inventory <= 0:
                average_inventory = max(current, 0)

            turnover = (
                _safe_float(annual_consumption) / average_inventory
                if average_inventory > 0
                else 0
            )

            preferred = conn.execute(
                """
                SELECT ps.supplier_id,
                       COALESCE(s.trade_name, s.legal_name) supplier_name
                FROM product_suppliers ps
                JOIN suppliers s ON s.id=ps.supplier_id
                WHERE ps.product_id=? AND ps.active=1
                ORDER BY ps.preferred DESC, ps.supplier_score DESC,
                         ps.last_price ASC
                LIMIT 1
                """,
                (row["product_id"],),
            ).fetchone()

            quote = _best_quote(
                conn,
                row["company_id"],
                row["product_id"],
            )

            recommendations.append(
                PurchasingRecommendation(
                    product_id=row["product_id"],
                    company_id=row["company_id"],
                    internal_code=row["internal_code"],
                    description=row["description"],
                    current_stock=round(current, 2),
                    reserved_stock=round(reserved, 2),
                    on_order_stock=round(on_order, 2),
                    available_stock=round(available, 2),
                    average_daily_consumption=round(average_daily, 4),
                    analysis_days=analysis_days,
                    lead_time_days=lead_time,
                    safety_days=safety_days,
                    coverage_days=coverage_days,
                    safety_stock=round(safety_stock, 2),
                    reorder_point=round(reorder_point, 2),
                    target_stock=round(target_stock, 2),
                    suggested_quantity=round(suggested, 2),
                    days_of_cover=(
                        round(days_cover, 1)
                        if days_cover is not None
                        else None
                    ),
                    rupture_date=rupture_date,
                    annual_consumption_quantity=round(
                        _safe_float(annual_consumption), 2
                    ),
                    annual_consumption_value=round(
                        _safe_float(annual_consumption) * average_cost, 2
                    ),
                    average_cost=round(average_cost, 4),
                    turnover=round(turnover, 2),
                    preferred_supplier_id=(
                        preferred["supplier_id"] if preferred else None
                    ),
                    preferred_supplier_name=(
                        preferred["supplier_name"] if preferred else None
                    ),
                    best_quote_supplier_id=(
                        quote["supplier_id"] if quote else None
                    ),
                    best_quote_supplier_name=(
                        quote["supplier_name"] if quote else None
                    ),
                    best_quote_landed_unit_cost=(
                        quote["landed_unit_cost"] if quote else None
                    ),
                )
            )

    ranked = sorted(
        recommendations,
        key=lambda item: item.annual_consumption_value,
        reverse=True,
    )
    total_value = sum(item.annual_consumption_value for item in ranked)
    cumulative = 0.0
    class_by_key: dict[tuple[int, int], str] = {}

    for item in ranked:
        cumulative += item.annual_consumption_value
        percentage = cumulative / total_value if total_value > 0 else 1
        abc_class = "A" if percentage <= 0.80 else (
            "B" if percentage <= 0.95 else "C"
        )
        class_by_key[(item.product_id, item.company_id)] = abc_class

    result = []
    for item in recommendations:
        data = item.to_dict()
        data["abc_class"] = class_by_key.get(
            (item.product_id, item.company_id),
            "C",
        )
        result.append(PurchasingRecommendation(**data))
    return result
