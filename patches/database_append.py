# SMARTBUY_SPRINT_4_INTELLIGENT_PRODUCTS
import json as _sprint4_json
import secrets as _sprint4_secrets


def init_intelligent_product_schema() -> None:
    with connect() as conn:
        product_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(products)")
        }
        if "manufacturer_reference" not in product_columns:
            conn.execute(
                "ALTER TABLE products ADD COLUMN manufacturer_reference TEXT"
            )
        if "manufacturer_id" not in product_columns:
            conn.execute(
                "ALTER TABLE products ADD COLUMN manufacturer_id INTEGER"
            )

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS ix_products_barcode
                ON products(barcode);
            CREATE INDEX IF NOT EXISTS ix_products_manufacturer_reference
                ON products(manufacturer_reference);

            CREATE TABLE IF NOT EXISTS product_external_codes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                source_system TEXT NOT NULL COLLATE NOCASE,
                company_id INTEGER,
                external_code TEXT NOT NULL COLLATE NOCASE,
                external_description TEXT,
                sync_status TEXT NOT NULL DEFAULT 'PENDING',
                last_sync_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_system, company_id, external_code),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS ix_external_codes_product
                ON product_external_codes(product_id);
            CREATE INDEX IF NOT EXISTS ix_external_codes_lookup
                ON product_external_codes(source_system, external_code);

            CREATE TABLE IF NOT EXISTS product_import_batches(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                user_id INTEGER,
                status TEXT NOT NULL DEFAULT 'VALIDATED',
                total_rows INTEGER NOT NULL DEFAULT 0,
                valid_rows INTEGER NOT NULL DEFAULT 0,
                error_rows INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS product_import_rows(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                row_number INTEGER NOT NULL,
                operation TEXT NOT NULL,
                internal_code TEXT,
                payload_json TEXT NOT NULL,
                errors_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                applied_product_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(batch_id) REFERENCES product_import_batches(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(applied_product_id) REFERENCES products(id)
            );

            CREATE INDEX IF NOT EXISTS ix_import_rows_batch
                ON product_import_rows(batch_id, row_number);
            """
        )

        new_permissions = {
            "catalog.smart_search": "Usar pesquisa inteligente de produtos",
            "catalog.external_codes": "Gerenciar códigos externos de ERP",
            "catalog.import.confirm": "Confirmar importações validadas",
        }
        for code, description in new_permissions.items():
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

        access = {
            "ADMIN": set(new_permissions),
            "MANAGER": set(new_permissions),
            "VIEWER": {"catalog.smart_search"},
        }
        for role_code, permission_codes in access.items():
            role = conn.execute(
                "SELECT id FROM roles WHERE code=?",
                (role_code,),
            ).fetchone()
            if role is None:
                continue
            for permission_code in permission_codes:
                permission = conn.execute(
                    "SELECT id FROM permissions WHERE code=?",
                    (permission_code,),
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


_sprint3_or_previous_init_db = init_db


def init_db() -> None:
    _sprint3_or_previous_init_db()
    init_intelligent_product_schema()


def create_import_token() -> str:
    return _sprint4_secrets.token_urlsafe(24)


def json_dump(value) -> str:
    return _sprint4_json.dumps(value, ensure_ascii=False, default=str)
