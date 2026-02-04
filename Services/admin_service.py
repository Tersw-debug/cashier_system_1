from Database.Schema import Database
import sqlite3


def get_products():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute(""" SELECT id, name, barcode, sell_price, quantity, min_quantity
        FROM products""")
    data = c.fetchall()
    conn.close()
    return data



def get_products_storage():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute(""" SELECT id,created_at ,name, barcode, sell_price, quantity, min_quantity
        FROM products""")
    data = c.fetchall()
    conn.close()
    return data


# we use add_product to function open_add_product
def add_product(created_at, name, barcode, price, qty, min_qty=5):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO products (created_at, name, barcode, sell_price, quantity, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (created_at, name, barcode, price, qty, min_qty))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()



def update_product_data(pid,name, barcode, price, qty, min_qty):
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT barcode
        FROM products
        WHERE name = ?
    """, (name,))
    result = c.fetchone()

    if not result:
        conn.close()
        raise ValueError("Product does not exist")

    old_barcode = result[0]
    if barcode and (barcode != old_barcode):
        c.execute("""
            UPDATE products
            SET name=?, barcode=?, sell_price=?, quantity=?, min_quantity=?
            WHERE id=?
        """, (name, barcode, price, qty, min_qty, pid))
    else:
        c.execute("""
            UPDATE products
            SET name=?, sell_price=?, quantity=?, min_quantity=?
            WHERE id=?
        """, (name, price, qty, min_qty, pid))
    conn.commit()
    conn.close()



def delete_product(pid):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()




def add_quantity_product(name, barcode, price, qty, min_qty):
   
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT id, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE name = ?
    """, (name,))
    result = c.fetchone()

    if not result:
        conn.close()
        raise ValueError("Product does not exist")

    product_id, old_barcode, old_price ,old_qty, old_min_qty = result

    try:
        qty = int(qty)
        price = float(price)
        min_qty = int(min_qty)
    except ValueError:
        conn.close()
        raise ValueError("Price, quantity, and min_qty must be numeric")

    new_qty = old_qty + qty
    new_price = price if price != old_price else old_price
    new_min_qty = min_qty if min_qty != old_min_qty else old_min_qty
    if barcode and (barcode != old_barcode):
        c.execute("""
            UPDATE products
            SET quantity=?, sell_price=?, barcode=?, min_quantity=?
            WHERE id=?
        """, (new_qty, new_price, barcode, new_min_qty, product_id))
    else:
        c.execute("""
            UPDATE products
            SET quantity=?, sell_price=?, min_quantity=?
            WHERE id=?
        """, (new_qty, new_price, new_min_qty, product_id))
        
    conn.commit()
    conn.close()


def get_product_price(name):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT sell_price FROM products WHERE name=?
        """
        , (name,)
    )
    result = c.fetchone()

    if result:
        return result[0]
    return None


def get_product_by_name_or_barcode(name, barcode):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE name = ? OR barcode = ?
    """, (name, barcode))
    return c.fetchall()


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


def get_low_stock_products():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT name, quantity, min_quantity
        FROM products
        WHERE quantity <= min_quantity
        ORDER BY quantity ASC
    """)
    data = c.fetchall()
    conn.close()
    return data