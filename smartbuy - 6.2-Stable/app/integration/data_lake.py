from __future__ import annotations

import json
from typing import Any

from app import database


def query_staging(
    *,
    entity_type: str | None = None,
    quality_status: str | None = None,
    promotion_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    conditions = []
    values: list[Any] = []

    if entity_type:
        conditions.append("entity_type=?")
        values.append(entity_type.upper())
    if quality_status:
        conditions.append("quality_status=?")
        values.append(quality_status.upper())
    if promotion_status:
        conditions.append("promotion_status=?")
        values.append(promotion_status.upper())

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    values.append(limit)

    with database.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, run_id, source_id, entity_type,
                   source_key, canonical_payload_json,
                   quality_status, promotion_status,
                   created_at
            FROM integration_staging_records
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            values,
        ).fetchall()

    return [
        {
            **dict(row),
            "canonical_payload": json.loads(
                row["canonical_payload_json"]
            ),
        }
        for row in rows
    ]
