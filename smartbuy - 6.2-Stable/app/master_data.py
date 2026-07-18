from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import database


router = APIRouter(tags=["master-data"])


@dataclass(frozen=True)
class EntityDefinition:
    key: str
    title: str
    table: str
    order_by: str
    fields: tuple[str, ...]


ENTITIES: dict[str, EntityDefinition] = {
    "manufacturers": EntityDefinition(
        key="manufacturers",
        title="Fabricantes",
        table="manufacturers",
        order_by="name",
        fields=("code", "name"),
    ),
    "ncms": EntityDefinition(
        key="ncms",
        title="NCM",
        table="ncms",
        order_by="code",
        fields=("code", "description", "national_rate", "imported_rate"),
    ),
    "cfops": EntityDefinition(
        key="cfops",
        title="CFOP",
        table="cfops",
        order_by="code",
        fields=("code", "description", "operation_type"),
    ),
    "cst-icms": EntityDefinition(
        key="cst-icms",
        title="CST ICMS",
        table="cst_icms",
        order_by="code",
        fields=("code", "description"),
    ),
    "cst-ipi": EntityDefinition(
        key="cst-ipi",
        title="CST IPI",
        table="cst_ipi",
        order_by="code",
        fields=("code", "description"),
    ),
}


def _current_user(request: Request):
    # Usa os mesmos helpers já definidos pela aplicação principal sem
    # duplicar autenticação ou autorização.
    from app.main import current_user

    return current_user(request)


def _permissions(user_id: int) -> set[str]:
    return database.permissions(user_id)


def _require(request: Request, permission: str):
    user = _current_user(request)
    if user is None:
        return None
    if permission not in _permissions(user["id"]):
        raise HTTPException(status_code=403, detail="Sem permissão")
    return user


def _context(request: Request, user, **extra: Any) -> dict[str, Any]:
    return {
        "request": request,
        "user": user,
        "permissions": _permissions(user["id"]),
        **extra,
    }


def _templates():
    from app.main import templates

    return templates


def _clean_code(value: str) -> str:
    return value.strip().upper()


def _clean_text(value: str) -> str:
    return value.strip()


@router.get("/master-data", response_class=HTMLResponse)
def master_data_page(
    request: Request,
    section: str = "manufacturers",
    error: str | None = None,
):
    user = _require(request, "master_data.read")
    if user is None:
        return RedirectResponse("/", status_code=303)

    if section not in {*ENTITIES, "warehouses"}:
        section = "manufacturers"

    with database.connect() as conn:
        companies = conn.execute(
            "SELECT id, code, legal_name, trade_name FROM companies "
            "WHERE active = 1 ORDER BY code"
        ).fetchall()

        if section == "warehouses":
            rows = conn.execute(
                """
                SELECT
                    w.*,
                    c.code AS company_code,
                    COALESCE(c.trade_name, c.legal_name) AS company_name,
                    COUNT(sl.id) AS location_count
                FROM warehouses w
                JOIN companies c ON c.id = w.company_id
                LEFT JOIN stock_locations sl ON sl.warehouse_id = w.id
                GROUP BY w.id
                ORDER BY c.code, w.code
                """
            ).fetchall()
            locations = conn.execute(
                """
                SELECT
                    sl.*,
                    w.code AS warehouse_code,
                    w.name AS warehouse_name,
                    c.code AS company_code
                FROM stock_locations sl
                JOIN warehouses w ON w.id = sl.warehouse_id
                JOIN companies c ON c.id = w.company_id
                ORDER BY c.code, w.code, sl.code
                """
            ).fetchall()
            warehouses = conn.execute(
                """
                SELECT w.id, w.code, w.name, c.code AS company_code
                FROM warehouses w
                JOIN companies c ON c.id = w.company_id
                WHERE w.active = 1
                ORDER BY c.code, w.code
                """
            ).fetchall()
            entity = None
        else:
            entity = ENTITIES[section]
            rows = conn.execute(
                f"SELECT * FROM {entity.table} ORDER BY {entity.order_by}"
            ).fetchall()
            locations = []
            warehouses = []

    return _templates().TemplateResponse(
        "master_data.html",
        _context(
            request,
            user,
            section=section,
            entity=entity,
            entities=ENTITIES,
            rows=rows,
            companies=companies,
            warehouses=warehouses,
            locations=locations,
            error=error,
        ),
    )


@router.post("/master-data/{section}")
def create_master_data(
    request: Request,
    section: str,
    code: str = Form(""),
    name: str = Form(""),
    description: str = Form(""),
    national_rate: float = Form(0),
    imported_rate: float = Form(0),
    operation_type: str = Form("ENTRADA"),
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    entity = ENTITIES.get(section)
    if entity is None:
        raise HTTPException(status_code=404, detail="Cadastro inexistente")

    values: dict[str, Any] = {
        "code": _clean_code(code),
        "name": _clean_text(name),
        "description": _clean_text(description),
        "national_rate": national_rate,
        "imported_rate": imported_rate,
        "operation_type": operation_type.strip().upper(),
    }

    if "code" in entity.fields and not values["code"]:
        return RedirectResponse(
            f"/master-data?section={section}&error=code",
            status_code=303,
        )
    if "name" in entity.fields and not values["name"]:
        return RedirectResponse(
            f"/master-data?section={section}&error=name",
            status_code=303,
        )
    if "description" in entity.fields and not values["description"]:
        return RedirectResponse(
            f"/master-data?section={section}&error=description",
            status_code=303,
        )

    columns = list(entity.fields)
    placeholders = ", ".join("?" for _ in columns)
    parameters = [values[column] for column in columns]

    try:
        with database.connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {entity.table}({', '.join(columns)}) "
                f"VALUES({placeholders})",
                parameters,
            )
            conn.commit()
            record_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return RedirectResponse(
            f"/master-data?section={section}&error=duplicate",
            status_code=303,
        )

    database.audit(
        user["id"],
        f"master_data.{section}.created",
        f"id={record_id};code={values.get('code', '')};name={values.get('name', '')}",
    )
    return RedirectResponse(
        f"/master-data?section={section}",
        status_code=303,
    )


@router.post("/master-data/{section}/{record_id}/toggle")
def toggle_master_data(
    request: Request,
    section: str,
    record_id: int,
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    entity = ENTITIES.get(section)
    if entity is None:
        raise HTTPException(status_code=404, detail="Cadastro inexistente")

    with database.connect() as conn:
        result = conn.execute(
            f"""
            UPDATE {entity.table}
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (record_id,),
        )
        conn.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Registro inexistente")

    database.audit(
        user["id"],
        f"master_data.{section}.status_changed",
        f"id={record_id}",
    )
    return RedirectResponse(
        f"/master-data?section={section}",
        status_code=303,
    )


@router.post("/master-data/warehouses")
def create_warehouse(
    request: Request,
    company_id: int = Form(...),
    code: str = Form(...),
    name: str = Form(...),
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    try:
        with database.connect() as conn:
            company = conn.execute(
                "SELECT id FROM companies WHERE id = ? AND active = 1",
                (company_id,),
            ).fetchone()
            if company is None:
                raise ValueError("Empresa inválida")

            cursor = conn.execute(
                """
                INSERT INTO warehouses(company_id, code, name)
                VALUES(?, ?, ?)
                """,
                (company_id, _clean_code(code), _clean_text(name)),
            )
            conn.commit()
            record_id = cursor.lastrowid
    except (sqlite3.IntegrityError, ValueError):
        return RedirectResponse(
            "/master-data?section=warehouses&error=warehouse",
            status_code=303,
        )

    database.audit(
        user["id"],
        "master_data.warehouse.created",
        f"id={record_id};company_id={company_id};code={_clean_code(code)}",
    )
    return RedirectResponse(
        "/master-data?section=warehouses",
        status_code=303,
    )


@router.post("/master-data/warehouses/{warehouse_id}/toggle")
def toggle_warehouse(
    request: Request,
    warehouse_id: int,
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    with database.connect() as conn:
        result = conn.execute(
            """
            UPDATE warehouses
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (warehouse_id,),
        )
        conn.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Depósito inexistente")

    database.audit(
        user["id"],
        "master_data.warehouse.status_changed",
        f"id={warehouse_id}",
    )
    return RedirectResponse(
        "/master-data?section=warehouses",
        status_code=303,
    )


@router.post("/master-data/locations")
def create_location(
    request: Request,
    warehouse_id: int = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    aisle: str = Form(""),
    rack: str = Form(""),
    level: str = Form(""),
    bin: str = Form(""),
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    try:
        with database.connect() as conn:
            warehouse = conn.execute(
                "SELECT id FROM warehouses WHERE id = ? AND active = 1",
                (warehouse_id,),
            ).fetchone()
            if warehouse is None:
                raise ValueError("Depósito inválido")

            cursor = conn.execute(
                """
                INSERT INTO stock_locations(
                    warehouse_id, code, description, aisle, rack, level, bin
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    warehouse_id,
                    _clean_code(code),
                    _clean_text(description) or None,
                    _clean_text(aisle) or None,
                    _clean_text(rack) or None,
                    _clean_text(level) or None,
                    _clean_text(bin) or None,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
    except (sqlite3.IntegrityError, ValueError):
        return RedirectResponse(
            "/master-data?section=warehouses&error=location",
            status_code=303,
        )

    database.audit(
        user["id"],
        "master_data.location.created",
        f"id={record_id};warehouse_id={warehouse_id};code={_clean_code(code)}",
    )
    return RedirectResponse(
        "/master-data?section=warehouses",
        status_code=303,
    )


@router.post("/master-data/locations/{location_id}/toggle")
def toggle_location(
    request: Request,
    location_id: int,
):
    user = _require(request, "master_data.write")
    if user is None:
        return RedirectResponse("/", status_code=303)

    with database.connect() as conn:
        result = conn.execute(
            """
            UPDATE stock_locations
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (location_id,),
        )
        conn.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Localização inexistente")

    database.audit(
        user["id"],
        "master_data.location.status_changed",
        f"id={location_id}",
    )
    return RedirectResponse(
        "/master-data?section=warehouses",
        status_code=303,
    )

# SMARTBUY_MASTER_DATA_ROUTE_PRIORITY
# FastAPI evaluates routes in declaration order. Static warehouse/location
# routes must precede the generic /master-data/{section} route.
router.routes.sort(
    key=lambda route: (
        "{" in getattr(route, "path", ""),
        getattr(route, "path", ""),
    )
)
