from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_ENTITIES = {
    "PRODUCT",
    "INVENTORY",
    "CONSUMPTION",
    "PURCHASE",
    "SUPPLIER",
    "OPEN_ORDER",
}

REQUIRED_FIELDS = {
    "PRODUCT": {"internal_code", "description", "unit_code"},
    "INVENTORY": {
        "product_code",
        "company_code",
        "current_stock",
    },
    "CONSUMPTION": {
        "product_code",
        "company_code",
        "quantity",
        "movement_date",
    },
    "PURCHASE": {
        "product_code",
        "company_code",
        "unit_cost",
        "purchase_date",
    },
    "SUPPLIER": {"supplier_code", "legal_name"},
    "OPEN_ORDER": {
        "product_code",
        "company_code",
        "quantity",
    },
}


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadResult:
    rows: list[dict[str, Any]]
    next_cursor: str | None = None
    warnings: list[str] = field(default_factory=list)
