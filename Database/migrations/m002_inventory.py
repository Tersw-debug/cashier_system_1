from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS, add_permissions

VERSION = 2
DESCRIPTION = "Inventory ledger, warehouses, transfers, document numbering"

MOVEMENT_TYPES = ("OPENING", "PURCHASE", "PURCHASE_RETURN", "SALE", "SALE_RETURN",
                  "ADJUSTMENT", "DAMAGE", "TRANSFER_IN", "TRANSFER_OUT")


def apply(c):
    types_sql = ", ".join(f"'{t}'" for t in MOVEMENT_TYPES)

    statements = [
        # At most one default warehouse: default_flag is 1 for the default row and NULL
        # otherwise (MySQL has no partial unique index; NULLs never collide).
        f"""CREATE TABLE warehouses (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL UNIQUE,
            code VARCHAR(50) UNIQUE,
            address VARCHAR(255),
            is_default TINYINT(1) NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            default_flag TINYINT GENERATED ALWAYS AS (IF(is_default = 1, 1, NULL)) VIRTUAL INVISIBLE,
            UNIQUE KEY uq_warehouses_default (default_flag)
        ) {TABLE_OPTS}""",

        # ---------- the ledger: append-only ----------
        # quantity_change: + in, - out.  unit_cost in minor units.
        # reference_type: 'SALE', 'PURCHASE_INVOICE', 'TRANSFER', ...
        f"""CREATE TABLE stock_movements (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            created_at {TS},
            product_id INT NOT NULL,
            warehouse_id INT NOT NULL,
            movement_type VARCHAR(30) NOT NULL,
            quantity_change DECIMAL(18,3) NOT NULL,
            unit_cost BIGINT NULL,
            reference_type VARCHAR(50) NULL,
            reference_id INT NULL,
            user_id INT NULL,
            note TEXT,
            CONSTRAINT chk_movement_type CHECK (movement_type IN ({types_sql})),
            CONSTRAINT chk_movement_qty CHECK (quantity_change <> 0),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_movements_product ON stock_movements(product_id, warehouse_id)",
        "CREATE INDEX idx_movements_ref ON stock_movements(reference_type, reference_id)",
        "CREATE INDEX idx_movements_created ON stock_movements(created_at)",

        # ---------- current stock: maintained ONLY by the trigger below ----------
        f"""CREATE TABLE stock_levels (
            product_id INT NOT NULL,
            warehouse_id INT NOT NULL,
            quantity DECIMAL(18,3) NOT NULL DEFAULT 0,
            PRIMARY KEY (product_id, warehouse_id),
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        ) {TABLE_OPTS}""",
        """CREATE TRIGGER trg_stock_movements_apply
        AFTER INSERT ON stock_movements
        FOR EACH ROW
        INSERT INTO stock_levels (product_id, warehouse_id, quantity)
        VALUES (NEW.product_id, NEW.warehouse_id, NEW.quantity_change)
        ON DUPLICATE KEY UPDATE quantity = quantity + NEW.quantity_change""",
        """CREATE TRIGGER trg_stock_movements_no_update
        BEFORE UPDATE ON stock_movements
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'stock_movements is append-only'""",
        """CREATE TRIGGER trg_stock_movements_no_delete
        BEFORE DELETE ON stock_movements
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'stock_movements is append-only'""",

        # ---------- transfers ----------
        f"""CREATE TABLE stock_transfers (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            from_warehouse_id INT NOT NULL,
            to_warehouse_id INT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
            note TEXT,
            created_by INT NULL,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_transfer_status CHECK (status IN ('DRAFT', 'COMPLETED', 'CANCELLED')),
            CONSTRAINT chk_transfer_distinct CHECK (from_warehouse_id <> to_warehouse_id),
            FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (to_warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE stock_transfer_items (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            transfer_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity DECIMAL(18,3) NOT NULL,
            CONSTRAINT chk_transfer_item_qty CHECK (quantity > 0),
            FOREIGN KEY (transfer_id) REFERENCES stock_transfers(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        ) {TABLE_OPTS}""",

        # ---------- document numbering (used by every module) ----------
        f"""CREATE TABLE doc_sequences (
            name VARCHAR(50) NOT NULL PRIMARY KEY,
            prefix VARCHAR(20) NOT NULL DEFAULT '',
            next_number INT NOT NULL DEFAULT 1,
            padding INT NOT NULL DEFAULT 6
        ) {TABLE_OPTS}""",

        # ---------- convenience view ----------
        """CREATE VIEW v_product_stock AS
        SELECT p.id AS product_id, COALESCE(SUM(sl.quantity), 0) AS quantity
        FROM products p
        LEFT JOIN stock_levels sl ON sl.product_id = p.id
        GROUP BY p.id""",
    ]
    for sql in statements:
        c.execute(sql)

    # ---------- seed ----------
    c.execute("INSERT INTO warehouses (name, code, is_default) VALUES ('المخزن الرئيسي', 'MAIN', 1)")
    c.executemany(
    "INSERT INTO doc_sequences (name, prefix) VALUES (%s, %s)",
    [
        ("TRANSFER", "TRF-"),
        ("PURCHASE_ORDER", "PO-"),
        ("PURCHASE_INVOICE", "PINV-"),
        ("SALE", "INV-"),
        ("SALE_RETURN", "RET-"),
        ("PAYMENT", "PAY-"),
        ("EXPENSE", "EXP-"),
        ("JOURNAL", "JE-"),
        ("PAYROLL", "PR-"),
    ],
)
    c.execute("INSERT INTO settings (`key`, `value`) VALUES ('allow_negative_stock', '0')")

    add_permissions(c, [
        ("inventory.view",     "View stock levels and movements"),
        ("inventory.adjust",   "Adjust stock manually"),
        ("inventory.transfer", "Transfer stock between warehouses"),
        ("warehouses.manage",  "Manage warehouses"),
    ], grants={"Cashier": ["inventory.view"]})