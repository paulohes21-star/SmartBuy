from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from io import BytesIO
from urllib.parse import quote
import re

from fastapi import APIRouter, Form, HTTPException, Request
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



# SMARTBUY_RFQ_PRESENTATION
def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _supplier_contact(conn, supplier_id: int | None) -> dict[str, Any]:
    if not supplier_id:
        return {
            "id": None,
            "code": "SEM-FORNECEDOR",
            "name": "Fornecedor não definido",
            "email": "",
            "phone": "",
        }
    row = conn.execute(
        """
        SELECT
            id,
            code,
            COALESCE(trade_name, legal_name) name,
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
            "email": "",
            "phone": "",
        }
    return dict(row)


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


def _rfq_message(
    *,
    request_number: str,
    supplier_name: str,
    company_name: str,
    items: list[dict[str, Any]],
) -> str:
    lines = [
        f"Olá, equipe {supplier_name}.",
        "",
        f"Segue a Solicitação de Cotação {request_number}, "
        f"referente à empresa {company_name}.",
        "",
        "Itens solicitados:",
    ]
    for item in items:
        lines.append(
            f"• {item['internal_code']} — {item['description']} — "
            f"{_format_quantity(item['quantity'])} UN"
        )
    lines.extend([
        "",
        "Favor informar:",
        "• preço unitário;",
        "• impostos;",
        "• valor do frete;",
        "• prazo de entrega;",
        "• condição de pagamento;",
        "• validade da proposta.",
        "",
        "Aguardamos o retorno. Obrigado.",
    ])
    return "\n".join(lines)


@router.get("/rfq", response_class=HTMLResponse)
def quotation_requests(
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
    selected = [
        item for item in recommendations
        if item.suggested_quantity > 0
    ]

    groups: dict[tuple[int, int | None], dict[str, Any]] = {}
    with database.connect() as conn:
        for item in selected:
            supplier_id = (
                item.best_quote_supplier_id
                or item.preferred_supplier_id
            )
            key = (item.company_id, supplier_id)
            if key not in groups:
                supplier = _supplier_contact(conn, supplier_id)
                company = _company_contact(conn, item.company_id)
                request_number = (
                    f"SC-{date.today().strftime('%Y%m%d')}-"
                    f"{item.company_id:03d}-"
                    f"{(supplier_id or 0):03d}"
                )
                groups[key] = {
                    "request_number": request_number,
                    "supplier": supplier,
                    "company": company,
                    "items": [],
                    "estimated_value": 0.0,
                }

            unit_cost = (
                item.best_quote_landed_unit_cost
                if item.best_quote_landed_unit_cost is not None
                else item.average_cost
            )
            line_total = item.suggested_quantity * unit_cost
            groups[key]["items"].append({
                "product_id": item.product_id,
                "internal_code": item.internal_code,
                "description": item.description,
                "quantity": item.suggested_quantity,
                "unit_cost": unit_cost,
                "estimated_total": line_total,
                "days_of_cover": item.days_of_cover,
                "rupture_date": item.rupture_date,
                "rupture_date_br": _format_date_br(item.rupture_date),
                "priority": (
                    "Alta prioridade"
                    if item.suggested_quantity > 0
                    and item.days_of_cover is not None
                    and item.days_of_cover <= 30
                    else "Média prioridade"
                ),
            })
            groups[key]["estimated_value"] += line_total

    rfqs = []
    for group in groups.values():
        message = _rfq_message(
            request_number=group["request_number"],
            supplier_name=group["supplier"]["name"],
            company_name=group["company"]["name"],
            items=group["items"],
        )
        phone = _digits(group["supplier"]["phone"])
        if phone and not phone.startswith("55"):
            phone = "55" + phone
        group["message"] = message
        group["valid_until_br"] = (
            date.today() + timedelta(days=2)
        ).strftime("%d-%m-%Y")
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
        rfqs.append(group)

    rfqs.sort(
        key=lambda group: (
            group["supplier"]["name"],
            group["company"]["name"],
        )
    )

    database.audit(
        user["id"],
        "purchasing.rfq.previewed",
        f"solicitacoes={len(rfqs)};itens={len(selected)}",
    )

    return _templates().TemplateResponse(
        "quotation_requests.html",
        _context(
            request,
            user,
            rfqs=rfqs,
            total_requests=len(rfqs),
            total_items=len(selected),
            total_estimated=sum(
                group["estimated_value"] for group in rfqs
            ),
            selected_company_id=company_id,
            selected_analysis_months=analysis_months or 3,
        ),
    )


def _build_rfq_pdf_groups(
    *,
    company_id: int | None,
    analysis_months: int | None,
) -> list[dict[str, Any]]:
    """Rebuild RFQ groups using the same recommendation rules as the screen."""
    recommendations = calculate_recommendations(
        company_id=company_id,
        analysis_months_override=analysis_months,
    )
    selected = [
        item for item in recommendations
        if item.suggested_quantity > 0
    ]

    groups: dict[tuple[int, int | None], dict[str, Any]] = {}
    with database.connect() as conn:
        for item in selected:
            supplier_id = (
                item.best_quote_supplier_id
                or item.preferred_supplier_id
            )
            key = (item.company_id, supplier_id)

            if key not in groups:
                supplier = _supplier_contact(conn, supplier_id)
                company = _company_contact(conn, item.company_id)
                request_number = (
                    f"SC-{date.today().strftime('%Y%m%d')}-"
                    f"{item.company_id:03d}-"
                    f"{(supplier_id or 0):03d}"
                )
                groups[key] = {
                    "request_number": request_number,
                    "supplier": supplier,
                    "company": company,
                    "items": [],
                    "estimated_value": 0.0,
                    "valid_until_br": (
                        date.today() + timedelta(days=2)
                    ).strftime("%d-%m-%Y"),
                }

            unit_cost = (
                item.best_quote_landed_unit_cost
                if item.best_quote_landed_unit_cost is not None
                else item.average_cost
            )
            line_total = item.suggested_quantity * unit_cost
            groups[key]["items"].append({
                "internal_code": item.internal_code,
                "description": item.description,
                "quantity": item.suggested_quantity,
                "unit_cost": unit_cost,
                "estimated_total": line_total,
                "days_of_cover": item.days_of_cover,
                "rupture_date_br": _format_date_br(item.rupture_date),
            })
            groups[key]["estimated_value"] += line_total

    return sorted(
        groups.values(),
        key=lambda group: (
            group["supplier"]["name"],
            group["company"]["name"],
        ),
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
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=28 * mm,
        bottomMargin=22 * mm,
        title=f"Solicitação de Cotação {group['request_number']}",
        author="SmartBuy Enterprise",
        subject="Solicitação de Cotação",
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
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#243B35"),
    )
    small_style = ParagraphStyle(
        "RfqSmall",
        parent=normal_style,
        fontSize=7.5,
        leading=10,
    )
    center_style = ParagraphStyle(
        "RfqCenter",
        parent=normal_style,
        alignment=TA_CENTER,
    )
    table_header_style = ParagraphStyle(
        "RfqTableHeader",
        parent=small_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    company = group["company"]
    supplier = group["supplier"]
    items = group["items"]

    story = [
        Paragraph("SOLICITAÇÃO DE COTAÇÃO", title_style),
        Paragraph(
            f"<b>Número:</b> {group['request_number']} &nbsp;&nbsp;&nbsp; "
            f"<b>Emissão:</b> {date.today().strftime('%d-%m-%Y')} &nbsp;&nbsp;&nbsp; "
            f"<b>Validade:</b> {group['valid_until_br']}",
            normal_style,
        ),
        Spacer(1, 4 * mm),
    ]

    company_data = [
        [
            Paragraph("<b>EMPRESA SOLICITANTE</b>", small_style),
            Paragraph("<b>FORNECEDOR</b>", small_style),
        ],
        [
            Paragraph(
                f"<b>{company['name']}</b><br/>"
                f"Código: {company['code']}<br/>"
                f"CNPJ: {company.get('tax_id') or 'Não informado'}",
                normal_style,
            ),
            Paragraph(
                f"<b>{supplier['name']}</b><br/>"
                f"CNPJ: {supplier.get('tax_id') or 'Não informado'}<br/>"
                f"Telefone: {supplier.get('phone') or 'Não informado'}<br/>"
                f"WhatsApp: {supplier.get('phone') or 'Não informado'}<br/>"
                f"E-mail: {supplier.get('email') or 'Não informado'}",
                normal_style,
            ),
        ],
    ]
    company_table = Table(company_data, colWidths=[88 * mm, 88 * mm])
    company_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF7F2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0B7454")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9D8CE")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4E8E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([
        company_table,
        Spacer(1, 5 * mm),
        Paragraph("Itens solicitados", section_style),
    ])

    item_rows = [[
        Paragraph("Código", table_header_style),
        Paragraph("Descrição", table_header_style),
        Paragraph("Quantidade", table_header_style),
        Paragraph("Cobertura", table_header_style),
        Paragraph("Ruptura prevista", table_header_style),
        Paragraph("Valor de referência", table_header_style),
    ]]

    for item in items:
        coverage = (
            f"{item['days_of_cover']:.1f} dias"
            if item["days_of_cover"] is not None
            else "Sem consumo"
        )
        item_rows.append([
            Paragraph(str(item["internal_code"]), small_style),
            Paragraph(str(item["description"]), small_style),
            Paragraph(f"{_pdf_quantity(item['quantity'])} UN", center_style),
            Paragraph(coverage, center_style),
            Paragraph(str(item["rupture_date_br"]), center_style),
            Paragraph(_pdf_money(item["unit_cost"]), center_style),
        ])

    item_table = Table(
        item_rows,
        repeatRows=1,
        colWidths=[25 * mm, 53 * mm, 23 * mm, 24 * mm, 29 * mm, 31 * mm],
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A22")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7D2C9")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5E5DF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#F4FAF7"),
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        item_table,
        Spacer(1, 4 * mm),
        Paragraph(
            f"<b>Valor estimado da solicitação:</b> "
            f"{_pdf_money(group['estimated_value'])}",
            normal_style,
        ),
        Spacer(1, 4 * mm),
        Paragraph("Informações obrigatórias na proposta", section_style),
    ])

    requirements = [
        "Preço unitário e valor total",
        "IPI e ICMS",
        "Valor do frete",
        "Prazo de entrega",
        "Condição de pagamento",
        "Validade da proposta",
        "Garantia",
        "Dados bancários e comerciais, quando aplicável",
    ]
    requirement_rows = []
    for index in range(0, len(requirements), 2):
        left = requirements[index]
        right = requirements[index + 1] if index + 1 < len(requirements) else ""
        requirement_rows.append([
            Paragraph(f"✓ {left}", normal_style),
            Paragraph(f"✓ {right}" if right else "", normal_style),
        ])

    requirements_table = Table(requirement_rows, colWidths=[88 * mm, 88 * mm])
    requirements_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3FAF7")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8E0D7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E1EEE9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        requirements_table,
        Spacer(1, 4 * mm),
        Paragraph("Observações", section_style),
        Paragraph(
            "Esta solicitação foi gerada a partir das recomendações do "
            "Motor Inteligente de Compras do SmartBuy. Os valores apresentados "
            "são referências para cotação e não representam pedido de compra "
            "ou autorização de faturamento.",
            normal_style,
        ),
        Spacer(1, 13 * mm),
    ])

    signature = Table(
        [[
            Paragraph(
                "_________________________________________<br/>"
                "<b>Departamento de Compras</b><br/>"
                "SmartBuy Enterprise",
                center_style,
            )
        ]],
        colWidths=[176 * mm],
    )
    signature.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether(signature))

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
):
    user = _user(request, "purchasing_intelligence.read")
    if not user:
        return _main().login_redirect()

    groups = _build_rfq_pdf_groups(
        company_id=company_id,
        analysis_months=analysis_months,
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
