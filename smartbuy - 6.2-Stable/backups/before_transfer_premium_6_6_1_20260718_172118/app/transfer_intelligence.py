from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app import database

router = APIRouter(
    prefix="/transfer-intelligence",
    tags=["transfer-intelligence"],
)


@dataclass(frozen=True)
class TransferRecommendation:
    product_id: int
    internal_code: str
    description: str
    origin_company_id: int
    origin_company: str
    destination_company_id: int
    destination_company: str
    origin_stock: float
    destination_stock: float
    origin_coverage_days: float | None
    destination_coverage_days: float | None
    quantity: float
    unit_cost: float
    avoided_purchase: float
    score: int
    priority: str
    explanation: str


def _main():
    import app.main as main
    return main


def _money(value: float) -> str:
    value = float(value or 0)
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _qty(value: float) -> str:
    value = float(value or 0)
    if value.is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _column_names(conn, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _daily_consumption(conn, product_id: int, company_id: int, months: int) -> float:
    if not _table_exists(conn, "stock_movements"):
        return 0.0
    cols = _column_names(conn, "stock_movements")
    required = {"product_id", "company_id", "movement_type", "quantity", "movement_date"}
    if not required.issubset(cols):
        return 0.0
    row = conn.execute(
        """
        SELECT COALESCE(SUM(ABS(quantity)), 0) total
        FROM stock_movements
        WHERE product_id=?
          AND company_id=?
          AND movement_type IN ('OUT', 'CONSUMPTION', 'SALE')
          AND date(movement_date) >= date('now', ?)
        """,
        (product_id, company_id, f"-{max(months, 1)} months"),
    ).fetchone()
    days = max(months, 1) * 30
    return float(row["total"] or 0) / days


def _inventory_rows(conn, company_id: int | None = None) -> list[Any]:
    required_tables = {"products", "companies", "product_company_settings"}
    if not all(_table_exists(conn, table) for table in required_tables):
        return []
    pcs_cols = _column_names(conn, "product_company_settings")
    required_cols = {"product_id", "company_id", "current_stock"}
    if not required_cols.issubset(pcs_cols):
        return []

    avg_cost = "COALESCE(pcs.average_cost, pcs.last_cost, 0)" if "average_cost" in pcs_cols and "last_cost" in pcs_cols else (
        "COALESCE(pcs.average_cost, 0)" if "average_cost" in pcs_cols else (
            "COALESCE(pcs.last_cost, 0)" if "last_cost" in pcs_cols else "0"
        )
    )
    reserved = "COALESCE(pcs.reserved_stock, 0)" if "reserved_stock" in pcs_cols else "0"
    safety = "COALESCE(pcs.minimum_stock, 0)" if "minimum_stock" in pcs_cols else "0"
    max_stock = "COALESCE(pcs.maximum_stock, 0)" if "maximum_stock" in pcs_cols else "0"
    active_filter = "AND p.active=1" if "active" in _column_names(conn, "products") else ""
    company_active = "AND c.active=1" if "active" in _column_names(conn, "companies") else ""
    params: list[Any] = []
    company_filter = ""
    if company_id:
        company_filter = "AND c.id=?"
        params.append(company_id)

    return conn.execute(
        f"""
        SELECT
            p.id product_id,
            p.internal_code,
            p.description,
            c.id company_id,
            COALESCE(c.trade_name, c.legal_name, c.code) company_name,
            c.code company_code,
            MAX(COALESCE(pcs.current_stock, 0) - {reserved}, 0) available_stock,
            {safety} safety_stock,
            {max_stock} maximum_stock,
            {avg_cost} unit_cost
        FROM product_company_settings pcs
        JOIN products p ON p.id=pcs.product_id
        JOIN companies c ON c.id=pcs.company_id
        WHERE 1=1 {active_filter} {company_active} {company_filter}
        ORDER BY p.internal_code, c.code
        """,
        params,
    ).fetchall()


def calculate_transfers(
    company_id: int | None = None,
    analysis_months: int = 3,
    critical_days: int = 30,
    target_days: int = 90,
    excess_days: int = 180,
) -> tuple[list[TransferRecommendation], dict[str, Any]]:
    with database.connect() as conn:
        rows = _inventory_rows(conn, company_id=None)
        companies = conn.execute(
            "SELECT id, code, legal_name, trade_name FROM companies WHERE active=1 ORDER BY code"
        ).fetchall() if _table_exists(conn, "companies") else []

        enriched: list[dict[str, Any]] = []
        for row in rows:
            consumption = _daily_consumption(
                conn, int(row["product_id"]), int(row["company_id"]), analysis_months
            )
            stock = float(row["available_stock"] or 0)
            coverage = stock / consumption if consumption > 0 else None
            enriched.append({
                **dict(row),
                "daily_consumption": consumption,
                "coverage_days": coverage,
            })

    by_product: dict[int, list[dict[str, Any]]] = {}
    for row in enriched:
        by_product.setdefault(int(row["product_id"]), []).append(row)

    recommendations: list[TransferRecommendation] = []
    for product_rows in by_product.values():
        destinations = []
        origins = []
        for row in product_rows:
            consumption = float(row["daily_consumption"] or 0)
            stock = float(row["available_stock"] or 0)
            safety = max(float(row["safety_stock"] or 0), consumption * critical_days)
            coverage = row["coverage_days"]

            target_stock = max(safety, consumption * target_days)
            need = max(target_stock - stock, 0)
            if consumption > 0 and (coverage is None or coverage < critical_days) and need > 0:
                destinations.append({**row, "need": need})

            if consumption > 0:
                keep_stock = max(safety, consumption * excess_days)
                excess = max(stock - keep_stock, 0)
            else:
                # Sem consumo: preserva o estoque mínimo e considera o restante como excedente.
                keep_stock = max(float(row["safety_stock"] or 0), 0)
                excess = max(stock - keep_stock, 0)

            if excess > 0:
                origins.append({**row, "excess": excess})

        destinations.sort(key=lambda x: (
            x["coverage_days"] is None,
            x["coverage_days"] if x["coverage_days"] is not None else 10**9,
            -x["need"],
        ))
        origins.sort(key=lambda x: (-x["excess"], -(x["coverage_days"] or 10**9)))

        for destination in destinations:
            remaining = float(destination["need"])
            for origin in origins:
                if remaining <= 0:
                    break
                if origin["company_id"] == destination["company_id"]:
                    continue
                available = float(origin["excess"])
                if available <= 0:
                    continue
                quantity = min(remaining, available)
                if quantity <= 0:
                    continue

                unit_cost = max(
                    float(destination["unit_cost"] or 0),
                    float(origin["unit_cost"] or 0),
                )
                avoided = quantity * unit_cost
                destination_cover = destination["coverage_days"]
                origin_cover = origin["coverage_days"]
                urgency_points = 35 if destination_cover is not None and destination_cover <= 15 else 25
                value_points = min(int(avoided / 5000) * 4, 25)
                balance_points = 25
                data_points = 15 if destination["daily_consumption"] > 0 else 5
                score = min(100, urgency_points + value_points + balance_points + data_points)
                priority = "Crítica" if destination_cover is not None and destination_cover <= 15 else "Alta"

                explanation = (
                    f"{origin['company_name']} possui {_qty(origin['available_stock'])} UN disponíveis"
                    + (
                        f" e cobertura estimada de {origin_cover:.0f} dias"
                        if origin_cover is not None else " sem consumo recente"
                    )
                    + f". {destination['company_name']} possui {_qty(destination['available_stock'])} UN"
                    + (
                        f" e cobertura de {destination_cover:.0f} dias"
                        if destination_cover is not None else ""
                    )
                    + f". Transferir {_qty(quantity)} UN preserva a segurança da origem e pode evitar {_money(avoided)} em compra externa."
                )

                recommendations.append(TransferRecommendation(
                    product_id=int(destination["product_id"]),
                    internal_code=str(destination["internal_code"]),
                    description=str(destination["description"]),
                    origin_company_id=int(origin["company_id"]),
                    origin_company=str(origin["company_name"]),
                    destination_company_id=int(destination["company_id"]),
                    destination_company=str(destination["company_name"]),
                    origin_stock=float(origin["available_stock"]),
                    destination_stock=float(destination["available_stock"]),
                    origin_coverage_days=origin_cover,
                    destination_coverage_days=destination_cover,
                    quantity=round(quantity, 2),
                    unit_cost=round(unit_cost, 4),
                    avoided_purchase=round(avoided, 2),
                    score=score,
                    priority=priority,
                    explanation=explanation,
                ))
                origin["excess"] = available - quantity
                remaining -= quantity

    if company_id:
        recommendations = [
            item for item in recommendations
            if item.origin_company_id == company_id or item.destination_company_id == company_id
        ]

    recommendations.sort(key=lambda item: (-item.avoided_purchase, -item.score, item.internal_code))
    total_avoided = sum(item.avoided_purchase for item in recommendations)
    total_units = sum(item.quantity for item in recommendations)
    critical_count = sum(1 for item in recommendations if item.priority == "Crítica")
    products = len({item.product_id for item in recommendations})
    origins = len({item.origin_company_id for item in recommendations})
    destinations = len({item.destination_company_id for item in recommendations})

    metrics = {
        "recommendations": len(recommendations),
        "products": products,
        "total_units": total_units,
        "total_avoided": total_avoided,
        "critical_count": critical_count,
        "origins": origins,
        "destinations": destinations,
        "money_total_avoided": _money(total_avoided),
        "qty_total_units": _qty(total_units),
    }
    return recommendations, {"metrics": metrics, "companies": companies}


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    company_id: int | None = Query(None),
    analysis_months: int = Query(3, ge=1, le=24),
    critical_days: int = Query(30, ge=1, le=365),
    target_days: int = Query(90, ge=1, le=730),
    excess_days: int = Query(180, ge=1, le=1460),
):
    user = _main().require(request, "purchasing_intelligence.read")
    if not user:
        return _main().login_redirect()

    recommendations, context = calculate_transfers(
        company_id=company_id,
        analysis_months=analysis_months,
        critical_days=critical_days,
        target_days=max(target_days, critical_days),
        excess_days=max(excess_days, target_days),
    )
    return _main().templates.TemplateResponse(
        "transfer_intelligence.html",
        _main().base_context(
            request,
            user,
            recommendations=recommendations,
            selected_company_id=company_id,
            selected_analysis_months=analysis_months,
            selected_critical_days=critical_days,
            selected_target_days=target_days,
            selected_excess_days=excess_days,
            money=_money,
            qty=_qty,
            **context,
        ),
    )


@router.get("/health")
def health(request: Request):
    user = _main().require(request, "purchasing_intelligence.read")
    if not user:
        return {"status": "unauthorized"}
    with database.connect() as conn:
        required = {
            "products": _table_exists(conn, "products"),
            "companies": _table_exists(conn, "companies"),
            "product_company_settings": _table_exists(conn, "product_company_settings"),
            "stock_movements": _table_exists(conn, "stock_movements"),
        }
    return {
        "status": "ok" if all(required.values()) else "degraded",
        "tables": required,
    }
