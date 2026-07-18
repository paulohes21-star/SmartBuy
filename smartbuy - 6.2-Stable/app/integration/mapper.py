from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.integration.models import REQUIRED_FIELDS, SUPPORTED_ENTITIES


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def normalize_record(
    entity_type: str,
    source_record: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, Any]:
    entity = entity_type.upper()
    if entity not in SUPPORTED_ENTITIES:
        raise ValueError(f"Entidade não suportada: {entity}")

    canonical = {}
    for canonical_field, source_field in mapping.items():
        canonical[canonical_field] = clean_value(
            source_record.get(source_field)
        )

    for field in (
        "internal_code",
        "product_code",
        "company_code",
        "supplier_code",
        "unit_code",
    ):
        if canonical.get(field) is not None:
            canonical[field] = str(canonical[field]).strip().upper()

    for field in (
        "current_stock",
        "reserved_stock",
        "on_order_stock",
        "quantity",
        "unit_cost",
    ):
        if canonical.get(field) is not None:
            canonical[field] = float(canonical[field])

    return canonical


def validate_mapping(entity_type: str, mapping: dict[str, str]) -> list[str]:
    entity = entity_type.upper()
    required = REQUIRED_FIELDS.get(entity, set())
    missing = sorted(field for field in required if not mapping.get(field))
    return [f"Campo obrigatório não mapeado: {field}" for field in missing]


def record_hash(
    source_id: int,
    entity_type: str,
    source_record: dict[str, Any],
) -> str:
    payload = json.dumps(
        {
            "source_id": source_id,
            "entity_type": entity_type,
            "record": source_record,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_key(entity_type: str, canonical: dict[str, Any]) -> str | None:
    keys = {
        "PRODUCT": ("internal_code",),
        "INVENTORY": ("company_code", "product_code"),
        "CONSUMPTION": (
            "company_code",
            "product_code",
            "movement_date",
            "reference_number",
        ),
        "PURCHASE": (
            "company_code",
            "product_code",
            "purchase_date",
            "reference_number",
        ),
        "SUPPLIER": ("supplier_code",),
        "OPEN_ORDER": ("company_code", "product_code", "order_number"),
    }.get(entity_type.upper(), ())
    values = [canonical.get(key) for key in keys]
    if not values or any(value in (None, "") for value in values):
        return None
    return "|".join(str(value) for value in values)
