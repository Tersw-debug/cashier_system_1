from Database.migrations.helpers import TS, add_updated_at_trigger, add_permissions

VERSION = 3
DESCRIPTION = "Partners (customers/suppliers), tax rates, purchasing"


def apply(c):
    statements = [
        f"""CREATE TABLE tax_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            rate_bp INTEGER NOT NULL CHECK (rate_bp >= 0),   -- basis points: 14% = 1400
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        "ALTER TABLE products ADD COLUMN tax_rate_id INTEGER REFERENCES tax_rates(id)",

        f"""CREATE TABLE partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            phone2 TEXT,
            email TEXT,
            address TEXT,
            tax_number TEXT,
            is_customer INTEGER NOT NULL DEFAULT 1,
            is_supplier INTEGER NOT NULL DEFAULT 0,
            credit_limit INTEGER NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS},
            CHECK (is_customer = 1 OR is_supplier = 1)
        )""",
        "CREATE INDEX idx_partners_name ON partners(name)",
        "CREATE INDEX idx_partners_phone ON partners(phone)",

        # ---------- purchase orders (optional step before receiving) ----------
        f"""CREATE TABLE purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            supplier_id INTEGER NOT NULL REFERENCES partners(id),
            order_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            expected_date TEXT,
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT','CONFIRMED','PARTIAL','RECEIVED','CANCELLED')),
            total INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS},
            updated_at {TS}
        )""",
        """CREATE TABLE purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity REAL NOT NULL CHECK (quantity > 0),
            received_quantity REAL NOT NULL DEFAULT 0,
            unit_cost INTEGER NOT NULL CHECK (unit_cost >= 0)
        )""",
        "CREATE INDEX idx_po_items_order ON purchase_order_items(order_id)",

        # ---------- purchase invoices: receive goods + create the payable ----------
        # total = subtotal + tax_total - discount (all minor units)
        # amount_paid is deliberately not stored; it is derived from payment_allocations.
        f"""CREATE TABLE purchase_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            invoice_type TEXT NOT NULL DEFAULT 'PURCHASE'
                CHECK (invoice_type IN ('PURCHASE','RETURN')),
            supplier_id INTEGER NOT NULL REFERENCES partners(id),
            order_id INTEGER REFERENCES purchase_orders(id) ON DELETE SET NULL,
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            supplier_ref TEXT,
            invoice_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'POSTED'
                CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
            subtotal INTEGER NOT NULL DEFAULT 0,
            tax_total INTEGER NOT NULL DEFAULT 0,
            discount INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS},
            updated_at {TS}
        )""",
        "CREATE INDEX idx_pinv_supplier ON purchase_invoices(supplier_id)",
        "CREATE INDEX idx_pinv_date ON purchase_invoices(invoice_date)",
        # line_total = quantity*unit_cost - line_discount + tax_amount
        """CREATE TABLE purchase_invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            product_name TEXT NOT NULL,
            order_item_id INTEGER REFERENCES purchase_order_items(id) ON DELETE SET NULL,
            quantity REAL NOT NULL CHECK (quantity > 0),
            unit_cost INTEGER NOT NULL CHECK (unit_cost >= 0),
            line_discount INTEGER NOT NULL DEFAULT 0,
            tax_rate_bp INTEGER NOT NULL DEFAULT 0,
            tax_amount INTEGER NOT NULL DEFAULT 0,
            line_total INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_pinv_items_invoice ON purchase_invoice_items(invoice_id)",
    ]
    for sql in statements:
        c.execute(sql)

    for table in ("tax_rates", "partners", "purchase_orders", "purchase_invoices"):
        add_updated_at_trigger(c, table)

    c.execute("INSERT INTO tax_rates (name, rate_bp) VALUES ('بدون ضريبة', 0)")

    add_permissions(c, [
        ("partners.view",      "View customers and suppliers"),
        ("partners.create",    "Add customers and suppliers"),
        ("partners.edit",      "Edit customers and suppliers"),
        ("partners.delete",    "Deactivate customers and suppliers"),
        ("taxes.manage",       "Manage tax rates"),
        ("purchasing.view",    "View purchase orders and invoices"),
        ("purchasing.create",  "Create purchase orders and invoices"),
        ("purchasing.cancel",  "Cancel purchase documents"),
    ], grants={"Cashier": ["partners.view", "partners.create"]})
