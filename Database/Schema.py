import sqlite3
import os
import random
import string
import datetime

def test(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check if 'id' column exists
    c.execute("SELECT * FROM sale_items")
    data_sale_items = c.fetchall()
    for row in data_sale_items:
        print(row)
    c.execute("SELECT * FROM sales")
    data_sales = c.fetchall()
    for row in data_sales:
        print(row)
    c.execute("SELECT * FROM customers")
    data_customers = c.fetchall()
    for row in data_customers:
        print(row)
    conn.commit()
    conn.close()


def migrate_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Check if column already exists
    c.execute("PRAGMA table_info(sale_items)")
    columns = [row[1] for row in c.fetchall()]

    if "product_name_at_sale" not in columns:
        c.execute("""
            ALTER TABLE sale_items
            ADD COLUMN product_name_at_sale TEXT
        """)

        # Optional: backfill existing rows
        c.execute("""
            UPDATE sale_items
            SET product_name_at_sale = (
                SELECT name FROM products
                WHERE products.id = sale_items.product_id
            )
            WHERE product_name_at_sale IS NULL
        """)

    conn.commit()
    conn.close()

    
class Database:

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_NAME = os.path.join(BASE_DIR, "shop.db")

    test(DB_NAME)

    @staticmethod
    def get_connection():
        conn = sqlite3.connect(Database.DB_NAME)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def init_db():
        conn = Database.get_connection()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL UNIQUE,
                barcode TEXT UNIQUE,
                sell_price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                min_quantity INTEGER NOT NULL DEFAULT 5
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS inventory_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_id INTEGER,
                created_at TEXT NOT NULL,

                old_price REAL,
                new_price REAL,

                old_quantity INTEGER,
                quantity_change INTEGER,   -- +10, -5, etc
                new_quantity INTEGER,

                action TEXT NOT NULL,       -- 'ADD', 'SALE', 'UPDATE', 'ADJUST'
                note TEXT,                  -- optional description
                user_id INTEGER,            -- who made the change

                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                cashier_id INTEGER NOT NULL,
                customer_id INTEGER,
                total REAL NOT NULL,
                amount_paid REAL NOT NULL, -- How much they actually handed over
                is_debt BOOLEAN DEFAULT 0,
                FOREIGN KEY (cashier_id)
                    REFERENCES users(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
                  
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                phone TEXT,
                current_debt REAL DEFAULT 0.0
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY,
                sale_id INTEGER NOT NULL,
                product_id INTEGER, -- Keep as FK
                product_name_at_sale TEXT, -- Snapshot: If product is deleted, we still know what it was
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL -- Safe
            )
        """)
        conn.commit()
        conn.close()

        Database.seed_default_products(200)
        Database.seed_default_shortage(200)

    @staticmethod
    def add_default_users():
        conn = Database.get_connection()
        c = conn.cursor()
        users = [("admin", "1234", "Admin"), ("cashier1", "1234", "Cashier"), ("cashier2", "1234", "Cashier") ]

        for u in users:
            try:
                c.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", u
                )
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        conn.close()
    @staticmethod
    def seed_default_products(count=200):
        conn = Database.get_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM products")
        current_count = c.fetchone()[0]

        if current_count >= count:
            conn.close()
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        products = []
        for i in range(1, count + 1):
            products.append((
                now,
                f"Product {i}",
                f"BC{random.randint(10**9, 10**10-1)}",
                round(random.uniform(5, 500), 2),
                random.randint(20, 100),
                random.randint(1, 10)
            ))

        c.executemany("""
            INSERT INTO products
            (created_at, name, barcode, sell_price, quantity, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, products)

        conn.commit()
        conn.close()

    @staticmethod
    def seed_default_shortage(count=200):
        conn = Database.get_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM products")
        current_count = c.fetchone()[0]

        if current_count >= count:
            conn.close()
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        products = []
        for i in range(1, count + 1):
            products.append((
                now,
                f"Productmkmakd_on_short {i}",
                f"BC{random.randint(10**9, 10**10-1)}",
                round(random.uniform(5, 500), 2),
                random.randint(1, 10),
                random.randint(10, 90)
            ))

        c.executemany("""
            INSERT INTO products
            (created_at, name, barcode, sell_price, quantity, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, products)

        conn.commit()
        conn.close()

    @staticmethod
    def add_stock(product_id, added_qty, new_price=None, user_id=None, note=None):
        conn = Database.get_connection()
        c = conn.cursor()

        # Get current state
        c.execute("""
            SELECT quantity, sell_price
            FROM products
            WHERE id=?
        """, (product_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise ValueError("Product not found")

        old_qty, old_price = row
        new_qty = old_qty + added_qty
        final_price = new_price if new_price is not None else old_price

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update product
        c.execute("""
            UPDATE products
            SET quantity=?, sell_price=?
            WHERE id=?
        """, (new_qty, final_price, product_id))

        # Log inventory change
        c.execute("""
            INSERT INTO inventory_log
            (product_id, created_at, old_price, new_price,
            old_quantity, quantity_change, new_quantity,
            action, note, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id, now,
            old_price, final_price,
            old_qty, added_qty, new_qty,
            "ADD", note, user_id
        ))

        conn.commit()
        conn.close()

    def sell_product(cashier_id, items, amount_paid, customer_id=None):
        conn = Database.get_connection()
        try:
            with conn: 
                c = conn.cursor()
                total_sale_price = 0.0
                sale_details = []

                for p_id, qty in items:
                    
                    c.execute("SELECT name, quantity, sell_price FROM products WHERE id=?", (p_id,))
                    row = c.fetchone()
                    
                    if not row:
                        raise ValueError(f"Product ID {p_id} not found.")
                
                    p_name, current_qty, price = row


                    if current_qty < qty:
                        raise ValueError(f"Insufficient stock for {p_name}. Available: {current_qty}")
     
                    item_total = price * qty
                    total_sale_price += item_total
                    sale_details.append({
                        'id': p_id, 'name': p_name, 'qty': qty, 
                        'price': price, 'old_qty': current_qty
                    })

                is_debt = amount_paid < total_sale_price
                if is_debt:
                    if not customer_id:
                        raise ValueError("A Customer must be selected for debt/partial payments.")
                    
                    debt_amount = total_sale_price - amount_paid
                    c.execute("""
                        UPDATE customers 
                        SET current_debt = current_debt + ? 
                        WHERE id = ?
                    """, (debt_amount, customer_id))
                
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("""
                    INSERT INTO sales (created_at, cashier_id, customer_id, total, amount_paid, is_debt)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (now, cashier_id, customer_id, total_sale_price, amount_paid, 1 if is_debt else 0))
                
                sale_id = c.lastrowid

              
                for item in sale_details:
                
                    c.execute("""
                        UPDATE products SET quantity = quantity - ? 
                        WHERE id = ? AND quantity >= ?
                    """, (item['qty'], item['id'], item['qty']))

                    
                    c.execute("""
                        INSERT INTO sale_items (sale_id, product_id, product_name_at_sale, qty, price)
                        VALUES (?, ?, ?, ?, ?)
                    """, (sale_id, item['id'], item['name'], item['qty'], item['price']))

                    
                    c.execute("""
                        INSERT INTO inventory_log 
                        (product_id, created_at, old_price, new_price, old_quantity, 
                        quantity_change, new_quantity, action, user_id, note)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item['id'], now, item['price'], item['price'], 
                        item['old_qty'], -item['qty'], item['old_qty'] - item['qty'],
                        "SALE", cashier_id, f"Sale ID: {sale_id}"
                    ))

            return True, "Sale completed successfully"
                
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()