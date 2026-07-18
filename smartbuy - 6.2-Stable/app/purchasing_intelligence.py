from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from io import BytesIO
from urllib.parse import quote
import re

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import database
from app.purchasing_engine import calculate_recommendations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)



router = APIRouter(
    prefix="/purchasing-intelligence",
    tags=["purchasing-intelligence"],
)


def _main():
    import app.main as main
    return main


def _user(request: Request, permission: str):
    return _main().require(request, permission)


def _templates():
    return _main().templates


def _context(request: Request, user, **extra: Any):
    return _main().base_context(request, user, **extra)


def _load_selects(conn):
    companies = conn.execute(
        """
        SELECT id, code, legal_name, trade_name
        FROM companies WHERE active=1 ORDER BY code
        """
    ).fetchall()
    products = conn.execute(
        """
        SELECT id, internal_code, description
        FROM products WHERE active=1 ORDER BY internal_code
        """
    ).fetchall()
    suppliers = conn.execute(
        """
        SELECT id, code, legal_name, trade_name
        FROM suppliers WHERE active=1 ORDER BY code
        """
    ).fetchall()
    return companies, products, suppliers


def _money_br(value: float) -> str:
    formatted = f"{float(value or 0):,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _quantity_br(value: float) -> str:
    number = float(value or 0)
    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")
    formatted = f"{number:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _build_decision_center(recommendations: list[Any]) -> dict[str, Any]:
    """Build deterministic decision explanations from current engine outputs."""
    items = list(recommendations or [])
    to_buy = [item for item in items if float(item.suggested_quantity or 0) > 0]
    critical = [
        item for item in items
        if item.days_of_cover is not None and float(item.days_of_cover) <= 30
    ]
    without_supplier = [
        item for item in to_buy
        if not (item.best_quote_supplier_name or item.preferred_supplier_name)
    ]
    idle = [
        item for item in items
        if float(item.average_daily_consumption or 0) <= 0
        and float(item.available_stock or 0) > 0
    ]

    def unit_cost(item: Any) -> float:
        return float(
            item.best_quote_landed_unit_cost
            if item.best_quote_landed_unit_cost is not None
            else item.average_cost or 0
        )

    investment = sum(float(item.suggested_quantity or 0) * unit_cost(item) for item in to_buy)
    critical_stock_value = sum(max(float(item.available_stock or 0), 0) * unit_cost(item) for item in critical)
    idle_capital = sum(max(float(item.available_stock or 0), 0) * unit_cost(item) for item in idle)

    ranked = sorted(
        to_buy,
        key=lambda item: (
            item.days_of_cover is None,
            float(item.days_of_cover) if item.days_of_cover is not None else 10**9,
            -float(item.suggested_quantity or 0) * unit_cost(item),
        ),
    )[:5]

    priorities = []
    for position, item in enumerate(ranked, start=1):
        coverage = float(item.days_of_cover) if item.days_of_cover is not None else None
        urgency = "Crítica" if coverage is not None and coverage <= 15 else ("Alta" if coverage is not None and coverage <= 30 else "Planejada")
        supplier = item.best_quote_supplier_name or item.preferred_supplier_name or "Fornecedor não definido"
        reason_parts = [
            f"estoque disponível de {_quantity_br(item.available_stock)} UN",
            f"ponto de reposição de {_quantity_br(item.reorder_point)} UN",
        ]
        if coverage is not None:
            reason_parts.append(f"cobertura de {coverage:.1f} dias".replace(".", ","))
        reason_parts.append(f"lead time de {int(item.lead_time_days or 0)} dias")
        priorities.append({
            "position": position,
            "code": item.internal_code,
            "description": item.description,
            "urgency": urgency,
            "suggested_quantity": _quantity_br(item.suggested_quantity),
            "estimated_value": _money_br(float(item.suggested_quantity or 0) * unit_cost(item)),
            "supplier": supplier,
            "reason": "A recomendação considera " + ", ".join(reason_parts) + ".",
        })

    total = len(items)
    if not items:
        summary = "Ainda não existem produtos configurados para análise. Cadastre os parâmetros por empresa para o SmartBuy gerar decisões de compra."
        status = "Aguardando dados"
    elif not to_buy:
        summary = f"O SmartBuy analisou {total} produto(s) e não identificou necessidade de reposição neste momento. Continue monitorando consumo, cobertura e pedidos em aberto."
        status = "Operação saudável"
    else:
        summary = (
            f"O SmartBuy analisou {total} produto(s) e identificou {len(to_buy)} item(ns) com reposição recomendada. "
            f"{len(critical)} item(ns) possuem cobertura de até 30 dias. "
            f"O investimento calculado para as recomendações atuais é {_money_br(investment)}."
        )
        status = "Ação recomendada"

    actions = []
    if to_buy:
        actions.append({"state": "primary", "title": "Gerar solicitações de cotação", "detail": f"Consolidar {len(to_buy)} item(ns) recomendados por empresa e fornecedor."})
    if critical:
        actions.append({"state": "danger", "title": "Tratar itens críticos primeiro", "detail": f"Revisar {len(critical)} item(ns) com cobertura de até 30 dias."})
    if without_supplier:
        actions.append({"state": "warning", "title": "Definir fornecedores", "detail": f"Existem {len(without_supplier)} item(ns) de compra sem fornecedor definido."})
    if idle:
        actions.append({"state": "neutral", "title": "Revisar capital sem consumo", "detail": f"Avaliar {len(idle)} item(ns) com estoque disponível e consumo médio zerado."})
    if not actions:
        actions.append({"state": "success", "title": "Manter monitoramento", "detail": "Nenhuma ação de compra é necessária com os dados atuais."})

    return {
        "status": status,
        "summary": summary,
        "priorities": priorities,
        "actions": actions[:4],
        "metrics": {
            "recommended_investment": _money_br(investment),
            "critical_items": len(critical),
            "critical_stock_value": _money_br(critical_stock_value),
            "idle_items": len(idle),
            "idle_capital": _money_br(idle_capital),
            "undefined_suppliers": len(without_supplier),
        },
    }


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    company_id: int | None = None,
    analysis_months: int | None = None,
    exclude: str = Query(""),
):
    user = _user(request, "purchasing_intelligence.read")
    if not user:
        return _main().login_redirect()

    recommendations = calculate_recommendations(
        company_id=company_id,
        analysis_months_override=analysis_months,
    )
    to_buy = [
        item for item in recommendations
        if item.suggested_quantity > 0
    ]
    estimated_value = sum(
        item.suggested_quantity
        * (
            item.best_quote_landed_unit_cost
            if item.best_quote_landed_unit_cost is not None
            else item.average_cost
        )
        for item in to_buy
    )
    rupture_soon = sum(
        1 for item in recommendations
        if item.days_of_cover is not None and item.days_of_cover <= 30
    )

    abc_counts = {"A": 0, "B": 0, "C": 0}
    health_counts = {"healthy": 0, "attention": 0, "risk": 0}
    for item in recommendations:
        abc_counts[item.abc_class if item.abc_class in abc_counts else "C"] += 1
        if item.days_of_cover is not None and item.days_of_cover <= 30:
            health_counts["risk"] += 1
        elif item.suggested_quantity > 0 or (
            item.days_of_cover is not None and item.days_of_cover <= 60
        ):
            health_counts["attention"] += 1
        else:
            health_counts["healthy"] += 1

    total_health = max(len(recommendations), 1)
    health_percentages = {
        key: round(value * 100 / total_health)
        for key, value in health_counts.items()
    }

    today = date.today()
    month_keys = []
    month_labels = [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez",
    ]
    for offset in range(6, -1, -1):
        month_number = today.month - offset
        year = today.year
        while month_number <= 0:
            month_number += 12
            year -= 1
        month_keys.append((f"{year:04d}-{month_number:02d}", month_labels[month_number - 1]))

    with database.connect() as conn:
        companies, products, suppliers = _load_selects(conn)
        monthly_params: list[Any] = []
        company_filter = ""
        if company_id:
            company_filter = " AND company_id=?"
            monthly_params.append(company_id)
        monthly_rows = conn.execute(
            f"""
            SELECT strftime('%Y-%m', movement_date) month_key,
                   COALESCE(SUM(quantity), 0) total
            FROM stock_movements
            WHERE movement_type IN ('OUT', 'CONSUMPTION', 'SALE')
              AND date(movement_date) >= date('now', 'start of month', '-6 months')
              {company_filter}
            GROUP BY strftime('%Y-%m', movement_date)
            ORDER BY month_key
            """,
            monthly_params,
        ).fetchall()

    monthly_lookup = {row["month_key"]: float(row["total"] or 0) for row in monthly_rows}
    monthly_demand = [
        {"label": label, "value": round(monthly_lookup.get(key, 0), 2)}
        for key, label in month_keys
    ]
    max_demand = max((item["value"] for item in monthly_demand), default=0) or 1
    chart_points = []
    for index, item in enumerate(monthly_demand):
        x = 24 + index * 92
        y = 156 - (item["value"] / max_demand) * 118
        chart_points.append(f"{x:.1f},{y:.1f}")
    demand_chart_points = " ".join(chart_points)
    first_value = monthly_demand[0]["value"] if monthly_demand else 0
    last_value = monthly_demand[-1]["value"] if monthly_demand else 0
    demand_growth = round(((last_value - first_value) / first_value) * 100, 1) if first_value else 0
    decision_center = _build_decision_center(recommendations)

    return _templates().TemplateResponse(
        "purchasing_intelligence.html",
        _context(
            request,
            user,
            recommendations=recommendations,
            to_buy=to_buy,
            total_products=len(recommendations),
            products_to_buy=len(to_buy),
            estimated_value=estimated_value,
            rupture_soon=rupture_soon,
            companies=companies,
            products=products,
            suppliers=suppliers,
            selected_company_id=company_id,
            selected_analysis_months=analysis_months or 3,
            abc_counts=abc_counts,
            health_counts=health_counts,
            health_percentages=health_percentages,
            monthly_demand=monthly_demand,
            demand_chart_points=demand_chart_points,
            demand_growth=demand_growth,
            decision_center=decision_center,
        ),
    )


@router.post("/movement")
def register_movement(
    request: Request,
    product_id: int = Form(...),
    company_id: int = Form(...),
    movement_type: str = Form(...),
    quantity: float = Form(...),
    movement_date: str = Form(...),
    reference_number: str = Form(""),
    unit_cost: float | None = Form(None),
    notes: str = Form(""),
):
    user = _user(request, "purchasing_intelligence.write")
    if not user:
        return _main().login_redirect()
    if quantity < 0:
        raise HTTPException(
            status_code=422,
            detail="Quantidade não pode ser negativa",
        )

    movement_type = movement_type.strip().upper()
    allowed = {"IN", "OUT", "CONSUMPTION", "SALE", "ADJUSTMENT"}
    if movement_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail="Tipo de movimentação inválido",
        )

    with database.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO stock_movements(
                product_id, company_id, movement_type, quantity,
                movement_date, reference_number, unit_cost,
                notes, created_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                company_id,
                movement_type,
                quantity,
                movement_date,
                reference_number.strip() or None,
                unit_cost,
                notes.strip() or None,
                user["id"],
            ),
        )
        conn.commit()

    database.audit(
        user["id"],
        "purchasing.movement.created",
        f"id={cursor.lastrowid};produto={product_id};quantidade={quantity}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )


@router.post("/cost")
def register_cost(
    request: Request,
    product_id: int = Form(...),
    company_id: int = Form(...),
    supplier_id: int | None = Form(None),
    unit_cost: float = Form(...),
    quantity: float = Form(0),
    cost_date: str = Form(...),
    reference_number: str = Form(""),
):
    user = _user(request, "purchasing_intelligence.write")
    if not user:
        return _main().login_redirect()
    if unit_cost < 0 or quantity < 0:
        raise HTTPException(
            status_code=422,
            detail="Valores não podem ser negativos",
        )

    total_cost = unit_cost * quantity
    with database.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO product_cost_history(
                product_id, company_id, supplier_id, unit_cost,
                quantity, total_cost, cost_date, reference_number,
                created_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                company_id,
                supplier_id,
                unit_cost,
                quantity,
                total_cost,
                cost_date,
                reference_number.strip() or None,
                user["id"],
            ),
        )

        weighted = conn.execute(
            """
            SELECT
                CASE
                  WHEN SUM(quantity) > 0
                  THEN SUM(total_cost) / SUM(quantity)
                  ELSE AVG(unit_cost)
                END weighted_average
            FROM product_cost_history
            WHERE product_id=? AND company_id=?
            """,
            (product_id, company_id),
        ).fetchone()["weighted_average"]

        conn.execute(
            """
            UPDATE product_company_settings
            SET average_cost=?,
                last_cost=?,
                last_purchase_date=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE product_id=? AND company_id=?
            """,
            (
                weighted or unit_cost,
                unit_cost,
                cost_date,
                product_id,
                company_id,
            ),
        )
        conn.commit()

    database.audit(
        user["id"],
        "purchasing.cost.created",
        f"id={cursor.lastrowid};produto={product_id};custo={unit_cost}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )


@router.post("/policy")
def update_policy(
    request: Request,
    product_id: int = Form(...),
    company_id: int = Form(...),
    analysis_months: int = Form(...),
    safety_days: int = Form(...),
    coverage_days: int = Form(...),
    lead_time_days: int = Form(...),
    on_order_stock: float = Form(0),
):
    user = _user(request, "purchasing_intelligence.configure")
    if not user:
        return _main().login_redirect()

    if min(
        analysis_months,
        safety_days,
        coverage_days,
        lead_time_days,
    ) < 0 or on_order_stock < 0:
        raise HTTPException(
            status_code=422,
            detail="Parâmetros não podem ser negativos",
        )
    if analysis_months < 1 or coverage_days < 1:
        raise HTTPException(
            status_code=422,
            detail="Período e cobertura devem ser maiores que zero",
        )

    with database.connect() as conn:
        result = conn.execute(
            """
            UPDATE product_company_settings
            SET analysis_months=?,
                safety_days=?,
                coverage_days=?,
                lead_time_days=?,
                on_order_stock=?,
                replenishment_mode='AUTO',
                updated_at=CURRENT_TIMESTAMP
            WHERE product_id=? AND company_id=?
            """,
            (
                analysis_months,
                safety_days,
                coverage_days,
                lead_time_days,
                on_order_stock,
                product_id,
                company_id,
            ),
        )
        conn.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Produto não configurado para essa empresa",
        )

    database.audit(
        user["id"],
        "purchasing.policy.updated",
        f"produto={product_id};empresa={company_id}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )


@router.post("/supplier")
def upsert_product_supplier(
    request: Request,
    product_id: int = Form(...),
    supplier_id: int = Form(...),
    preferred: int = Form(0),
    last_price: float | None = Form(None),
    lead_time_days: int | None = Form(None),
    minimum_order_quantity: float = Form(0),
    supplier_score: float = Form(0),
):
    user = _user(request, "purchasing_intelligence.write")
    if not user:
        return _main().login_redirect()

    with database.connect() as conn:
        if preferred:
            conn.execute(
                """
                UPDATE product_suppliers
                SET preferred=0
                WHERE product_id=?
                """,
                (product_id,),
            )
        conn.execute(
            """
            INSERT INTO product_suppliers(
                product_id, supplier_id, preferred, last_price,
                lead_time_days, minimum_order_quantity,
                supplier_score, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(product_id, supplier_id) DO UPDATE SET
                preferred=excluded.preferred,
                last_price=excluded.last_price,
                lead_time_days=excluded.lead_time_days,
                minimum_order_quantity=excluded.minimum_order_quantity,
                supplier_score=excluded.supplier_score,
                active=1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                product_id,
                supplier_id,
                1 if preferred else 0,
                last_price,
                lead_time_days,
                minimum_order_quantity,
                supplier_score,
            ),
        )
        conn.commit()

    database.audit(
        user["id"],
        "purchasing.product_supplier.updated",
        f"produto={product_id};fornecedor={supplier_id}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )


@router.post("/quote")
def register_quote(
    request: Request,
    company_id: int = Form(...),
    product_id: int = Form(...),
    supplier_id: int = Form(...),
    quantity: float = Form(...),
    unit_price: float = Form(...),
    freight_total: float = Form(0),
    taxes_total: float = Form(0),
    discount_total: float = Form(0),
    payment_term_days: int = Form(0),
    lead_time_days: int = Form(0),
    valid_until: str = Form(""),
    notes: str = Form(""),
):
    user = _user(request, "purchasing_intelligence.write")
    if not user:
        return _main().login_redirect()

    numeric = [
        quantity,
        unit_price,
        freight_total,
        taxes_total,
        discount_total,
        payment_term_days,
        lead_time_days,
    ]
    if quantity <= 0 or any(value < 0 for value in numeric[1:]):
        raise HTTPException(
            status_code=422,
            detail="Valores da cotação são inválidos",
        )

    with database.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO supplier_quotes(
                company_id, product_id, supplier_id, quantity,
                unit_price, freight_total, taxes_total, discount_total,
                payment_term_days, lead_time_days, valid_until,
                notes, created_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                product_id,
                supplier_id,
                quantity,
                unit_price,
                freight_total,
                taxes_total,
                discount_total,
                payment_term_days,
                lead_time_days,
                valid_until or None,
                notes.strip() or None,
                user["id"],
            ),
        )
        conn.commit()

    database.audit(
        user["id"],
        "purchasing.quote.created",
        f"id={cursor.lastrowid};produto={product_id};fornecedor={supplier_id}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )


@router.post("/snapshot")
def create_snapshot(
    request: Request,
    company_id: int = Form(...),
):
    user = _user(request, "purchasing_intelligence.write")
    if not user:
        return _main().login_redirect()

    today = date.today().isoformat()
    with database.connect() as conn:
        rows = conn.execute(
            """
            SELECT product_id, company_id, current_stock,
                   reserved_stock, on_order_stock
            FROM product_company_settings
            WHERE company_id=?
            """,
            (company_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO inventory_snapshots(
                    product_id, company_id, snapshot_date,
                    current_stock, reserved_stock, on_order_stock
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, company_id, snapshot_date)
                DO UPDATE SET
                    current_stock=excluded.current_stock,
                    reserved_stock=excluded.reserved_stock,
                    on_order_stock=excluded.on_order_stock
                """,
                (
                    row["product_id"],
                    row["company_id"],
                    today,
                    row["current_stock"],
                    row["reserved_stock"],
                    row["on_order_stock"],
                ),
            )
        conn.commit()

    database.audit(
        user["id"],
        "purchasing.snapshot.created",
        f"empresa={company_id};data={today};itens={len(rows)}",
    )
    return RedirectResponse(
        "/purchasing-intelligence",
        status_code=303,
    )



# SMARTBUY_RFQ_PRESENTATION
def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize_supplier_name(value: str | None) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
    suffixes = (
        "LTDA", "EIRELI", "ME", "EPP", "SA", "SAA", "COMERCIO",
        "INDUSTRIA", "DISTRIBUIDORA", "IMPORTACAO", "EXPORTACAO",
    )
    for suffix in suffixes:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 3:
            normalized = normalized[:-len(suffix)]
    return normalized or "SEMFORNECEDOR"


def _supplier_contact(conn, supplier_id: int | None) -> dict[str, Any]:
    if not supplier_id:
        return {
            "id": None,
            "code": "SEM-FORNECEDOR",
            "name": "Fornecedor não definido",
            "legal_name": "",
            "trade_name": "",
            "tax_id": "",
            "email": "",
            "phone": "",
        }

    row = conn.execute(
        """
        SELECT
            id,
            code,
            COALESCE(trade_name, legal_name) name,
            COALESCE(legal_name, '') legal_name,
            COALESCE(trade_name, '') trade_name,
            COALESCE(tax_id, '') tax_id,
            COALESCE(email, '') email,
            COALESCE(phone, '') phone
        FROM suppliers
        WHERE id=?
        """,
        (supplier_id,),
    ).fetchone()

    if not row:
        return {
            "id": None,
            "code": "SEM-FORNECEDOR",
            "name": "Fornecedor não definido",
            "legal_name": "",
            "trade_name": "",
            "tax_id": "",
            "email": "",
            "phone": "",
        }
    return dict(row)


def _supplier_identity(supplier: dict[str, Any]) -> tuple[str, str]:
    tax_digits = _digits(supplier.get("tax_id"))
    if tax_digits:
        return ("tax_id", tax_digits)

    normalized_name = _normalize_supplier_name(
        supplier.get("legal_name")
        or supplier.get("trade_name")
        or supplier.get("name")
    )
    if normalized_name and normalized_name != "SEMFORNECEDOR":
        return ("name", normalized_name)

    return ("id", str(supplier.get("id") or 0))


def _company_contact(conn, company_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            id,
            code,
            COALESCE(trade_name, legal_name) name,
            COALESCE(tax_id, '') tax_id,
            COALESCE(city, '') city,
            COALESCE(state, '') state
        FROM companies
        WHERE id=?
        """,
        (company_id,),
    ).fetchone()
    return dict(row) if row else {
        "id": company_id,
        "code": "",
        "name": "Empresa não identificada",
        "tax_id": "",
        "city": "",
        "state": "",
    }


def _format_date_br(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return parsed.strftime("%d-%m-%Y")


def _format_quantity(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".replace(".", ",")


def _parse_rfq_exclusions(value: str | None) -> set[tuple[int, int]]:
    exclusions: set[tuple[int, int]] = set()
    for token in (value or "").split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        company_text, product_text = token.split(":", 1)
        try:
            exclusions.add((int(company_text), int(product_text)))
        except ValueError:
            continue
    return exclusions


def _serialize_rfq_exclusions(exclusions: set[tuple[int, int]]) -> str:
    return ",".join(
        f"{company_id}:{product_id}"
        for company_id, product_id in sorted(exclusions)
    )


def _rfq_message(
    *,
    request_number: str,
    supplier_name: str,
    product_groups: list[dict[str, Any]],
) -> str:
    lines = [
        f"Olá, equipe {supplier_name}.",
        "",
        f"Segue a Solicitação de Cotação Consolidada {request_number}.",
        "",
        "Itens solicitados:",
    ]

    for product in product_groups:
        lines.append(
            f"• {product['internal_code']} — {product['description']} — "
            f"{_format_quantity(product['total_quantity'])} UN"
        )
        for allocation in product["allocations"]:
            lines.append(
                f"  - {allocation['company_code']} — "
                f"{_format_quantity(allocation['quantity'])} UN"
            )

    lines.extend([
        "",
        "Favor informar:",
        "• preço unitário e valor total;",
        "• IPI e ICMS;",
        "• valor do frete;",
        "• disponibilidade e prazo de entrega;",
        "• condição de pagamento;",
        "• validade da proposta;",
        "• garantia.",
        "",
        "Aguardamos o retorno. Obrigado.",
    ])
    return "\n".join(lines)


def _choose_primary_supplier(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    def score(supplier: dict[str, Any]) -> tuple[int, int, int]:
        return (
            1 if supplier.get("tax_id") else 0,
            1 if supplier.get("email") else 0,
            1 if supplier.get("phone") else 0,
        )
    return candidate if score(candidate) > score(current) else current


def _build_supplier_rfq_groups(
    recommendations: list[Any],
    *,
    exclusions: set[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Consolidate recommendations into one RFQ per real supplier identity."""
    excluded = exclusions or set()
    selected = [
        item for item in recommendations
        if float(item.suggested_quantity or 0) > 0
        and (int(item.company_id), int(item.product_id)) not in excluded
    ]

    groups: dict[tuple[str, str], dict[str, Any]] = {}
    with database.connect() as conn:
        for item in selected:
            supplier_id = (
                item.best_quote_supplier_id
                or item.preferred_supplier_id
            )
            supplier = _supplier_contact(conn, supplier_id)
            identity = _supplier_identity(supplier)

            if identity not in groups:
                identity_code = re.sub(r"[^A-Z0-9]", "", identity[1].upper())[-10:] or "000"
                request_number = (
                    f"SC-{date.today().strftime('%Y%m%d')}-"
                    f"FORN-{identity_code}"
                )
                groups[identity] = {
                    "request_number": request_number,
                    "supplier": supplier,
                    "supplier_ids": set(),
                    "identity_type": identity[0],
                    "identity_value": identity[1],
                    "duplicate_records_merged": 0,
                    "companies": {},
                    "items": [],
                    "estimated_value": 0.0,
                    "total_units": 0.0,
                    "valid_until_br": (
                        date.today() + timedelta(days=2)
                    ).strftime("%d-%m-%Y"),
                }

            group = groups[identity]
            group["supplier"] = _choose_primary_supplier(
                group["supplier"],
                supplier,
            )
            if supplier.get("id") is not None:
                group["supplier_ids"].add(int(supplier["id"]))

            company = _company_contact(conn, int(item.company_id))
            group["companies"][company["id"]] = company

            unit_cost = (
                item.best_quote_landed_unit_cost
                if item.best_quote_landed_unit_cost is not None
                else item.average_cost
            )
            line_total = float(item.suggested_quantity or 0) * float(unit_cost or 0)
            group["items"].append({
                "product_id": int(item.product_id),
                "company_id": int(item.company_id),
                "company_code": company["code"],
                "company_name": company["name"],
                "company_tax_id": company.get("tax_id") or "",
                "internal_code": item.internal_code,
                "description": item.description,
                "quantity": float(item.suggested_quantity or 0),
                "unit_cost": float(unit_cost or 0),
                "estimated_total": line_total,
                "days_of_cover": item.days_of_cover,
                "rupture_date": item.rupture_date,
                "rupture_date_br": _format_date_br(item.rupture_date),
                "priority": (
                    "Alta prioridade"
                    if item.days_of_cover is not None
                    and float(item.days_of_cover) <= 30
                    else "Média prioridade"
                ),
                "exclusion_token": f"{int(item.company_id)}:{int(item.product_id)}",
            })
            group["estimated_value"] += line_total
            group["total_units"] += float(item.suggested_quantity or 0)

    result = []
    for group in groups.values():
        group["companies"] = sorted(
            group["companies"].values(),
            key=lambda company: (company["code"], company["name"]),
        )
        group["supplier_ids"] = sorted(group["supplier_ids"])
        group["duplicate_records_merged"] = max(
            len(group["supplier_ids"]) - 1,
            0,
        )

        product_map: dict[tuple[int, str], dict[str, Any]] = {}
        for item in group["items"]:
            product_key = (
                int(item["product_id"]),
                str(item["internal_code"]).upper(),
            )
            if product_key not in product_map:
                product_map[product_key] = {
                    "product_id": item["product_id"],
                    "internal_code": item["internal_code"],
                    "description": item["description"],
                    "total_quantity": 0.0,
                    "estimated_total": 0.0,
                    "unit_cost": item["unit_cost"],
                    "highest_priority": item["priority"],
                    "minimum_cover": item["days_of_cover"],
                    "earliest_rupture": item["rupture_date"],
                    "earliest_rupture_br": item["rupture_date_br"],
                    "allocations": [],
                }

            product = product_map[product_key]
            product["total_quantity"] += float(item["quantity"])
            product["estimated_total"] += float(item["estimated_total"])
            product["allocations"].append(item)

            if item["priority"] == "Alta prioridade":
                product["highest_priority"] = "Alta prioridade"

            covers = [
                value for value in (
                    product["minimum_cover"],
                    item["days_of_cover"],
                )
                if value is not None
            ]
            product["minimum_cover"] = min(covers) if covers else None

            dates = [
                value for value in (
                    product["earliest_rupture"],
                    item["rupture_date"],
                )
                if value
            ]
            if dates:
                earliest = min(dates)
                product["earliest_rupture"] = earliest
                product["earliest_rupture_br"] = _format_date_br(earliest)

        group["product_groups"] = sorted(
            product_map.values(),
            key=lambda product: (
                0 if product["highest_priority"] == "Alta prioridade" else 1,
                product["internal_code"],
            ),
        )
        group["unique_skus"] = len(group["product_groups"])
        group["company_count"] = len(group["companies"])
        group["items"].sort(
            key=lambda item: (
                item["company_code"],
                item["internal_code"],
            )
        )
        result.append(group)

    return sorted(
        result,
        key=lambda group: (
            0 if group["supplier"].get("tax_id") else 1,
            group["supplier"]["name"],
        ),
    )


@router.get("/rfq", response_class=HTMLResponse)
def quotation_requests(
    request: Request,
    company_id: int | None = None,
    analysis_months: int | None = None,
    exclude: str = Query(""),
):
    user = _user(request, "purchasing_intelligence.read")
    if not user:
        return _main().login_redirect()

    recommendations = calculate_recommendations(
        company_id=company_id,
        analysis_months_override=analysis_months,
    )
    excluded = _parse_rfq_exclusions(exclude)
    rfqs = _build_supplier_rfq_groups(
        recommendations,
        exclusions=excluded,
    )

    for group in rfqs:
        message = _rfq_message(
            request_number=group["request_number"],
            supplier_name=group["supplier"]["name"],
            product_groups=group["product_groups"],
        )
        phone = _digits(group["supplier"]["phone"])
        if phone and not phone.startswith("55"):
            phone = "55" + phone
        group["message"] = message
        group["whatsapp_url"] = (
            f"https://wa.me/{phone}?text={quote(message)}"
            if phone
            else f"https://wa.me/?text={quote(message)}"
        )
        group["email_url"] = (
            f"mailto:{group['supplier']['email']}?"
            f"subject={quote('Solicitação de Cotação ' + group['request_number'])}"
            f"&body={quote(message)}"
        )

    total_items = sum(len(group["items"]) for group in rfqs)
    database.audit(
        user["id"],
        "purchasing.rfq.previewed",
        f"fornecedores={len(rfqs)};itens={total_items};excluidos={len(excluded)}",
    )

    return _templates().TemplateResponse(
        "quotation_requests.html",
        _context(
            request,
            user,
            rfqs=rfqs,
            total_requests=len(rfqs),
            total_items=total_items,
            total_estimated=sum(
                group["estimated_value"] for group in rfqs
            ),
            total_suppliers=len(rfqs),
            excluded_tokens=_serialize_rfq_exclusions(excluded),
            excluded_count=len(excluded),
            selected_company_id=company_id,
            selected_analysis_months=analysis_months or 3,
        ),
    )


def _build_rfq_pdf_groups(
    *,
    company_id: int | None,
    analysis_months: int | None,
    exclusions: set[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    recommendations = calculate_recommendations(
        company_id=company_id,
        analysis_months_override=analysis_months,
    )
    return _build_supplier_rfq_groups(
        recommendations,
        exclusions=exclusions,
    )


def _pdf_money(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _pdf_quantity(value: float) -> str:
    return _format_quantity(value)


def _pdf_header_footer(canvas, doc) -> None:
    canvas.saveState()
    page_width, page_height = A4

    canvas.setFillColor(colors.HexColor("#0B2A22"))
    canvas.rect(0, page_height - 21 * mm, page_width, 21 * mm, fill=1, stroke=0)

    canvas.setFillColor(colors.HexColor("#35E2AD"))
    canvas.roundRect(14 * mm, page_height - 16 * mm, 10 * mm, 10 * mm, 2 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#06231A"))
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawCentredString(19 * mm, page_height - 12.4 * mm, "SB")

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(28 * mm, page_height - 10.5 * mm, "SmartBuy Enterprise")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#A9C9C0"))
    canvas.drawString(28 * mm, page_height - 15 * mm, "Solicitação de Cotação")

    canvas.setStrokeColor(colors.HexColor("#D8E7E2"))
    canvas.line(14 * mm, 15 * mm, page_width - 14 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#647B75"))
    canvas.drawString(14 * mm, 10 * mm, "Documento gerado pelo SmartBuy Enterprise")
    canvas.drawRightString(
        page_width - 14 * mm,
        10 * mm,
        f"Página {doc.page}",
    )
    canvas.restoreState()


def _generate_rfq_pdf(group: dict[str, Any]) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
        title=f"Solicitação de Cotação {group['request_number']}",
        author="SmartBuy Enterprise",
        subject="Solicitação de Cotação Consolidada",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RfqTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0B2A22"),
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    section_style = ParagraphStyle(
        "RfqSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0B7454"),
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )
    normal_style = ParagraphStyle(
        "RfqNormal",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#243B35"),
    )
    small_style = ParagraphStyle(
        "RfqSmall",
        parent=normal_style,
        fontSize=7,
        leading=9,
    )
    center_style = ParagraphStyle(
        "RfqCenter",
        parent=small_style,
        alignment=TA_CENTER,
    )
    table_header_style = ParagraphStyle(
        "RfqTableHeader",
        parent=small_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    supplier = group["supplier"]
    companies = group["companies"]
    products = group["product_groups"]

    company_lines = "<br/>".join(
        f"<b>{company['code']} — {company['name']}</b>"
        + (f" · CNPJ {company.get('tax_id')}" if company.get("tax_id") else "")
        for company in companies
    )

    supplier_identifier = (
        f"CNPJ: {supplier.get('tax_id')}"
        if supplier.get("tax_id")
        else f"Identidade consolidada: {group['identity_value']}"
    )

    story = [
        Paragraph("SOLICITAÇÃO DE COTAÇÃO CONSOLIDADA", title_style),
        Paragraph(
            f"<b>Número:</b> {group['request_number']} &nbsp;&nbsp; "
            f"<b>Emissão:</b> {date.today().strftime('%d-%m-%Y')} &nbsp;&nbsp; "
            f"<b>Validade:</b> {group['valid_until_br']}",
            normal_style,
        ),
        Spacer(1, 4 * mm),
    ]

    contact_data = [[
        Paragraph("<b>EMPRESAS SOLICITANTES</b>", small_style),
        Paragraph("<b>FORNECEDOR</b>", small_style),
    ], [
        Paragraph(company_lines or "Empresa não identificada", normal_style),
        Paragraph(
            f"<b>{supplier['name']}</b><br/>"
            f"{supplier_identifier}<br/>"
            f"Telefone: {supplier.get('phone') or 'Não informado'}<br/>"
            f"E-mail: {supplier.get('email') or 'Não informado'}",
            normal_style,
        ),
    ]]
    contact_table = Table(contact_data, colWidths=[94 * mm, 88 * mm])
    contact_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF7F2")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9D8CE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4E8E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        contact_table,
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Resumo executivo:</b> {group['unique_skus']} SKU(s), "
            f"{group['company_count']} empresa(s), "
            f"{_pdf_quantity(group['total_units'])} unidade(s), "
            f"valor estimado {_pdf_money(group['estimated_value'])}.",
            normal_style,
        ),
        Spacer(1, 4 * mm),
        Paragraph("Produtos consolidados", section_style),
    ])

    rows = [[
        Paragraph("Código", table_header_style),
        Paragraph("Descrição", table_header_style),
        Paragraph("Qtd. total", table_header_style),
        Paragraph("Distribuição por empresa", table_header_style),
        Paragraph("Cobertura mínima", table_header_style),
        Paragraph("Ruptura", table_header_style),
        Paragraph("Referência", table_header_style),
    ]]

    for product in products:
        allocations = "<br/>".join(
            f"{allocation['company_code']}: "
            f"{_pdf_quantity(allocation['quantity'])} UN"
            for allocation in product["allocations"]
        )
        coverage = (
            f"{float(product['minimum_cover']):.1f} dias".replace(".", ",")
            if product["minimum_cover"] is not None
            else "Sem consumo"
        )
        rows.append([
            Paragraph(str(product["internal_code"]), small_style),
            Paragraph(str(product["description"]), small_style),
            Paragraph(
                f"{_pdf_quantity(product['total_quantity'])} UN",
                center_style,
            ),
            Paragraph(allocations, small_style),
            Paragraph(coverage, center_style),
            Paragraph(
                str(product["earliest_rupture_br"]),
                center_style,
            ),
            Paragraph(
                _pdf_money(float(product["unit_cost"] or 0)),
                center_style,
            ),
        ])

    item_table = Table(
        rows,
        repeatRows=1,
        colWidths=[23 * mm, 48 * mm, 20 * mm, 37 * mm, 22 * mm, 24 * mm, 25 * mm],
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A22")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7D2C9")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5E5DF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F4FAF7"),
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.extend([
        item_table,
        Spacer(1, 4 * mm),
        Paragraph("Informações obrigatórias na proposta", section_style),
        Paragraph(
            "Preço unitário e total; IPI; ICMS; frete; disponibilidade; "
            "prazo de entrega; condição de pagamento; validade e garantia.",
            normal_style,
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "Documento de cotação. Os valores apresentados são referências "
            "e não representam pedido de compra ou autorização de faturamento.",
            normal_style,
        ),
    ])

    document.build(
        story,
        onFirstPage=_pdf_header_footer,
        onLaterPages=_pdf_header_footer,
    )
    return output.getvalue()


@router.get("/rfq/pdf/{request_number}")
def quotation_request_pdf(
    request: Request,
    request_number: str,
    company_id: int | None = None,
    analysis_months: int | None = None,
    exclude: str = Query(""),
):
    user = _user(request, "purchasing_intelligence.read")
    if not user:
        return _main().login_redirect()

    groups = _build_rfq_pdf_groups(
        company_id=company_id,
        analysis_months=analysis_months,
        exclusions=_parse_rfq_exclusions(exclude),
    )
    group = next(
        (
            current
            for current in groups
            if current["request_number"] == request_number
        ),
        None,
    )
    if group is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitação de cotação não encontrada.",
        )

    pdf_bytes = _generate_rfq_pdf(group)
    database.audit(
        user["id"],
        "purchasing.rfq.pdf.generated",
        f"solicitacao={request_number}",
    )

    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", request_number)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="Solicitacao_Cotacao_{safe_name}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )
