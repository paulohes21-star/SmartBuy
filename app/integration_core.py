from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app import database
from app.decision_explain import ENGINE_VERSION, explain
from app.integration.connectors import connector_registry, load_secrets
from app.integration.mapper import normalize_record, validate_mapping
from app.integration.quality import evaluate
from app.integration.sync_engine import execute_sync, promote_run
from app.purchasing_engine import calculate_recommendations


router = APIRouter(prefix="/integration-core", tags=["integration-core"])


CONNECTOR_CONFIG_TEMPLATES = {
    "CSV": {
        "path": r"C:\dados\estoque.csv",
        "delimiter": ";",
        "encoding": "utf-8-sig",
    },
    "EXCEL": {
        "path": r"C:\dados\estoque.xlsx",
        "sheet": "Estoque",
    },
    "REST": {
        "url": "https://erp.exemplo/api/estoque",
        "records_path": "data",
    },
    "POSTGRESQL": {
        "host": "servidor",
        "port": 5432,
        "database": "erp",
        "query": "SELECT * FROM estoque",
    },
    "MYSQL": {
        "host": "servidor",
        "port": 3306,
        "database": "erp",
        "query": "SELECT * FROM estoque",
    },
    "SQLSERVER": {
        "host": "servidor",
        "port": 1433,
        "database": "erp",
        "driver": "ODBC Driver 18 for SQL Server",
        "query": "SELECT * FROM estoque",
    },
    "ORACLE": {
        "host": "servidor",
        "port": 1521,
        "database": "ORCL",
        "query": "SELECT * FROM ESTOQUE",
    },
    "FIREBIRD": {
        "host": "servidor",
        "port": 3050,
        "database": r"C:\ERP\DADOS.FDB",
        "query": "SELECT * FROM ESTOQUE",
    },
}

ENTITY_MAPPING_TEMPLATES = {
    "PRODUCT": {
        "internal_code": "COD_PRODUTO",
        "description": "DESCRICAO",
        "unit_code": "UNIDADE",
        "unit_cost": "CUSTO_MEDIO",
    },
    "INVENTORY": {
        "product_code": "COD_PRODUTO",
        "company_code": "COD_EMPRESA",
        "current_stock": "ESTOQUE_ATUAL",
        "reserved_stock": "ESTOQUE_RESERVADO",
        "on_order_stock": "ESTOQUE_PEDIDO",
    },
    "CONSUMPTION": {
        "product_code": "COD_PRODUTO",
        "company_code": "COD_EMPRESA",
        "quantity": "QUANTIDADE",
        "movement_date": "DATA_MOVIMENTO",
        "reference_number": "DOCUMENTO",
    },
    "PURCHASE": {
        "product_code": "COD_PRODUTO",
        "company_code": "COD_EMPRESA",
        "unit_cost": "CUSTO_UNITARIO",
        "purchase_date": "DATA_COMPRA",
        "reference_number": "DOCUMENTO",
        "supplier_code": "COD_FORNECEDOR",
    },
    "SUPPLIER": {
        "supplier_code": "COD_FORNECEDOR",
        "legal_name": "RAZAO_SOCIAL",
        "trade_name": "NOME_FANTASIA",
        "tax_id": "CNPJ",
    },
    "OPEN_ORDER": {
        "product_code": "COD_PRODUTO",
        "company_code": "COD_EMPRESA",
        "quantity": "QUANTIDADE",
        "order_number": "NUMERO_PEDIDO",
        "supplier_code": "COD_FORNECEDOR",
    },
}


def _main():
    import app.main as main
    return main


def _user(request: Request, permission: str):
    return _main().require(request, permission)


def _context(request: Request, user, **extra: Any):
    return _main().base_context(request, user, **extra)


def _templates():
    return _main().templates


@router.get("", response_class=HTMLResponse)
def integration_dashboard(request: Request):
    user = _user(request, "integration.read")
    if not user:
        return _main().login_redirect()

    with database.connect() as conn:
        sources = conn.execute(
            """
            SELECT s.*,
                   (SELECT COUNT(*) FROM integration_mappings m
                    WHERE m.source_id=s.id AND m.active=1) mapping_count
            FROM integration_sources s
            ORDER BY s.name
            """
        ).fetchall()
        mappings = conn.execute(
            """
            SELECT m.*, s.name source_name
            FROM integration_mappings m
            JOIN integration_sources s ON s.id=m.source_id
            ORDER BY m.id DESC
            """
        ).fetchall()
        runs = conn.execute(
            """
            SELECT r.*, s.name source_name, m.name mapping_name
            FROM integration_sync_runs r
            JOIN integration_sources s ON s.id=r.source_id
            LEFT JOIN integration_mappings m ON m.id=r.mapping_id
            ORDER BY r.id DESC LIMIT 50
            """
        ).fetchall()
        issues = conn.execute(
            """
            SELECT q.*, s.source_key
            FROM integration_quality_issues q
            JOIN integration_staging_records s
              ON s.id=q.staging_record_id
            ORDER BY q.id DESC LIMIT 100
            """
        ).fetchall()
        connectors = conn.execute(
            """
            SELECT * FROM integration_connector_registry
            WHERE active=1 ORDER BY display_name
            """
        ).fetchall()

        quality_summary = conn.execute(
            """
            SELECT
                COUNT(*) total_issues,
                SUM(CASE WHEN severity='ERROR' THEN 1 ELSE 0 END) errors,
                SUM(CASE WHEN severity='WARNING' THEN 1 ELSE 0 END) warnings
            FROM integration_quality_issues
            """
        ).fetchone()
        run_summary = conn.execute(
            """
            SELECT
                COALESCE(SUM(rows_read), 0) rows_read,
                COALESCE(SUM(rows_valid), 0) rows_valid,
                COALESCE(SUM(rows_invalid), 0) rows_invalid,
                COALESCE(SUM(rows_promoted), 0) rows_promoted
            FROM integration_sync_runs
            """
        ).fetchone()

    return _templates().TemplateResponse(
        "integration_core.html",
        _context(
            request,
            user,
            sources=sources,
            mappings=mappings,
            runs=runs,
            issues=issues,
            connectors=connectors,
            quality_summary=quality_summary,
            run_summary=run_summary,
            connector_templates=CONNECTOR_CONFIG_TEMPLATES,
            mapping_templates=ENTITY_MAPPING_TEMPLATES,
        ),
    )


@router.post("/sources")
def create_source(
    request: Request,
    name: str = Form(...),
    connector_type: str = Form(...),
    entity_type: str = Form(...),
    config_json: str = Form("{}"),
    secret_env_prefix: str = Form(""),
):
    user = _user(request, "integration.configure")
    if not user:
        return _main().login_redirect()

    connector_type = connector_type.strip().upper()
    entity_type = entity_type.strip().upper()
    if connector_type not in connector_registry:
        raise HTTPException(422, "Conector não suportado")
    try:
        config = json.loads(config_json or "{}")
        if not isinstance(config, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "Configuração JSON inválida")

    with database.connect() as conn:
        source_id = conn.execute(
            """
            INSERT INTO integration_sources(
                name, connector_type, connector_version,
                entity_type, config_json, secret_env_prefix,
                created_by
            ) VALUES(?, ?, '1.0.0', ?, ?, ?, ?)
            """,
            (
                name.strip(),
                connector_type,
                entity_type,
                json.dumps(config, ensure_ascii=False),
                secret_env_prefix.strip().upper() or None,
                user["id"],
            ),
        ).lastrowid
        conn.commit()

    database.audit(
        user["id"],
        "integration.source.created",
        f"id={source_id};tipo={connector_type};entidade={entity_type}",
    )
    return RedirectResponse("/integration-core", status_code=303)


@router.post("/sources/{source_id}/test")
def test_source(request: Request, source_id: int):
    user = _user(request, "integration.configure")
    if not user:
        return _main().login_redirect()

    with database.connect() as conn:
        source = conn.execute(
            "SELECT * FROM integration_sources WHERE id=?",
            (source_id,),
        ).fetchone()
        if not source:
            raise HTTPException(404, "Fonte não encontrada")

    connector = connector_registry[source["connector_type"]]
    result = connector.test_connection(
        json.loads(source["config_json"]),
        load_secrets(source["secret_env_prefix"]),
    )

    with database.connect() as conn:
        conn.execute(
            """
            UPDATE integration_sources
            SET last_test_status=?,
                last_test_message=?,
                last_test_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            ("OK" if result.ok else "ERROR", result.message, source_id),
        )
        conn.commit()

    database.audit(
        user["id"],
        "integration.source.tested",
        f"id={source_id};ok={result.ok}",
    )
    return RedirectResponse(
        f"/integration-core?test={'ok' if result.ok else 'error'}",
        status_code=303,
    )


@router.post("/mappings")
def create_mapping(
    request: Request,
    source_id: int = Form(...),
    name: str = Form(...),
    mapping_json: str = Form(...),
):
    user = _user(request, "integration.configure")
    if not user:
        return _main().login_redirect()

    with database.connect() as conn:
        source = conn.execute(
            "SELECT * FROM integration_sources WHERE id=?",
            (source_id,),
        ).fetchone()
        if not source:
            raise HTTPException(404, "Fonte não encontrada")

    try:
        mapping = json.loads(mapping_json)
        if not isinstance(mapping, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "Mapeamento JSON inválido")

    errors = validate_mapping(source["entity_type"], mapping)
    if errors:
        raise HTTPException(422, "; ".join(errors))

    with database.connect() as conn:
        current = conn.execute(
            """
            SELECT COALESCE(MAX(version), 0) current_version
            FROM integration_mappings
            WHERE source_id=? AND name=?
            """,
            (source_id, name.strip()),
        ).fetchone()["current_version"]
        mapping_id = conn.execute(
            """
            INSERT INTO integration_mappings(
                source_id, name, entity_type, version,
                mapping_json, created_by
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                name.strip(),
                source["entity_type"],
                current + 1,
                json.dumps(mapping, ensure_ascii=False),
                user["id"],
            ),
        ).lastrowid
        conn.commit()

    database.audit(
        user["id"],
        "integration.mapping.created",
        f"id={mapping_id};fonte={source_id};versao={current + 1}",
    )
    return RedirectResponse("/integration-core", status_code=303)


@router.post("/sync")
def run_sync(
    request: Request,
    source_id: int = Form(...),
    mapping_id: int = Form(...),
    mode: str = Form("INCREMENTAL"),
):
    user = _user(request, "integration.execute")
    if not user:
        return _main().login_redirect()
    try:
        run_id = execute_sync(
            source_id=source_id,
            mapping_id=mapping_id,
            user_id=user["id"],
            mode=mode,
        )
    except Exception as exc:
        database.audit(
            user["id"],
            "integration.sync.failed",
            f"fonte={source_id};erro={exc}",
        )
        return RedirectResponse(
            "/integration-core?sync=error",
            status_code=303,
        )

    database.audit(
        user["id"],
        "integration.sync.staged",
        f"run={run_id};fonte={source_id}",
    )
    return RedirectResponse(
        f"/integration-core?sync=ok&run={run_id}",
        status_code=303,
    )


@router.post("/runs/{run_id}/promote")
def promote(request: Request, run_id: int):
    user = _user(request, "integration.promote")
    if not user:
        return _main().login_redirect()
    result = promote_run(run_id, user["id"])
    database.audit(
        user["id"],
        "integration.run.promoted",
        f"run={run_id};promovidos={result['promoted']};"
        f"ignorados={result['skipped']}",
    )
    return RedirectResponse(
        f"/integration-core?promote=ok&count={result['promoted']}",
        status_code=303,
    )


@router.get("/api/decisions/today")
def decisions_today(
    request: Request,
    company_id: int | None = None,
):
    user = _user(request, "decision_api.read")
    if not user:
        raise HTTPException(401, "Não autenticado")

    recommendations = calculate_recommendations(company_id=company_id)
    items = []
    with database.connect() as conn:
        for recommendation in recommendations:
            explanation = explain(recommendation)
            if recommendation.suggested_quantity > 0:
                conn.execute(
                    """
                    INSERT INTO decision_explanations(
                        product_id, company_id, recommendation_json,
                        explanation_text, engine_version
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        recommendation.product_id,
                        recommendation.company_id,
                        json.dumps(
                            recommendation.to_dict(),
                            ensure_ascii=False,
                            default=str,
                        ),
                        explanation,
                        ENGINE_VERSION,
                    ),
                )
            items.append(
                {
                    **recommendation.to_dict(),
                    "explanation": explanation,
                    "engine_version": ENGINE_VERSION,
                }
            )
        conn.commit()

    return JSONResponse(
        {
            "question": "O que comprar hoje?",
            "company_id": company_id,
            "recommendations": [
                item for item in items
                if item["suggested_quantity"] > 0
            ],
            "total_analyzed": len(items),
        }
    )



@router.get("/api/templates")
def integration_templates(request: Request):
    user = _user(request, "integration.read")
    if not user:
        raise HTTPException(401, "Não autenticado")
    return {
        "connectors": CONNECTOR_CONFIG_TEMPLATES,
        "entities": ENTITY_MAPPING_TEMPLATES,
    }


@router.post("/api/json/validate")
async def validate_json_payload(request: Request):
    user = _user(request, "integration.configure")
    if not user:
        raise HTTPException(401, "Não autenticado")
    payload = await request.json()
    raw_value = payload.get("value", "{}")
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}.",
                "line": exc.lineno,
                "column": exc.colno,
            },
            status_code=422,
        )
    if not isinstance(decoded, dict):
        return JSONResponse(
            {"ok": False, "message": "O conteúdo deve ser um objeto JSON."},
            status_code=422,
        )
    return {
        "ok": True,
        "message": "JSON válido.",
        "formatted": json.dumps(decoded, ensure_ascii=False, indent=2),
    }


@router.post("/api/mapping/validate")
async def validate_mapping_payload(request: Request):
    user = _user(request, "integration.configure")
    if not user:
        raise HTTPException(401, "Não autenticado")
    payload = await request.json()
    entity_type = str(payload.get("entity_type", "")).upper()
    try:
        mapping = json.loads(payload.get("mapping_json", "{}"))
    except json.JSONDecodeError as exc:
        return JSONResponse(
            {
                "ok": False,
                "errors": [
                    f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}."
                ],
            },
            status_code=422,
        )
    if not isinstance(mapping, dict):
        return JSONResponse(
            {"ok": False, "errors": ["O mapeamento deve ser um objeto JSON."]},
            status_code=422,
        )
    errors = validate_mapping(entity_type, mapping)
    return {
        "ok": not errors,
        "errors": errors,
        "formatted": json.dumps(mapping, ensure_ascii=False, indent=2),
    }


@router.post("/api/source/preview")
async def preview_source(request: Request):
    user = _user(request, "integration.configure")
    if not user:
        raise HTTPException(401, "Não autenticado")

    payload = await request.json()
    connector_type = str(payload.get("connector_type", "")).strip().upper()
    entity_type = str(payload.get("entity_type", "")).strip().upper()
    secret_env_prefix = str(payload.get("secret_env_prefix", "")).strip()
    limit = min(max(int(payload.get("limit", 5)), 1), 20)

    if connector_type not in connector_registry:
        raise HTTPException(422, "Conector não suportado")

    try:
        config = json.loads(payload.get("config_json", "{}"))
        mapping = json.loads(payload.get("mapping_json", "{}"))
    except json.JSONDecodeError as exc:
        return JSONResponse(
            {
                "ok": False,
                "message": f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}.",
            },
            status_code=422,
        )

    if not isinstance(config, dict) or not isinstance(mapping, dict):
        raise HTTPException(422, "Configuração e mapeamento devem ser objetos JSON")

    mapping_errors = validate_mapping(entity_type, mapping)
    if mapping_errors:
        return JSONResponse(
            {"ok": False, "message": "; ".join(mapping_errors)},
            status_code=422,
        )

    connector = connector_registry[connector_type]
    test_result = connector.test_connection(
        config,
        load_secrets(secret_env_prefix or None),
    )
    if not test_result.ok:
        return JSONResponse(
            {
                "ok": False,
                "message": test_result.message,
                "connection": {"ok": False},
            },
            status_code=422,
        )

    try:
        read_result = connector.read(
            config,
            load_secrets(secret_env_prefix or None),
            limit=limit,
        )
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "message": str(exc)},
            status_code=422,
        )

    preview = []
    total_valid = 0
    total_invalid = 0
    for raw_record in read_result.rows:
        try:
            canonical = normalize_record(entity_type, raw_record, mapping)
            record_issues = evaluate(entity_type, canonical)
        except Exception as exc:
            canonical = {}
            record_issues = [{
                "severity": "ERROR",
                "rule_code": "NORMALIZATION_ERROR",
                "field_name": None,
                "message": str(exc),
            }]

        has_error = any(
            issue.get("severity") == "ERROR"
            for issue in record_issues
        )
        if has_error:
            total_invalid += 1
        else:
            total_valid += 1

        preview.append({
            "raw": raw_record,
            "canonical": canonical,
            "issues": record_issues,
            "status": "INVALID" if has_error else "VALID",
        })

    return {
        "ok": True,
        "message": test_result.message,
        "connection": {
            "ok": True,
            "metadata": test_result.metadata,
        },
        "summary": {
            "rows": len(preview),
            "valid": total_valid,
            "invalid": total_invalid,
        },
        "preview": preview,
    }
