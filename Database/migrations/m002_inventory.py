from Database.migrations.helpers import TS, add_updated_at_trigger, add_permissions

VERSION = 2
DESCRIPTION = "Inventory ledger, warehouses, transfers, document numbering"

MOVEMENT_TYPES = ("OPENING", "PURCHASE", "PURCHASE_RETURN", "SALE", "SALE_RETURN",
                  "ADJUSTMENT", "DAMAGE", "TRANSFER_IN", "TRANSFER_OUT")


def apply(c):
    types_sql = ", ".join(f"'{t}'" for t in MOVEMENT_TYPES)

    statements = [
        f"""CREATE TABLE warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT UNIQUE,
            address TEXT,
            is_default INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        "CREATE UNIQUE INDEX uq_warehouses_default ON warehouses(is_default) WHERE is_default = 1",

        # ---------- the ledger: append-only ----------
        f"""CREATE TABLE stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at {TS},
            product_id INTEGER NOT NULL REFERENCES products(id),
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            movement_type TEXT NOT NULL CHECK (movement_type IN ({types_sql})),
            quantity_change REAL NOT NULL CHECK (quantity_change <> 0),   -- + in, - out
            unit_cost INTEGER,                                            -- minor units
            reference_type TEXT,          -- 'SALE', 'PURCHASE_INVOICE', 'TRANSFER', ...
            reference_id INTEGER,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            note TEXT
        )""",
        "CREATE INDEX idx_movements_product ON stock_movements(product_id, warehouse_id)",
        "CREATE INDEX idx_movements_ref ON stock_movements(reference_type, reference_id)",
        "CREATE INDEX idx_movements_created ON stock_movements(created_at)",

        # ---------- current stock: maintained ONLY by the trigger below ----------
        """CREATE TABLE stock_levels (
            product_id INTEGER NOT NULL REFERENCES products(id),
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            quantity REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (product_id, warehouse_id)
        )""",
        """CREATE TRIGGER trg_stock_movements_apply
        AFTER INSERT ON stock_movements
        BEGIN
            INSERT INTO stock_levels (product_id, warehouse_id, quantity)
            VALUES (NEW.product_id, NEW.warehouse_id, NEW.quantity_change)
            ON CONFLICT(product_id, warehouse_id)
            DO UPDATE SET quantity = quantity + NEW.quantity_change;
        END""",
        """CREATE TRIGGER trg_stock_movements_no_update
        BEFORE UPDATE ON stock_movements
        BEGIN SELECT RAISE(ABORT, 'stock_movements is append-only'); END""",
        """CREATE TRIGGER trg_stock_movements_no_delete
        BEFORE DELETE ON stock_movements
        BEGIN SELECT RAISE(ABORT, 'stock_movements is append-only'); END""",

        # ---------- transfers ----------
        f"""CREATE TABLE stock_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            from_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            to_warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT', 'COMPLETED', 'CANCELLED')),
            note TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS},
            updated_at {TS},
            CHECK (from_warehouse_id <> to_warehouse_id)
        )""",
        """CREATE TABLE stock_transfer_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id INTEGER NOT NULL REFERENCES stock_transfers(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity REAL NOT NULL CHECK (quantity > 0)
        )""",
        "CREATE INDEX idx_transfer_items ON stock_transfer_items(transfer_id)",

        # ---------- document numbering (used by every module) ----------
        """CREATE TABLE doc_sequences (
            name TEXT PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT '',
            next_number INTEGER NOT NULL DEFAULT 1,
            padding INTEGER NOT NULL DEFAULT 6
        )""",

        # ---------- convenience view ----------
        """CREATE VIEW v_product_stock AS
        SELECT p.id AS product_id, COALESCE(SUM(sl.quantity), 0) AS quantity
        FROM products p
        LEFT JOIN stock_levels sl ON sl.product_id = p.id
        GROUP BY p.id""",
    ]
    for sql in statements:
        c.execute(sql)

    for table in ("warehouses", "stock_transfers"):
        add_updated_at_trigger(c, table)

    # ---------- seed ----------
    c.execute("INSERT INTO warehouses (name, code, is_default) VALUES ('المخزن الرئيسي', 'MAIN', 1)")
    c.executemany(
        "INSERT INTO doc_sequences (name, prefix) VALUES (?, ?)",
        [("TRANSFER", "TRF-"), ("PURCHASE_ORDER", "PO-"), ("PURCHASE_INVOICE", "PINV-"),
         ("SALE", "INV-"), ("SALE_RETURN", "RET-"), ("PAYMENT", "PAY-"),
         ("EXPENSE", "EXP-"), ("JOURNAL", "JE-"), ("PAYROLL", "PR-")]
    )
    c.execute("INSERT INTO settings (key, value) VALUES ('allow_negative_stock', '0')")

    add_permissions(c, [
        ("inventory.view",     "View stock levels and movements"),
        ("inventory.adjust",   "Adjust stock manually"),
        ("inventory.transfer", "Transfer stock between warehouses"),
        ("warehouses.manage",  "Manage warehouses"),
    ], grants={"Cashier": ["inventory.view"]})