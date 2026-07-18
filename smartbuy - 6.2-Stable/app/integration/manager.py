from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from app import database
from app.integration.connectors import load_secrets
from app.integration.contracts import HealthSnapshot
from app.integration.registry import get_connector


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ConnectorManager:
    def test_source(self, source_id: int) -> HealthSnapshot:
        with database.connect() as conn:
            source = conn.execute(
                """
                SELECT * FROM integration_sources
                WHERE id=? AND active=1
                """,
                (source_id,),
            ).fetchone()
            if not source:
                raise ValueError("Fonte inexistente ou inativa.")

        config = json.loads(source["config_json"] or "{}")
        connector = get_connector(
            source["connector_type"],
            source["connector_version"],
        )
        started = time.perf_counter()
        result = connector.test_connection(
            config,
            load_secrets(source["secret_env_prefix"]),
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        status = "ONLINE" if result.ok else "OFFLINE"

        snapshot = HealthSnapshot(
            connector_type=source["connector_type"],
            connector_version=source["connector_version"],
            status=status,
            message=result.message,
            latency_ms=latency_ms,
            checked_at=utc_now(),
            metadata=result.metadata,
        )

        with database.connect() as conn:
            conn.execute(
                """
                INSERT INTO integration_health_snapshots(
                    source_id, connector_type, connector_version,
                    status, message, latency_ms, metadata_json,
                    checked_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    snapshot.connector_type,
                    snapshot.connector_version,
                    snapshot.status,
                    snapshot.message,
                    snapshot.latency_ms,
                    json.dumps(snapshot.metadata, ensure_ascii=False),
                    snapshot.checked_at,
                ),
            )
            conn.execute(
                """
                UPDATE integration_sources
                SET last_test_status=?,
                    last_test_message=?,
                    last_test_at=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    snapshot.status,
                    snapshot.message,
                    snapshot.checked_at,
                    source_id,
                ),
            )
            conn.commit()
        return snapshot

    def preview(
        self,
        source_id: int,
        limit: int = 50,
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 500))
        with database.connect() as conn:
            source = conn.execute(
                """
                SELECT * FROM integration_sources
                WHERE id=? AND active=1
                """,
                (source_id,),
            ).fetchone()
            if not source:
                raise ValueError("Fonte inexistente ou inativa.")

        config = json.loads(source["config_json"] or "{}")
        connector = get_connector(
            source["connector_type"],
            source["connector_version"],
        )
        result = connector.read(
            config,
            load_secrets(source["secret_env_prefix"]),
            cursor=None,
            limit=limit,
        )
        return {
            "source_id": source_id,
            "connector_type": source["connector_type"],
            "connector_version": source["connector_version"],
            "rows": result.rows,
            "rows_count": len(result.rows),
            "next_cursor": result.next_cursor,
            "warnings": result.warnings,
            "config_hash": _config_hash(config),
        }

    def record_event(
        self,
        *,
        event_type: str,
        source_id: int | None,
        severity: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with database.connect() as conn:
            event_id = conn.execute(
                """
                INSERT INTO integration_events(
                    event_type, source_id, severity,
                    message, payload_json
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    source_id,
                    severity,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            ).lastrowid
            conn.commit()
        return int(event_id)


connector_manager = ConnectorManager()
