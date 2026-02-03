from Database.Schema import Database
import sqlite3


def get_products():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    data = c.fetchall()
    conn.close()
    return data



def add_product(time, name, barcode, price, qty, total):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (time, name, barcode, sell_price, quantity, total) VALUES (?, ?, ?, ?, ?, ?)",
            (time, name, barcode, price, qty, total)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Tells the UI that the save failed
    finally:
        conn.close()

def update_product(pid, name, barcode, price, qty):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("""
    UPDATE products SET name=?,barcode=?,sell_price=?,quantity=? WHERE id=?
    """, (name, barcode, price, qty, pid))
    conn.commit()
    conn.close()


def get_number_of_products():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("""
    SELECT name FROM products
              """)
    rows = c.fetchall()
    conn.close()

    return [row[0] for row in rows]



def get_total_quantity():
    conn = Database.get_connection()
    c = conn.cursor()
    # This sums up the 'quantity' column for all products
    c.execute("SELECT SUM(quantity) FROM products")
    result = c.fetchone()[0]
    conn.close()
    return result if result else 0


def add_quantity_product(time,name,barcode, price, qty, total):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id ,quantity, barcode, total FROM products WHERE name = ?", (name,))
    result = c.fetchone()
    price = float(price)
    qty = int(qty)
    total = float(total)

    if result:
        product_id, old_qty, old_barcode, old_total = result
        new_qty = int(old_qty) + qty
        new_total = float(old_total) + total
        if old_barcode and old_barcode == barcode:

                 c.execute("""
                    UPDATE products
                    SET quantity = ?, sell_price = ?, total = ?
                    WHERE id = ?
                """, (new_qty, price, new_total,product_id))
        else:

                c.execute("""
                    UPDATE products
                    SET quantity = ?, sell_price = ?, barcode = ?, total = ?
                    WHERE id = ?
                """, (new_qty, price, barcode, new_total,product_id))

    else:
        raise ValueError("Product does not exist in storage")
    conn.commit()
    conn.close()


def delete_product(pid):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
