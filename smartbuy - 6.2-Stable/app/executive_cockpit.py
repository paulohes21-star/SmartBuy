from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import database
from app.transfer_intelligence import calculate_transfers

router = APIRouter(prefix="/executive-cockpit", tags=["executive-cockpit"])


def _main():
    import app.main as main
    return main


def _money(value: float) -> str:
    value = float(value or 0)
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


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


def _company_health() -> list[dict]:
    with database.connect() as conn:
        if not all(_table_exists(conn, t) for t in ("companies", "products", "product_company_settings")):
            return []

        pcs_cols = _column_names(conn, "product_company_settings")
        reserved = "COALESCE(pcs.reserved_stock, 0)" if "reserved_stock" in pcs_cols else "0"
        average_cost = (
            "COALESCE(pcs.average_cost, pcs.last_cost, 0)"
            if {"average_cost", "last_cost"}.issubset(pcs_cols)
            else "COALESCE(pcs.average_cost, 0)"
            if "average_cost" in pcs_cols
            else "COALESCE(pcs.last_cost, 0)"
            if "last_cost" in pcs_cols
            else "0"
        )

        rows = conn.execute(
            f"""
            SELECT
                c.id,
                c.code,
                COALESCE(c.trade_name, c.legal_name, c.code) company_name,
                COUNT(DISTINCT pcs.product_id) products,
                SUM(CASE WHEN MAX(COALESCE(pcs.current_stock,0)-{reserved},0) <= COALESCE(pcs.minimum_stock,0) THEN 1 ELSE 0 END) critical_products,
                SUM(MAX(COALESCE(pcs.current_stock,0)-{reserved}-COALESCE(pcs.maximum_stock,0),0) * {average_cost}) idle_capital
            FROM companies c
            LEFT JOIN product_company_settings pcs ON pcs.company_id=c.id
            LEFT JOIN products p ON p.id=pcs.product_id
            WHERE c.active=1
            GROUP BY c.id, c.code, c.trade_name, c.legal_name
            ORDER BY idle_capital DESC, critical_products DESC, c.code
            """
        ).fetchall()

    result = []
    for row in rows:
        products = int(row["products"] or 0)
        critical = int(row["critical_products"] or 0)
        health = max(0, round(100 - ((critical / products) * 100))) if products else 100
        status = "critical" if health < 50 else "attention" if health < 75 else "healthy"
        result.append({
            "id": int(row["id"]),
            "code": str(row["code"]),
            "company_name": str(row["company_name"]),
            "products": products,
            "critical_products": critical,
            "idle_capital": float(row["idle_capital"] or 0),
            "money_idle_capital": _money(float(row["idle_capital"] or 0)),
            "health": health,
            "status": status,
        })
    return result


def _inventory_totals() -> dict:
    with database.connect() as conn:
        if not _table_exists(conn, "product_company_settings"):
            return {"inventory_value": 0.0, "critical_products": 0, "products": 0}
        cols = _column_names(conn, "product_company_settings")
        cost = (
            "COALESCE(average_cost,last_cost,0)"
            if {"average_cost", "last_cost"}.issubset(cols)
            else "COALESCE(average_cost,0)"
            if "average_cost" in cols
            else "COALESCE(last_cost,0)"
            if "last_cost" in cols
            else "0"
        )
        reserved = "COALESCE(reserved_stock,0)" if "reserved_stock" in cols else "0"
        row = conn.execute(
            f"""
            SELECT
                SUM(MAX(COALESCE(current_stock,0)-{reserved},0) * {cost}) inventory_value,
                SUM(CASE WHEN MAX(COALESCE(current_stock,0)-{reserved},0) <= COALESCE(minimum_stock,0) THEN 1 ELSE 0 END) critical_products,
                COUNT(DISTINCT product_id) products
            FROM product_company_settings
            """
        ).fetchone()
    return {
        "inventory_value": float(row["inventory_value"] or 0),
        "critical_products": int(row["critical_products"] or 0),
        "products": int(row["products"] or 0),
    }


@router.get("", response_class=HTMLResponse)
def executive_cockpit(request: Request):
    user = _main().require(request)
    if not user:
        return _main().login_redirect()

    recommendations, transfer_context = calculate_transfers()
    transfer_metrics = transfer_context["metrics"]
    companies = _company_health()
    inventory = _inventory_totals()

    top_opportunities = recommendations[:5]
    best_company = max(companies, key=lambda item: item["health"], default=None)
    attention_company = min(companies, key=lambda item: item["health"], default=None)

    summary = (
        f"Hoje o SmartBuy identificou {transfer_metrics['recommendations']} oportunidade(s) de transferência, "
        f"com potencial de evitar {transfer_metrics['money_total_avoided']} em compras. "
        f"O capital acima da cobertura está estimado em {transfer_metrics['money_idle_capital']}. "
    )
    if top_opportunities:
        first = top_opportunities[0]
        summary += (
            f"A prioridade é transferir {int(first.quantity) if float(first.quantity).is_integer() else first.quantity} "
            f"unidades de {first.origin_company} para {first.destination_company}, "
            f"evitando aproximadamente {_money(first.avoided_purchase)}."
        )
    else:
        summary += "Nenhuma transferência segura foi encontrada neste momento."

    context = {
        "transfer_metrics": transfer_metrics,
        "companies": companies,
        "top_opportunities": top_opportunities,
        "inventory": {
            **inventory,
            "money_inventory_value": _money(inventory["inventory_value"]),
        },
        "best_company": best_company,
        "attention_company": attention_company,
        "executive_summary": summary,
        "money": _money,
    }

    return _main().templates.TemplateResponse(
        "executive_cockpit.html",
        _main().base_context(request, user, **context),
    )
