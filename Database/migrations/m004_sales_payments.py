from Database.migrations.helpers import TS, add_updated_at_trigger, add_permissions

VERSION = 4
DESCRIPTION = "Sales, returns, payments, cash shifts, balance views"


def apply(c):
    statements = [
        f"""CREATE TABLE payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'CASH'
                CHECK (kind IN ('CASH','CARD','TRANSFER','WALLET','OTHER')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",

        # ---------- cash drawer shifts ----------
        f"""CREATE TABLE cash_shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            opened_at {TS},
            closed_at TEXT,
            opening_cash INTEGER NOT NULL DEFAULT 0,
            closing_cash INTEGER,
            expected_cash INTEGER,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
            note TEXT
        )""",
        "CREATE UNIQUE INDEX uq_one_open_shift_per_user ON cash_shifts(user_id) WHERE status = 'OPEN'",

        # ---------- sales and returns ----------
        # total = subtotal + tax_total - discount (minor units)
        # amount_paid is deliberately not stored; it is derived from payment_allocations.
        f"""CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            sale_type TEXT NOT NULL DEFAULT 'SALE' CHECK (sale_type IN ('SALE','RETURN')),
            original_sale_id INTEGER REFERENCES sales(id),
            customer_id INTEGER REFERENCES partners(id),          -- NULL = walk-in
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            cashier_id INTEGER NOT NULL REFERENCES users(id),
            shift_id INTEGER REFERENCES cash_shifts(id),
            status TEXT NOT NULL DEFAULT 'POSTED'
                CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
            sold_at {TS},
            subtotal INTEGER NOT NULL DEFAULT 0,
            tax_total INTEGER NOT NULL DEFAULT 0,
            discount INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            due_date TEXT,
            note TEXT,
            created_at {TS},
            updated_at {TS}
        )""",
        "CREATE INDEX idx_sales_customer ON sales(customer_id)",
        "CREATE INDEX idx_sales_sold_at ON sales(sold_at)",
        "CREATE INDEX idx_sales_shift ON sales(shift_id)",
        # line_total = quantity*unit_price - line_discount + tax_amount
        # unit_cost is a snapshot so profit reports survive later cost changes
        """CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id),
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL CHECK (quantity > 0),
            unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
            unit_cost INTEGER NOT NULL DEFAULT 0,
            line_discount INTEGER NOT NULL DEFAULT 0,
            tax_rate_bp INTEGER NOT NULL DEFAULT 0,
            tax_amount INTEGER NOT NULL DEFAULT 0,
            line_total INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_sale_items_sale ON sale_items(sale_id)",
        "CREATE INDEX idx_sale_items_product ON sale_items(product_id)",

        # ---------- payments (customers IN, suppliers OUT) ----------
        f"""CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),
            partner_id INTEGER REFERENCES partners(id),
            method_id INTEGER NOT NULL REFERENCES payment_methods(id),
            shift_id INTEGER REFERENCES cash_shifts(id),
            amount INTEGER NOT NULL CHECK (amount > 0),
            paid_at {TS},
            reference TEXT,
            note TEXT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS}
        )""",
        "CREATE INDEX idx_payments_partner ON payments(partner_id)",
        # a payment can be split across documents; the unallocated rest is "on account"
        """CREATE TABLE payment_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
            document_type TEXT NOT NULL CHECK (document_type IN ('SALE','PURCHASE_INVOICE')),
            document_id INTEGER NOT NULL,
            amount INTEGER NOT NULL CHECK (amount > 0)
        )""",
        "CREATE INDEX idx_alloc_doc ON payment_allocations(document_type, document_id)",
        "CREATE INDEX idx_alloc_payment ON payment_allocations(payment_id)",

        # ---------- derived balances: allocation totals are calculated when queried ----------
        # Positive = the customer owes us.
        """CREATE VIEW v_customer_balances AS
        SELECT p.id AS partner_id, p.name,
            COALESCE((
                SELECT SUM(
                    CASE s.sale_type
                        WHEN 'SALE' THEN s.total - COALESCE((
                            SELECT SUM(a.amount)
                            FROM payment_allocations a
                            WHERE a.document_type = 'SALE' AND a.document_id = s.id
                        ), 0)
                        ELSE -(s.total - COALESCE((
                            SELECT SUM(a.amount)
                            FROM payment_allocations a
                            WHERE a.document_type = 'SALE' AND a.document_id = s.id
                        ), 0))
                    END
                )
                FROM sales s
                WHERE s.customer_id = p.id AND s.status = 'POSTED'
            ), 0)
            - COALESCE((
                SELECT SUM(py.amount - COALESCE((
                    SELECT SUM(a.amount)
                    FROM payment_allocations a
                    WHERE a.payment_id = py.id
                ), 0))
                FROM payments py
                WHERE py.partner_id = p.id AND py.direction = 'IN'
            ), 0) AS balance
        FROM partners p
        WHERE p.is_customer = 1""",

        # Positive = we owe the supplier.
        """CREATE VIEW v_supplier_balances AS
        SELECT p.id AS partner_id, p.name,
            COALESCE((
                SELECT SUM(
                    CASE i.invoice_type
                        WHEN 'PURCHASE' THEN i.total - COALESCE((
                            SELECT SUM(a.amount)
                            FROM payment_allocations a
                            WHERE a.document_type = 'PURCHASE_INVOICE' AND a.document_id = i.id
                        ), 0)
                        ELSE -(i.total - COALESCE((
                            SELECT SUM(a.amount)
                            FROM payment_allocations a
                            WHERE a.document_type = 'PURCHASE_INVOICE' AND a.document_id = i.id
                        ), 0))
                    END
                )
                FROM purchase_invoices i
                WHERE i.supplier_id = p.id AND i.status = 'POSTED'
            ), 0)
            - COALESCE((
                SELECT SUM(py.amount - COALESCE((
                    SELECT SUM(a.amount)
                    FROM payment_allocations a
                    WHERE a.payment_id = py.id
                ), 0))
                FROM payments py
                WHERE py.partner_id = p.id AND py.direction = 'OUT'
            ), 0) AS balance
        FROM partners p
        WHERE p.is_supplier = 1""",
    ]
    for sql in statements:
        c.execute(sql)

    for table in ("payment_methods", "sales"):
        add_updated_at_trigger(c, table)

    c.executemany(
        "INSERT INTO payment_methods (name, kind) VALUES (?, ?)",
        [("نقدي", "CASH"), ("بطاقة", "CARD"), ("تحويل بنكي", "TRANSFER")]
    )

    add_permissions(c, [
        ("sales.view",             "View sales"),
        ("sales.create",           "Create sales"),
        ("sales.discount",         "Give discounts"),
        ("sales.return",           "Process returns"),
        ("sales.cancel",           "Cancel sales"),
        ("payments.view",          "View payments"),
        ("payments.create",        "Record payments"),
        ("shifts.manage",          "Open and close cash shifts"),
        ("payment_methods.manage", "Manage payment methods"),
    ], grants={"Cashier": ["sales.view", "sales.create", "payments.create", "shifts.manage"]})
