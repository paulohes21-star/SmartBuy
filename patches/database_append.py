# SMARTBUY_SPRINT_3_MASTER_DATA
# Extensão incremental da Sprint 2. Mantém a função init_db original e adiciona
# as tabelas e permissões dos cadastros mestres.

_MASTER_DATA_PERMISSIONS = {
    "master_data.read": "Consultar cadastros mestres",
    "master_data.write": "Criar e alterar cadastros mestres",
}

_MASTER_DATA_ROLE_ACCESS = {
    "ADMIN": {"master_data.read", "master_data.write"},
    "MANAGER": {"master_data.read", "master_data.write"},
    "VIEWER": {"master_data.read"},
}


def init_master_data_schema() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS manufacturers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ncms(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                description TEXT NOT NULL,
                national_rate REAL NOT NULL DEFAULT 0,
                imported_rate REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cfops(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                description TEXT NOT NULL,
                operation_type TEXT NOT NULL DEFAULT 'ENTRADA',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cst_icms(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                description TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cst_ipi(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                description TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS warehouses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                code TEXT NOT NULL COLLATE NOCASE,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, code),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_warehouses_company
                ON warehouses(company_id);

            CREATE TABLE IF NOT EXISTS stock_locations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_id INTEGER NOT NULL,
                code TEXT NOT NULL COLLATE NOCASE,
                description TEXT,
                aisle TEXT,
                rack TEXT,
                level TEXT,
                bin TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(warehouse_id, code),
                FOREIGN KEY(warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_stock_locations_warehouse
                ON stock_locations(warehouse_id);
            """
        )

        for code, description in _MASTER_DATA_PERMISSIONS.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO permissions(code, description)
                VALUES(?, ?)
                """,
                (code, description),
            )

        for role_code, permission_codes in _MASTER_DATA_ROLE_ACCESS.items():
            role = conn.execute(
                "SELECT id FROM roles WHERE code = ?",
                (role_code,),
            ).fetchone()
            if role is None:
                continue

            for permission_code in permission_codes:
                permission = conn.execute(
                    "SELECT id FROM permissions WHERE code = ?",
                    (permission_code,),
                ).fetchone()
                if permission is None:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO role_permissions(role_id, permission_id)
                    VALUES(?, ?)
                    """,
                    (role["id"], permission["id"]),
                )

        conn.commit()


_sprint2_init_db = init_db


def init_db() -> None:
    _sprint2_init_db()
    init_master_data_schema()
