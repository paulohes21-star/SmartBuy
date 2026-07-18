from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app import database


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def set_cache(
    *,
    namespace: str,
    cache_key: str,
    payload: Any,
    ttl_seconds: int,
) -> None:
    ttl_seconds = max(1, min(ttl_seconds, 86400))
    expires_at = (
        utc_now() + timedelta(seconds=ttl_seconds)
    ).isoformat()

    with database.connect() as conn:
        conn.execute(
            """
            INSERT INTO integration_cache_entries(
                namespace, cache_key, payload_json,
                expires_at, updated_at
            ) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(namespace, cache_key) DO UPDATE SET
                payload_json=excluded.payload_json,
                expires_at=excluded.expires_at,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                namespace,
                cache_key,
                json.dumps(payload, ensure_ascii=False, default=str),
                expires_at,
            ),
        )
        conn.commit()


def get_cache(
    *,
    namespace: str,
    cache_key: str,
) -> Any | None:
    with database.connect() as conn:
        row = conn.execute(
            """
            SELECT payload_json, expires_at
            FROM integration_cache_entries
            WHERE namespace=? AND cache_key=?
            """,
            (namespace, cache_key),
        ).fetchone()

        if not row:
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= utc_now():
            conn.execute(
                """
                DELETE FROM integration_cache_entries
                WHERE namespace=? AND cache_key=?
                """,
                (namespace, cache_key),
            )
            conn.commit()
            return None

    return json.loads(row["payload_json"])


def purge_expired() -> int:
    now = utc_now().isoformat()
    with database.connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM integration_cache_entries
            WHERE expires_at<=?
            """,
            (now,),
        )
        conn.commit()
        return int(cursor.rowcount)
