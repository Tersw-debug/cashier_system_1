import sqlite3

class Database:

    DB_NAME = "shop.db"

    @staticmethod
    def get_connection():
        return sqlite3.connect(Database.DB_NAME)    


    def init_db():
        conn = Database.get_connection()
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            barcode TEXT UNIQUE,
            sell_price REAL,
            quantity INTEGER
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total REAL,
            cashier TEXT
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            sale_id INTEGER,
            product_id INTEGER,
            qty INTEGER,
            price REAL
        )
        ''')
        conn.commit()
        conn.close()

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
