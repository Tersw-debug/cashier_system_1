from Database.Schema import Database
import sqlite3


def get_products():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id,name,barcode,sell_price,quantity FROM products")
    data = c.fetchall()
    conn.close()
    return data

def add_product(name, barcode, price, qty):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (name,barcode,sell_price,quantity) VALUES (?,?,?,?)",
        (name, barcode, price, qty)
    )
    conn.commit()
    conn.close()

def update_product(pid, name, barcode, price, qty):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("""
    UPDATE products SET name=?,barcode=?,sell_price=?,quantity=? WHERE id=?
    """, (name, barcode, price, qty, pid))
    conn.commit()
    conn.close()

def delete_product(pid):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
