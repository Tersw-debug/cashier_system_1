import sqlite3
import os
import random
import string
import datetime


def migrate_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Enable FK support
    c.execute("PRAGMA foreign_keys = ON")

    # --- PRODUCTS MIGRATION ---
    c.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='products'
    """)
    exists = c.fetchone()

    if exists:
        c.execute("ALTER TABLE products RENAME TO products_old")

        c.execute("""
            CREATE TABLE products (
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
            INSERT INTO products (id, created_at, name, barcode, sell_price, quantity, min_quantity)
            SELECT id, created_at, name, barcode, sell_price, quantity, 5
            FROM products_old
        """)

        c.execute("DROP TABLE products_old")

    conn.commit()
    conn.close()



class Database:

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_NAME = os.path.join(BASE_DIR, "shop.db")



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
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                cashier_id INTEGER NOT NULL,
                total REAL NOT NULL,
                FOREIGN KEY (cashier_id)
                    REFERENCES users(id)
                    ON DELETE RESTRICT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (sale_id)
                    REFERENCES sales(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE RESTRICT
            )
        """)
        conn.commit()
        conn.close()

        Database.seed_default_products(200)

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
                random.randint(0, 100),
                random.randint(1, 10)
            ))

        c.executemany("""
            INSERT INTO products
            (created_at, name, barcode, sell_price, quantity, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, products)

        conn.commit()
        conn.close()
