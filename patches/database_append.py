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
