from __future__ import annotations

from app import database


def apply_eip_schema() -> None:
    with database.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS integration_health_snapshots(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                connector_type TEXT NOT NULL,
                connector_version TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                latency_ms INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                checked_at TEXT NOT NULL,
                FOREIGN KEY(source_id)
                    REFERENCES integration_sources(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_eip_health_source_checked
                ON integration_health_snapshots(
                    source_id, checked_at DESC
                );

            CREATE TABLE IF NOT EXISTS integration_cache_entries(
                namespace TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(namespace, cache_key)
            );

            CREATE INDEX IF NOT EXISTS ix_eip_cache_expiry
                ON integration_cache_entries(expires_at);

            CREATE TABLE IF NOT EXISTS integration_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source_id INTEGER,
                severity TEXT NOT NULL DEFAULT 'INFO',
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_id)
                    REFERENCES integration_sources(id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS ix_eip_events_created
                ON integration_events(created_at DESC);

            CREATE INDEX IF NOT EXISTS ix_eip_events_source
                ON integration_events(source_id, created_at DESC);
            """
        )
        conn.commit()
