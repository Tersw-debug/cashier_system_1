from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS, add_permissions

VERSION = 3
DESCRIPTION = "Partners (customers/suppliers), tax rates, purchasing"


def apply(c):
    statements = [
        # rate_bp = basis points: 14% = 1400
        f"""CREATE TABLE tax_rates (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            rate_bp INT NOT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_tax_rate CHECK (rate_bp >= 0)
        ) {TABLE_OPTS}""",
        "ALTER TABLE products ADD COLUMN tax_rate_id INT NULL, "
        "ADD CONSTRAINT fk_products_tax_rate FOREIGN KEY (tax_rate_id) REFERENCES tax_rates(id)",

        f"""CREATE TABLE partners (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            phone VARCHAR(40),
            phone2 VARCHAR(40),
            email VARCHAR(150),
            address VARCHAR(255),
            tax_number VARCHAR(50),
            is_customer TINYINT(1) NOT NULL DEFAULT 1,
            is_supplier TINYINT(1) NOT NULL DEFAULT 0,
            credit_limit BIGINT NOT NULL DEFAULT 0,
            notes TEXT,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_partner_credit CHECK (credit_limit >= 0),
            CONSTRAINT chk_partner_role CHECK (is_customer = 1 OR is_supplier = 1)
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_partners_name ON partners(name)",
        "CREATE INDEX idx_partners_phone ON partners(phone)",

        # ---------- purchase orders (optional step before receiving) ----------
        f"""CREATE TABLE purchase_orders (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            supplier_id INT NOT NULL,
            order_date DATE NOT NULL DEFAULT (CURRENT_DATE),
            expected_date DATE NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
            total BIGINT NOT NULL DEFAULT 0,
            note TEXT,
            created_by INT NULL,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_po_status CHECK (status IN ('DRAFT','CONFIRMED','PARTIAL','RECEIVED','CANCELLED')),
            FOREIGN KEY (supplier_id) REFERENCES partners(id),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE purchase_order_items (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity DECIMAL(18,3) NOT NULL,
            received_quantity DECIMAL(18,3) NOT NULL DEFAULT 0,
            unit_cost BIGINT NOT NULL,
            CONSTRAINT chk_poi_qty CHECK (quantity > 0),
            CONSTRAINT chk_poi_cost CHECK (unit_cost >= 0),
            FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        ) {TABLE_OPTS}""",

        # ---------- purchase invoices: receive goods + create the payable ----------
        # total = subtotal + tax_total - discount (all minor units)
        # amount_paid is deliberately not stored; it is derived from payment_allocations.
        f"""CREATE TABLE purchase_invoices (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            invoice_type VARCHAR(20) NOT NULL DEFAULT 'PURCHASE',
            supplier_id INT NOT NULL,
            order_id INT NULL,
            warehouse_id INT NOT NULL,
            supplier_ref VARCHAR(100),
            invoice_date DATE NOT NULL DEFAULT (CURRENT_DATE),
            due_date DATE NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'POSTED',
            subtotal BIGINT NOT NULL DEFAULT 0,
            tax_total BIGINT NOT NULL DEFAULT 0,
            discount BIGINT NOT NULL DEFAULT 0,
            total BIGINT NOT NULL DEFAULT 0,
            note TEXT,
            created_by INT NULL,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_pinv_type CHECK (invoice_type IN ('PURCHASE','RETURN')),
            CONSTRAINT chk_pinv_status CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
            FOREIGN KEY (supplier_id) REFERENCES partners(id),
            FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_pinv_supplier ON purchase_invoices(supplier_id)",
        "CREATE INDEX idx_pinv_date ON purchase_invoices(invoice_date)",

        # line_total = quantity*unit_cost - line_discount + tax_amount
        f"""CREATE TABLE purchase_invoice_items (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            invoice_id INT NOT NULL,
            product_id INT NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            order_item_id INT NULL,
            quantity DECIMAL(18,3) NOT NULL,
            unit_cost BIGINT NOT NULL,
            line_discount BIGINT NOT NULL DEFAULT 0,
            tax_rate_bp INT NOT NULL DEFAULT 0,
            tax_amount BIGINT NOT NULL DEFAULT 0,
            line_total BIGINT NOT NULL,
            CONSTRAINT chk_pii_qty CHECK (quantity > 0),
            CONSTRAINT chk_pii_cost CHECK (unit_cost >= 0),
            FOREIGN KEY (invoice_id) REFERENCES purchase_invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (order_item_id) REFERENCES purchase_order_items(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
    ]
    for sql in statements:
        c.execute(sql)

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