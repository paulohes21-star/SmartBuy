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
