# SMARTBUY_SPRINT_6_INTEGRATION_CORE
def init_integration_core_schema() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS integration_sources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                connector_type TEXT NOT NULL,
                connector_version TEXT NOT NULL DEFAULT '1.0.0',
                entity_type TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                read_only INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                secret_env_prefix TEXT,
                last_test_status TEXT,
                last_test_message TEXT,
                last_test_at TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS integration_mappings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                mapping_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_id, name, version),
                FOREIGN KEY(source_id) REFERENCES integration_sources(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS integration_sync_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                mapping_id INTEGER,
                mode TEXT NOT NULL DEFAULT 'INCREMENTAL',
                status TEXT NOT NULL DEFAULT 'RUNNING',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                duration_ms INTEGER,
                rows_read INTEGER NOT NULL DEFAULT 0,
                rows_staged INTEGER NOT NULL DEFAULT 0,
                rows_valid INTEGER NOT NULL DEFAULT 0,
                rows_invalid INTEGER NOT NULL DEFAULT 0,
                rows_promoted INTEGER NOT NULL DEFAULT 0,
                errors_count INTEGER NOT NULL DEFAULT 0,
                warnings_count INTEGER NOT NULL DEFAULT 0,
                cursor_value TEXT,
                error_message TEXT,
                created_by INTEGER,
                FOREIGN KEY(source_id) REFERENCES integration_sources(id),
                FOREIGN KEY(mapping_id) REFERENCES integration_mappings(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS integration_staging_records(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                source_key TEXT,
                source_hash TEXT NOT NULL,
                source_payload_json TEXT NOT NULL,
                canonical_payload_json TEXT NOT NULL,
                quality_status TEXT NOT NULL DEFAULT 'PENDING',
                promotion_status TEXT NOT NULL DEFAULT 'PENDING',
                promoted_entity_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                promoted_at TEXT,
                UNIQUE(source_id, entity_type, source_hash),
                FOREIGN KEY(run_id) REFERENCES integration_sync_runs(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(source_id) REFERENCES integration_sources(id)
            );

            CREATE INDEX IF NOT EXISTS ix_staging_run_status
                ON integration_staging_records(
                    run_id, quality_status, promotion_status
                );

            CREATE TABLE IF NOT EXISTS integration_quality_issues(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staging_record_id INTEGER NOT NULL,
                run_id INTEGER NOT NULL,
                severity TEXT NOT NULL,
                rule_code TEXT NOT NULL,
                field_name TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(staging_record_id)
                    REFERENCES integration_staging_records(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(run_id) REFERENCES integration_sync_runs(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_quality_run
                ON integration_quality_issues(run_id, severity);

            CREATE TABLE IF NOT EXISTS integration_sync_state(
                source_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                cursor_value TEXT,
                last_successful_run_id INTEGER,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(source_id, entity_type),
                FOREIGN KEY(source_id) REFERENCES integration_sources(id),
                FOREIGN KEY(last_successful_run_id)
                    REFERENCES integration_sync_runs(id)
            );

            CREATE TABLE IF NOT EXISTS integration_connector_registry(
                connector_type TEXT NOT NULL,
                version TEXT NOT NULL,
                display_name TEXT NOT NULL,
                capabilities_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(connector_type, version)
            );

            CREATE TABLE IF NOT EXISTS decision_explanations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                recommendation_json TEXT NOT NULL,
                explanation_text TEXT NOT NULL,
                engine_version TEXT NOT NULL DEFAULT '1.0.0',
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(company_id) REFERENCES companies(id)
            );
            """
        )

        connectors = [
            (
                "CSV",
                "1.0.0",
                "Arquivo CSV",
                '{"preview":true,"sync":true,"read_only":true}',
            ),
            (
                "EXCEL",
                "1.0.0",
                "Arquivo Excel",
                '{"preview":true,"sync":true,"read_only":true}',
            ),
            (
                "SQLSERVER",
                "1.0.0",
                "Microsoft SQL Server",
                '{"test":true,"sync":true,"driver":"pyodbc"}',
            ),
            (
                "POSTGRESQL",
                "1.0.0",
                "PostgreSQL",
                '{"test":true,"sync":true,"driver":"psycopg"}',
            ),
            (
                "MYSQL",
                "1.0.0",
                "MySQL",
                '{"test":true,"sync":true,"driver":"mysql-connector"}',
            ),
            (
                "FIREBIRD",
                "1.0.0",
                "Firebird",
                '{"test":true,"sync":true,"driver":"firebird-driver"}',
            ),
            (
                "ORACLE",
                "1.0.0",
                "Oracle",
                '{"test":true,"sync":true,"driver":"oracledb"}',
            ),
            (
                "REST",
                "1.0.0",
                "API REST",
                '{"test":true,"sync":true,"read_only":true}',
            ),
        ]
        for connector in connectors:
            conn.execute(
                """
                INSERT OR IGNORE INTO integration_connector_registry(
                    connector_type, version, display_name, capabilities_json
                ) VALUES(?, ?, ?, ?)
                """,
                connector,
            )

        permissions = {
            "integration.read": "Consultar integrações e sincronizações",
            "integration.configure": "Configurar fontes e mapeamentos",
            "integration.execute": "Executar sincronizações",
            "integration.promote": "Promover dados validados",
            "decision_api.read": "Consultar API interna de decisões",
        }
        for code, description in permissions.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO permissions(code, description)
                VALUES(?, ?)
                """,
                (code, description),
            )
            conn.execute(
                "UPDATE permissions SET description=? WHERE code=?",
                (description, code),
            )

        assignments = {
            "ADMIN": set(permissions),
            "MANAGER": set(permissions),
            "VIEWER": {"integration.read", "decision_api.read"},
        }
        for role_code, codes in assignments.items():
            role = conn.execute(
                "SELECT id FROM roles WHERE code=?",
                (role_code,),
            ).fetchone()
            if not role:
                continue
            for code in codes:
                permission = conn.execute(
                    "SELECT id FROM permissions WHERE code=?",
                    (code,),
                ).fetchone()
                if permission:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO role_permissions(
                            role_id, permission_id
                        ) VALUES(?, ?)
                        """,
                        (role["id"], permission["id"]),
                    )
        conn.commit()


_sprint5_or_previous_init_db = init_db


def init_db() -> None:
    _sprint5_or_previous_init_db()
    init_integration_core_schema()
