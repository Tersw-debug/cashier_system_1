import sqlite3
import os


def migrate_db(databaseName):
    conn = sqlite3.connect(databaseName)
    cursor = conn.cursor()
    
    try:
        # This command adds the 'total' column if it's missing
        cursor.execute("ALTER TABLE products ADD COLUMN total REAL DEFAULT 0")
        conn.commit()
        print("Database updated successfully!")
    except sqlite3.OperationalError:

        print("Column 'total' already exists, skipping...")
    
    conn.close()




class Database:

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_NAME = os.path.join(BASE_DIR, "shop.db")



    @staticmethod
    def get_connection():
        return sqlite3.connect(Database.DB_NAME)    

    @staticmethod
    def init_db():
        conn = Database.get_connection()
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time DATE NOT NULL,
            name TEXT NOT NULL UNIQUE,
            barcode TEXT UNIQUE,
            sell_price REAL,
            quantity INTEGER,
            total INTEGER
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
