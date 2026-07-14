from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integration.models import REQUIRED_FIELDS


def _issue(
    severity: str,
    code: str,
    message: str,
    field: str | None = None,
) -> dict[str, str | None]:
    return {
        "severity": severity,
        "rule_code": code,
        "field_name": field,
        "message": message,
    }


def evaluate(
    entity_type: str,
    payload: dict[str, Any],
) -> list[dict[str, str | None]]:
    entity = entity_type.upper()
    issues = []

    for field in REQUIRED_FIELDS.get(entity, set()):
        if payload.get(field) in (None, ""):
            issues.append(
                _issue(
                    "ERROR",
                    "REQUIRED_FIELD",
                    f"Campo obrigatório ausente: {field}",
                    field,
                )
            )

    for field in (
        "current_stock",
        "reserved_stock",
        "on_order_stock",
        "quantity",
        "unit_cost",
    ):
        value = payload.get(field)
        if value is not None:
            try:
                number = float(value)
            except (TypeError, ValueError):
                issues.append(
                    _issue(
                        "ERROR",
                        "INVALID_NUMBER",
                        f"Valor numérico inválido em {field}",
                        field,
                    )
                )
                continue
            if number < 0:
                severity = "WARNING" if field == "current_stock" else "ERROR"
                issues.append(
                    _issue(
                        severity,
                        "NEGATIVE_VALUE",
                        f"Valor negativo em {field}",
                        field,
                    )
                )

    for field in ("movement_date", "purchase_date"):
        value = payload.get(field)
        if value:
            try:
                datetime.fromisoformat(str(value)[:10])
            except ValueError:
                issues.append(
                    _issue(
                        "ERROR",
                        "INVALID_DATE",
                        f"Data inválida em {field}; use AAAA-MM-DD",
                        field,
                    )
                )

    if entity == "PRODUCT" and payload.get("unit_cost") == 0:
        issues.append(
            _issue(
                "WARNING",
                "ZERO_COST",
                "Produto com custo zerado",
                "unit_cost",
            )
        )

    return issues
