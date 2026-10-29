from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS

VERSION = 1
DESCRIPTION = "Core, security and catalog (MySQL 8)"


def apply(c):
    # NOTE: MySQL ignores inline "REFERENCES"; every foreign key is an explicit FOREIGN KEY clause.
    statements = [
        # ---------- settings ----------
        f"""CREATE TABLE settings (
            `key` VARCHAR(100) NOT NULL PRIMARY KEY,
            `value` TEXT,
            updated_at {TS_UPDATED}
        ) {TABLE_OPTS}""",

        # ---------- security ----------
        f"""CREATE TABLE roles (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR(255),
            is_system TINYINT(1) NOT NULL DEFAULT 0,
            created_at {TS},
            updated_at {TS_UPDATED}
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE permissions (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR(255)
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE role_permissions (
            role_id INT NOT NULL,
            permission_id INT NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE users (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(150),
            role_id INT NOT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            must_change_password TINYINT(1) NOT NULL DEFAULT 0,
            last_login_at DATETIME NULL,
            created_at {TS},
            updated_at {TS_UPDATED},
            FOREIGN KEY (role_id) REFERENCES roles(id)
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE audit_log (
            id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            created_at {TS},
            user_id INT NULL,
            action VARCHAR(100) NOT NULL,
            entity VARCHAR(100) NOT NULL,
            entity_id BIGINT NULL,
            old_values MEDIUMTEXT,
            new_values MEDIUMTEXT,
            note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id)",
        "CREATE INDEX idx_audit_created ON audit_log(created_at)",

        # ---------- catalog ----------
        f"""CREATE TABLE units (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            symbol VARCHAR(20),
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED}
        ) {TABLE_OPTS}""",

        # Section names are unique PER PARENT (the same "A4" / "colorful" can exist under
        # every category). parent_key makes root sections (parent_id NULL) comparable,
        # because MySQL treats NULLs as distinct in unique indexes.
        f"""CREATE TABLE sections (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            parent_id INT NULL,
            sort_order INT NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            parent_key INT GENERATED ALWAYS AS (IFNULL(parent_id, 0)) VIRTUAL INVISIBLE,
            UNIQUE KEY ux_sections_parent_name (parent_key, name),
            FOREIGN KEY (parent_id) REFERENCES sections(id) ON DELETE RESTRICT
        ) {TABLE_OPTS}""",

        # MySQL has no partial unique index, so "unique name among ACTIVE products"
        # is emulated with a generated column that is NULL for inactive rows.
        f"""CREATE TABLE products (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            sku VARCHAR(100) UNIQUE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            section_id INT NULL,
            unit_id INT NULL,
            color CHAR(7) NULL,
            cost_price BIGINT NOT NULL DEFAULT 0,
            sell_price BIGINT NOT NULL,
            min_quantity DECIMAL(18,3) NOT NULL DEFAULT 0,
            track_stock TINYINT(1) NOT NULL DEFAULT 1,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            active_name VARCHAR(255) GENERATED ALWAYS AS (IF(is_active = 1, name, NULL)) VIRTUAL INVISIBLE,
            UNIQUE KEY uq_products_active_name (active_name),
            CONSTRAINT chk_products_color CHECK (color IS NULL OR color REGEXP '^#[0-9A-Fa-f]{{6}}$'),
            CONSTRAINT chk_products_cost CHECK (cost_price >= 0),
            CONSTRAINT chk_products_sell CHECK (sell_price >= 0),
            FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE SET NULL,
            FOREIGN KEY (unit_id) REFERENCES units(id)
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE product_barcodes (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            barcode VARCHAR(64) NOT NULL UNIQUE,
            is_primary TINYINT(1) NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        ) {TABLE_OPTS}""",
    ]

    for sql in statements:
        c.execute(sql)

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
    c.executemany("INSERT INTO permissions (code, description) VALUES (%s, %s)", permissions)

    c.execute("INSERT INTO roles (name, description, is_system) VALUES ('Admin', 'Full access', 1)")
    admin_role = c.lastrowid
    c.execute("INSERT INTO roles (name, description, is_system) VALUES ('Cashier', 'Sales only', 1)")
    cashier_role = c.lastrowid

    c.execute("SELECT id, code FROM permissions")
    perm_ids = {code: pid for pid, code in c.fetchall()}

    for pid in perm_ids.values():
        c.execute("INSERT INTO role_permissions VALUES (%s, %s)", (admin_role, pid))
    c.execute("INSERT INTO role_permissions VALUES (%s, %s)",
              (cashier_role, perm_ids["products.view"]))

    c.execute("INSERT INTO units (name, symbol) VALUES ('قطعة', 'pcs')")
    c.executemany(
        "INSERT INTO settings (`key`, `value`) VALUES (%s, %s)",
        [("company_name", ""), ("currency_symbol", ""), ("currency_decimals", "2")]
    )