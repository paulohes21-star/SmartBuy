from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.integration.data_lake import query_staging
from app.integration.manager import connector_manager
from app.integration.registry import descriptors


router = APIRouter(
    prefix="/integration-core/api",
    tags=["integration-eip"],
)


def _main():
    import app.main as main
    return main


def _require(request: Request, permission: str):
    return _main().require(request, permission)


@router.get("/connectors")
def list_connectors(request: Request):
    user = _require(request, "integration.read")
    if not user:
        return JSONResponse({"detail": "Não autenticado"}, status_code=401)

    return {
        "items": [
            {
                "connector_type": item.connector_type,
                "version": item.version,
                "display_name": item.display_name,
                "capabilities": sorted(
                    capability.value
                    for capability in item.capabilities
                ),
            }
            for item in descriptors()
        ]
    }


@router.post("/sources/{source_id}/health")
def test_source_health(request: Request, source_id: int):
    user = _require(request, "integration.execute")
    if not user:
        return JSONResponse({"detail": "Não autenticado"}, status_code=401)

    try:
        snapshot = connector_manager.test_source(source_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc))

    return {
        "source_id": source_id,
        "status": snapshot.status,
        "message": snapshot.message,
        "latency_ms": snapshot.latency_ms,
        "checked_at": snapshot.checked_at,
        "metadata": snapshot.metadata,
    }


@router.get("/sources/{source_id}/preview")
def preview_source(
    request: Request,
    source_id: int,
    limit: int = Query(50, ge=1, le=500),
):
    user = _require(request, "integration.read")
    if not user:
        return JSONResponse({"detail": "Não autenticado"}, status_code=401)

    try:
        return connector_manager.preview(source_id, limit=limit)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc))


@router.get("/staging")
def staging_records(
    request: Request,
    entity_type: str | None = None,
    quality_status: str | None = None,
    promotion_status: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    user = _require(request, "integration.read")
    if not user:
        return JSONResponse({"detail": "Não autenticado"}, status_code=401)

    return {
        "items": query_staging(
            entity_type=entity_type,
            quality_status=quality_status,
            promotion_status=promotion_status,
            limit=limit,
        )
    }
