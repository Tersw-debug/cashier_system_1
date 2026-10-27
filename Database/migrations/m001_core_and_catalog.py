from Database.migrations.helpers import TS, add_updated_at_trigger

VERSION = 1
DESCRIPTION = "Core, security and catalog"


def apply(c):
    statements = [
        # ---------- settings ----------
        f"""CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at {TS}
        )""",

        # ---------- security ----------
        f"""CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at {TS},
            updated_at {TS}
        )""",
        """CREATE TABLE permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            description TEXT
        )""",
        """CREATE TABLE role_permissions (
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )""",
        f"""CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role_id INTEGER NOT NULL REFERENCES roles(id),
            is_active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            last_login_at TEXT,
            created_at {TS},
            updated_at {TS}
        )""",
        f"""CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at {TS},
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            old_values TEXT,
            new_values TEXT,
            note TEXT
        )""",
        "CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id)",
        "CREATE INDEX idx_audit_created ON audit_log(created_at)",

        # ---------- catalog ----------
        f"""CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            symbol TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        f"""CREATE TABLE sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            parent_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        f"""CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
            unit_id INTEGER REFERENCES units(id),
            color TEXT CHECK (
                color IS NULL OR
                color GLOB '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'
            ),
            cost_price INTEGER NOT NULL DEFAULT 0 CHECK (cost_price >= 0),
            sell_price INTEGER NOT NULL CHECK (sell_price >= 0),
            min_quantity REAL NOT NULL DEFAULT 0,
            track_stock INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        "CREATE UNIQUE INDEX uq_products_active_name ON products(name) WHERE is_active = 1",
        "CREATE INDEX idx_products_section ON products(section_id)",
        """CREATE TABLE product_barcodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            barcode TEXT NOT NULL UNIQUE,
            is_primary INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX idx_barcodes_product ON product_barcodes(product_id)",
    ]

    for sql in statements:
        c.execute(sql)

    for table in ("roles", "users", "units", "sections", "products"):
        add_updated_at_trigger(c, table)

    # ---------- seed data ----------
    permissions = [
        ("users.manage",    "Create, edit and disable users"),
        ("roles.manage",    "Manage roles and permissions"),
        ("settings.manage", "Change company settings"),
        ("audit.view",      "View the audit log"),
        ("products.view",   "View products"),
        ("products.create", "Add products"),
        ("products.edit",   "Edit products and prices"),
        ("products.delete", "Deactivate products"),
        ("sections.manage", "Manage sections"),
    ]
    c.executemany("INSERT INTO permissions (code, description) VALUES (?, ?)", permissions)

    c.execute("INSERT INTO roles (name, description, is_system) VALUES ('Admin', 'Full access', 1)")
    admin_role = c.lastrowid
    c.execute("INSERT INTO roles (name, description, is_system) VALUES ('Cashier', 'Sales only', 1)")
    cashier_role = c.lastrowid

    c.execute("SELECT id, code FROM permissions")
    perm_ids = {code: pid for pid, code in c.fetchall()}

    for pid in perm_ids.values():
        c.execute("INSERT INTO role_permissions VALUES (?, ?)", (admin_role, pid))
    c.execute("INSERT INTO role_permissions VALUES (?, ?)",
              (cashier_role, perm_ids["products.view"]))

    c.execute("INSERT INTO units (name, symbol) VALUES ('قطعة', 'pcs')")
    c.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [("company_name", ""), ("currency_symbol", ""), ("currency_decimals", "2")]
    )