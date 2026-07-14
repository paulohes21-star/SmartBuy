import sqlite3
from pathlib import Path
from datetime import datetime

from app.security import hash_password

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "data" / "smartbuy.db"

ROLE_PERMISSIONS = {
    "ADMIN": {
        "companies.read", "companies.write",
        "users.read", "users.write", "audit.read",
        "catalog.read", "catalog.write", "catalog.import", "catalog.export",
        "inventory.read", "inventory.write", "history.read",
    },
    "MANAGER": {
        "companies.read", "companies.write", "users.read",
        "catalog.read", "catalog.write", "catalog.import", "catalog.export",
        "inventory.read", "inventory.write", "history.read",
    },
    "VIEWER": {
        "companies.read", "catalog.read", "catalog.export", "inventory.read",
    },
}

PERMISSION_DESCRIPTIONS = {
    "companies.read": "Consultar empresas",
    "companies.write": "Cadastrar empresas",
    "users.read": "Consultar usuários",
    "users.write": "Cadastrar usuários",
    "audit.read": "Consultar auditoria",
    "catalog.read": "Consultar catálogo",
    "catalog.write": "Cadastrar e alterar catálogo",
    "catalog.import": "Importar produtos por Excel",
    "catalog.export": "Exportar produtos para Excel",
    "inventory.read": "Consultar estoque por empresa",
    "inventory.write": "Alterar parâmetros de estoque",
    "history.read": "Consultar histórico de produtos",
}

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS roles(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS permissions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL,
          description TEXT
        );
        CREATE TABLE IF NOT EXISTS role_permissions(
          role_id INTEGER NOT NULL,
          permission_id INTEGER NOT NULL,
          PRIMARY KEY(role_id, permission_id),
          FOREIGN KEY(role_id) REFERENCES roles(id),
          FOREIGN KEY(permission_id) REFERENCES permissions(id)
        );
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          full_name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL COLLATE NOCASE,
          password_hash TEXT NOT NULL,
          role_id INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(role_id) REFERENCES roles(id)
        );
        CREATE TABLE IF NOT EXISTS companies(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL,
          legal_name TEXT NOT NULL,
          trade_name TEXT,
          tax_id TEXT UNIQUE NOT NULL,
          city TEXT,
          state TEXT,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          action TEXT NOT NULL,
          details TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS categories(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL COLLATE NOCASE,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS brands(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL COLLATE NOCASE,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS units(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL COLLATE NOCASE,
          description TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS suppliers(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT UNIQUE NOT NULL,
          legal_name TEXT NOT NULL,
          trade_name TEXT,
          tax_id TEXT UNIQUE,
          contact_name TEXT,
          email TEXT,
          phone TEXT,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          internal_code TEXT UNIQUE NOT NULL,
          description TEXT NOT NULL,
          category_id INTEGER,
          brand_id INTEGER,
          unit_id INTEGER NOT NULL,
          default_supplier_id INTEGER,
          ncm TEXT,
          ipi_rate REAL NOT NULL DEFAULT 0,
          icms_rate REAL NOT NULL DEFAULT 0,
          barcode TEXT UNIQUE,
          erp_code TEXT UNIQUE,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(category_id) REFERENCES categories(id),
          FOREIGN KEY(brand_id) REFERENCES brands(id),
          FOREIGN KEY(unit_id) REFERENCES units(id),
          FOREIGN KEY(default_supplier_id) REFERENCES suppliers(id)
        );
        CREATE INDEX IF NOT EXISTS ix_products_description ON products(description);
        CREATE INDEX IF NOT EXISTS ix_products_erp_code ON products(erp_code);
        CREATE INDEX IF NOT EXISTS ix_products_category ON products(category_id);

        CREATE TABLE IF NOT EXISTS product_company_settings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id INTEGER NOT NULL,
          company_id INTEGER NOT NULL,
          minimum_stock REAL NOT NULL DEFAULT 0,
          maximum_stock REAL NOT NULL DEFAULT 0,
          lead_time_days INTEGER NOT NULL DEFAULT 0,
          stock_location TEXT,
          average_cost REAL NOT NULL DEFAULT 0,
          last_cost REAL NOT NULL DEFAULT 0,
          last_purchase_date TEXT,
          current_stock REAL NOT NULL DEFAULT 0,
          reserved_stock REAL NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(product_id, company_id),
          FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
          FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS ix_product_company_company ON product_company_settings(company_id);

        CREATE TABLE IF NOT EXISTS product_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id INTEGER NOT NULL,
          user_id INTEGER,
          action TEXT NOT NULL,
          snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS ix_product_history_product ON product_history(product_id, created_at);
        ''')

        # Atualiza bancos da Sprint 1 que ainda não tinham description.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(permissions)")}
        if "description" not in columns:
            conn.execute("ALTER TABLE permissions ADD COLUMN description TEXT")

        roles = {"ADMIN": "Administrador", "MANAGER": "Gestor", "VIEWER": "Visualizador"}
        for code, name in roles.items():
            conn.execute("INSERT OR IGNORE INTO roles(code,name) VALUES(?,?)", (code,name))

        all_permissions = sorted(set().union(*ROLE_PERMISSIONS.values()))
        for code in all_permissions:
            conn.execute(
                "INSERT OR IGNORE INTO permissions(code,description) VALUES(?,?)",
                (code, PERMISSION_DESCRIPTIONS.get(code, code)),
            )
            conn.execute(
                "UPDATE permissions SET description=? WHERE code=?",
                (PERMISSION_DESCRIPTIONS.get(code, code), code),
            )

        for role_code, permission_codes in ROLE_PERMISSIONS.items():
            role=conn.execute("SELECT id FROM roles WHERE code=?",(role_code,)).fetchone()
            for permission_code in permission_codes:
                permission=conn.execute("SELECT id FROM permissions WHERE code=?",(permission_code,)).fetchone()
                conn.execute("INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)",(role['id'],permission['id']))

        if not conn.execute("SELECT id FROM users WHERE email=?",("admin@smartbuy.local",)).fetchone():
            role=conn.execute("SELECT id FROM roles WHERE code='ADMIN'").fetchone()
            conn.execute("INSERT INTO users(full_name,email,password_hash,role_id) VALUES(?,?,?,?)",(
                "Administrador SmartBuy","admin@smartbuy.local",hash_password("SmartBuy@123"),role['id']))

        if not conn.execute("SELECT id FROM companies WHERE code='1'").fetchone():
            conn.execute("INSERT INTO companies(code,legal_name,trade_name,tax_id,city,state) VALUES(?,?,?,?,?,?)",(
                "1","SmartBuy Demonstração Ltda.","SmartBuy Demo","00000000000000","Anápolis","GO"))

        conn.execute("INSERT OR IGNORE INTO units(code,description) VALUES('UN','Unidade')")
        conn.commit()

def get_user(user_id:int):
    with connect() as conn:
        return conn.execute('''SELECT users.*,roles.code role_code,roles.name role_name
          FROM users JOIN roles ON roles.id=users.role_id WHERE users.id=?''',(user_id,)).fetchone()

def get_user_by_email(email:str):
    with connect() as conn:
        return conn.execute('''SELECT users.*,roles.code role_code,roles.name role_name
          FROM users JOIN roles ON roles.id=users.role_id WHERE users.email=?''',(email.strip().lower(),)).fetchone()

def permissions(user_id:int)->set[str]:
    with connect() as conn:
        rows=conn.execute('''SELECT permissions.code FROM users
          JOIN roles ON roles.id=users.role_id
          JOIN role_permissions ON role_permissions.role_id=roles.id
          JOIN permissions ON permissions.id=role_permissions.permission_id
          WHERE users.id=?''',(user_id,)).fetchall()
    return {r['code'] for r in rows}

def audit(user_id:int|None, action:str, details:str=''):
    with connect() as conn:
        conn.execute("INSERT INTO audit_log(user_id,action,details) VALUES(?,?,?)",(user_id,action,details)); conn.commit()

# SMARTBUY_SPRINT_5_PURCHASING_ENGINE
def init_purchasing_engine_schema() -> None:
    with connect() as conn:
        settings_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(product_company_settings)"
            )
        }
        additions = {
            "analysis_months": "INTEGER NOT NULL DEFAULT 3",
            "safety_days": "INTEGER NOT NULL DEFAULT 15",
            "coverage_days": "INTEGER NOT NULL DEFAULT 60",
            "replenishment_mode": "TEXT NOT NULL DEFAULT 'AUTO'",
            "on_order_stock": "REAL NOT NULL DEFAULT 0",
        }
        for column, definition in additions.items():
            if column not in settings_columns:
                conn.execute(
                    f"ALTER TABLE product_company_settings "
                    f"ADD COLUMN {column} {definition}"
                )

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL CHECK(quantity >= 0),
                movement_date TEXT NOT NULL,
                reference_type TEXT,
                reference_number TEXT,
                unit_cost REAL,
                notes TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(company_id) REFERENCES companies(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS ix_stock_movements_analysis
                ON stock_movements(
                    product_id, company_id, movement_type, movement_date
                );

            CREATE TABLE IF NOT EXISTS product_cost_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                supplier_id INTEGER,
                cost_type TEXT NOT NULL DEFAULT 'PURCHASE',
                unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
                quantity REAL NOT NULL DEFAULT 0,
                total_cost REAL NOT NULL DEFAULT 0,
                cost_date TEXT NOT NULL,
                reference_number TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(company_id) REFERENCES companies(id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS ix_cost_history_product
                ON product_cost_history(product_id, company_id, cost_date);

            CREATE TABLE IF NOT EXISTS product_suppliers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                supplier_product_code TEXT,
                preferred INTEGER NOT NULL DEFAULT 0,
                last_price REAL,
                lead_time_days INTEGER,
                minimum_order_quantity REAL NOT NULL DEFAULT 0,
                supplier_score REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, supplier_id),
                FOREIGN KEY(product_id) REFERENCES products(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
            );

            CREATE INDEX IF NOT EXISTS ix_product_suppliers_preferred
                ON product_suppliers(product_id, preferred, active);

            CREATE TABLE IF NOT EXISTS supplier_quotes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                quantity REAL NOT NULL CHECK(quantity > 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0),
                freight_total REAL NOT NULL DEFAULT 0,
                taxes_total REAL NOT NULL DEFAULT 0,
                discount_total REAL NOT NULL DEFAULT 0,
                payment_term_days INTEGER NOT NULL DEFAULT 0,
                lead_time_days INTEGER NOT NULL DEFAULT 0,
                valid_until TEXT,
                status TEXT NOT NULL DEFAULT 'VALID',
                notes TEXT,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(company_id) REFERENCES companies(id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS ix_supplier_quotes_compare
                ON supplier_quotes(
                    company_id, product_id, status, created_at
                );

            CREATE TABLE IF NOT EXISTS inventory_snapshots(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                current_stock REAL NOT NULL DEFAULT 0,
                reserved_stock REAL NOT NULL DEFAULT 0,
                on_order_stock REAL NOT NULL DEFAULT 0,
                UNIQUE(product_id, company_id, snapshot_date),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(company_id) REFERENCES companies(id)
            );

            CREATE TABLE IF NOT EXISTS purchase_recommendation_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                analysis_date TEXT NOT NULL,
                analysis_months INTEGER NOT NULL,
                total_products INTEGER NOT NULL DEFAULT 0,
                products_to_buy INTEGER NOT NULL DEFAULT 0,
                estimated_value REAL NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(company_id) REFERENCES companies(id),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );
            """
        )

        permissions = {
            "purchasing_intelligence.read":
                "Consultar inteligência de compras",
            "purchasing_intelligence.write":
                "Registrar movimentações, custos e cotações",
            "purchasing_intelligence.configure":
                "Configurar políticas de reposição",
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

        role_permissions = {
            "ADMIN": set(permissions),
            "MANAGER": set(permissions),
            "VIEWER": {"purchasing_intelligence.read"},
        }
        for role_code, codes in role_permissions.items():
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


_sprint4_or_previous_init_db = init_db


def init_db() -> None:
    _sprint4_or_previous_init_db()
    init_purchasing_engine_schema()

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
