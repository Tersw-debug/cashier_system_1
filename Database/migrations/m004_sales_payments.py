from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS, add_permissions

VERSION = 4
DESCRIPTION = "Sales, returns, payments, cash shifts, balance views"


def apply(c):
    statements = [
        f"""CREATE TABLE payment_methods (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            kind VARCHAR(20) NOT NULL DEFAULT 'CASH',
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_pm_kind CHECK (kind IN ('CASH','CARD','TRANSFER','WALLET','OTHER'))
        ) {TABLE_OPTS}""",

        # ---------- cash drawer shifts ----------
        # open_user_id = the user while the shift is OPEN, NULL once closed, so the unique
        # key allows only one open shift per user (MySQL has no partial unique index).
        # user_id must stay ON DELETE RESTRICT: MySQL refuses SET NULL / CASCADE on the
        # base column of an indexed generated column.
        f"""CREATE TABLE cash_shifts (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            opened_at {TS},
            closed_at DATETIME NULL,
            opening_cash BIGINT NOT NULL DEFAULT 0,
            closing_cash BIGINT NULL,
            expected_cash BIGINT NULL,
            status VARCHAR(10) NOT NULL DEFAULT 'OPEN',
            note TEXT,
            open_user_id INT GENERATED ALWAYS AS (IF(status = 'OPEN', user_id, NULL)) VIRTUAL INVISIBLE,
            UNIQUE KEY uq_one_open_shift_per_user (open_user_id),
            CONSTRAINT chk_shift_status CHECK (status IN ('OPEN','CLOSED')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        ) {TABLE_OPTS}""",

        # ---------- sales and returns ----------
        # total = subtotal + tax_total - discount (minor units); customer_id NULL = walk-in
        # amount_paid is deliberately not stored; it is derived from payment_allocations.
        f"""CREATE TABLE sales (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            sale_type VARCHAR(10) NOT NULL DEFAULT 'SALE',
            original_sale_id INT NULL,
            customer_id INT NULL,
            warehouse_id INT NOT NULL,
            cashier_id INT NOT NULL,
            shift_id INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'POSTED',
            sold_at {TS},
            subtotal BIGINT NOT NULL DEFAULT 0,
            tax_total BIGINT NOT NULL DEFAULT 0,
            discount BIGINT NOT NULL DEFAULT 0,
            total BIGINT NOT NULL DEFAULT 0,
            due_date DATE NULL,
            note TEXT,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_sale_type CHECK (sale_type IN ('SALE','RETURN')),
            CONSTRAINT chk_sale_status CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
            FOREIGN KEY (original_sale_id) REFERENCES sales(id),
            FOREIGN KEY (customer_id) REFERENCES partners(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (cashier_id) REFERENCES users(id),
            FOREIGN KEY (shift_id) REFERENCES cash_shifts(id)
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_sales_customer ON sales(customer_id)",
        "CREATE INDEX idx_sales_sold_at ON sales(sold_at)",
        "CREATE INDEX idx_sales_shift ON sales(shift_id)",

        # line_total = quantity*unit_price - line_discount + tax_amount
        # unit_cost is a snapshot so profit reports survive later cost changes
        f"""CREATE TABLE sale_items (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            sale_id INT NOT NULL,
            product_id INT NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            quantity DECIMAL(18,3) NOT NULL,
            unit_price BIGINT NOT NULL,
            unit_cost BIGINT NOT NULL DEFAULT 0,
            line_discount BIGINT NOT NULL DEFAULT 0,
            tax_rate_bp INT NOT NULL DEFAULT 0,
            tax_amount BIGINT NOT NULL DEFAULT 0,
            line_total BIGINT NOT NULL,
            CONSTRAINT chk_si_qty CHECK (quantity > 0),
            CONSTRAINT chk_si_price CHECK (unit_price >= 0),
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_sale_items_product ON sale_items(product_id)",

        # ---------- payments (customers IN, suppliers OUT) ----------
        f"""CREATE TABLE payments (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            direction VARCHAR(3) NOT NULL,
            partner_id INT NULL,
            method_id INT NOT NULL,
            shift_id INT NULL,
            amount BIGINT NOT NULL,
            paid_at {TS},
            reference VARCHAR(100),
            note TEXT,
            user_id INT NULL,
            created_at {TS},
            CONSTRAINT chk_pay_direction CHECK (direction IN ('IN','OUT')),
            CONSTRAINT chk_pay_amount CHECK (amount > 0),
            FOREIGN KEY (partner_id) REFERENCES partners(id),
            FOREIGN KEY (method_id) REFERENCES payment_methods(id),
            FOREIGN KEY (shift_id) REFERENCES cash_shifts(id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_payments_partner ON payments(partner_id)",

        # a payment can be split across documents; the unallocated rest is "on account"
        f"""CREATE TABLE payment_allocations (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            payment_id INT NOT NULL,
            document_type VARCHAR(20) NOT NULL,
            document_id INT NOT NULL,
            amount BIGINT NOT NULL,
            CONSTRAINT chk_alloc_type CHECK (document_type IN ('SALE','PURCHASE_INVOICE')),
            CONSTRAINT chk_alloc_amount CHECK (amount > 0),
            FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_alloc_doc ON payment_allocations(document_type, document_id)",

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