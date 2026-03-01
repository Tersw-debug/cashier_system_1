from Database.Schema import Database
import sqlite3
import datetime

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
def add_product(created_at, name, barcode, price, qty, min_qty=5, user_id=None):
    conn = Database.get_connection()
    try:
        c = conn.cursor()

        c.execute("""
            INSERT INTO products
            (created_at, name, barcode, sell_price, quantity, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (created_at, name, barcode, price, qty, min_qty))

        product_id = c.lastrowid

        # 🔹 log inventory
        c.execute("""
            INSERT INTO inventory_log
            (product_id, created_at,
             old_price, new_price,
             old_quantity, quantity_change, new_quantity,
             action, note, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            created_at,
            None, price,
            0, qty, qty,
            "ADD",
            "إضافة منتج جديد",
            user_id
        ))

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_product_data(
    pid,
    name,
    barcode,
    price,
    new_qty,
    min_qty,
    user_id=None
):
    conn = Database.get_connection()
    c = conn.cursor()

    # Get old state
    c.execute("""
        SELECT name, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE id = ?
    """, (pid,))
    row = c.fetchone()

    if not row:
        conn.close()
        raise ValueError("Product not found")

    old_name, old_barcode, old_price, old_qty, old_min_qty = row
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Convert
    new_qty = int(new_qty)
    price = float(price)
    min_qty = int(min_qty)

    # Detect quantity change
    qty_diff = new_qty - old_qty

    # Update product
    c.execute("""
        UPDATE products
        SET name=?, barcode=?, sell_price=?, quantity=?, min_quantity=?
        WHERE id=?
    """, (name, barcode, price, new_qty, min_qty, pid))

    # Log changes
    if qty_diff != 0 or price != old_price:
        action = "ADJUST" if qty_diff != 0 else "UPDATE"

        c.execute("""
            INSERT INTO inventory_log
            (product_id, created_at,
             old_price, new_price,
             old_quantity, quantity_change, new_quantity,
             action, note, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, now,
            old_price, price,
            old_qty, qty_diff, new_qty,
            action,
            "تعديل يدوي من صفحة البحث",
            user_id
        ))

    conn.commit()
    conn.close()


def delete_product(pid, user_id=None):
    conn = Database.get_connection()
    c = conn.cursor()

    # Get product before delete
    c.execute("""
        SELECT quantity, sell_price
        FROM products
        WHERE id=?
    """, (pid,))
    row = c.fetchone()

    if not row:
        conn.close()
        raise ValueError("Product not found")

    old_qty, old_price = row
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log deletion
    c.execute("""
        INSERT INTO inventory_log
        (product_id, created_at,
         old_price, new_price,
         old_quantity, quantity_change, new_quantity,
         action, note, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid, now,
        old_price, None,
        old_qty, -old_qty, 0,
        "DELETE",
        "حذف المنتج من النظام",
        user_id
    ))

    # Delete product
    c.execute("DELETE FROM products WHERE id=?", (pid,))

    conn.commit()
    conn.close()




# -------------------------------
# Helpers
# -------------------------------

def get_all_product_names():
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("SELECT name FROM products ORDER BY name")
    rows = c.fetchall()

    conn.close()
    return [r[0] for r in rows]


def get_product_by_name(name):
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT id, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE name = ?
    """, (name,))
    row = c.fetchone()

    conn.close()
    return row


def get_product_price(name):
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("SELECT sell_price FROM products WHERE name = ?", (name,))
    row = c.fetchone()

    conn.close()
    return row[0] if row else None


# -------------------------------
# Main admin action
# -------------------------------

def admin_add_stock(
    product_name: str,
    added_qty: int,
    new_price: float | None = None,
    new_barcode: str | None = None,
    new_min_qty: int | None = None,
    user_id: int | None = None,
    note: str | None = None
):
    """
    Add stock to an EXISTING product.
    Logs everything to inventory_log.
    """

    product = get_product_by_name(product_name)
    if not product:
        raise ValueError("Product not found")

    product_id, old_barcode, old_price, old_qty, old_min_qty = product

    if added_qty <= 0:
        raise ValueError("Quantity must be greater than zero")

    # Decide final values
    final_price = new_price if new_price is not None else old_price
    final_barcode = new_barcode if new_barcode else old_barcode
    final_min_qty = new_min_qty if new_min_qty is not None else old_min_qty

    # Use YOUR existing DB logic (this is important)
    Database.add_stock(
        product_id=product_id,
        added_qty=added_qty,
        new_price=final_price,
        user_id=user_id,
        note=note
    )

    # Update barcode / min_quantity if changed
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("""
        UPDATE products
        SET barcode = ?, min_quantity = ?
        WHERE id = ?
    """, (final_barcode, final_min_qty, product_id))

    conn.commit()
    conn.close()

def get_product_by_name_or_barcode_sells(value):
    conn = Database.get_connection()
    c = conn.cursor()

    query = """
        SELECT id, name, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE name LIKE ? OR barcode = ?
    """

    params = (f"%{value}%", value)

    c.execute(query, params)
    data = c.fetchall()
    conn.close()
    return data


def get_product_by_name_or_barcode(name, barcode):
    conn = Database.get_connection()
    c = conn.cursor()

    query = """
        SELECT id, name, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE 1=1
    """
    params = []

    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")

    if barcode:
        query += " AND barcode = ?"
        params.append(barcode)

    c.execute(query, params)
    data = c.fetchall()
    conn.close()
    return data


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
        SELECT id,created_at ,name, barcode, sell_price, quantity, min_quantity
        FROM products
        WHERE quantity <= min_quantity
        ORDER BY quantity ASC
    """)
    data = c.fetchall()
    conn.close()
    return data

def get_inventory_history(from_date=None, to_date=None):
    conn = Database.get_connection()
    c = conn.cursor()

    query = """
        SELECT 
            il.id,
            il.created_at,
            IFNULL(p.name, '[DELETED PRODUCT]') as product_name,
            il.action,
            il.old_quantity,
            il.quantity_change,
            il.new_quantity,
            il.old_price,
            il.new_price,
            il.note
        FROM inventory_log il
        LEFT JOIN products p ON p.id = il.product_id
        WHERE 1=1
    """
    params = []

    if from_date:
        query += " AND DATE(il.created_at) >= DATE(?)"
        params.append(from_date)

    if to_date:
        query += " AND DATE(il.created_at) <= DATE(?)"
        params.append(to_date)

    query += " ORDER BY il.created_at DESC"

    c.execute(query, params)
    rows = c.fetchall()

    conn.close()
    return rows


def get_user_id(username:str):
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT id FROM users
        WHERE username = ?
    """, (username,))

    result = c.fetchone()[0]

    conn.close()
    return result



# Customers Helpers

def get_customers():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, current_debt FROM customers")
    rows = c.fetchall()
    conn.close()
    return rows


def get_or_create_customer(name, phone):
    conn = Database.get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM customers WHERE name = ?", (name,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    c.execute(
        "INSERT INTO customers (name, phone) VALUES (?, ?)",
        (name, phone)
    )
    cid = c.lastrowid
    conn.commit()
    conn.close()
    return cid



def get_sale_items(sale_id: int):

    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT product_id, product_name_at_sale, qty, price
            FROM sale_items
            WHERE sale_id = ?
        """, (sale_id,))
        rows = c.fetchall()
        if not rows:
            return []

        result = []
        for row in rows:
            result.append({
                'product_id': row[0],
                'name': row[1],
                'qty': row[2],
                'price': row[3]
            })
        return result
    finally:
        conn.close()


def get_product_by_id(product_id):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, name, barcode, sell_price, quantity, min_quantity
            FROM products
            WHERE id = ?
        """, (product_id,))
        return c.fetchone()
    finally:
        conn.close()


def get_all_users():
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, username, password, role FROM users
        """)
        data = c.fetchall()
        return data
    finally:
        conn.close()

def add_user(username, password, role):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (username, password, role) VALUES (?,?,?)
        """, (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def search_user(username):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id ,username, password, role FROM users WHERE username LIKE ?
        """,  (f"%{username}%",))
        data = c.fetchall()
        return data
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_user(username, password, role, id):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE users 
            SET username = ?, password = ?, role = ? 
            WHERE id = ?
        """,(username,password, role, id))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_user(id):
    conn = Database.get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            DELETE FROM users WHERE id = ?
        """,(id,))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()
