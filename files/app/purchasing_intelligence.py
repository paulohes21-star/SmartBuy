from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import database
from app.purchasing_engine import calculate_recommendations


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


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    company_id: int | None = None,
    analysis_months: int | None = None,
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

    with database.connect() as conn:
        companies, products, suppliers = _load_selects(conn)

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
