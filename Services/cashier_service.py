from Database.Schema import Database

def find_product_by_barcode(barcode):
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id,name,sell_price,quantity FROM products WHERE barcode=?", (barcode,))
    data = c.fetchone()
    conn.close()
    return data

def save_sale(cart, cashier, date):
    conn = Database.get_connection()
    c = conn.cursor()
    total = cart.total()

    c.execute("INSERT INTO sales (date,total,cashier) VALUES (?,?,?)",
              (date, total, cashier))
    sale_id = c.lastrowid

    for item in cart.items:
        pid, name, qty, price, sub = item
        c.execute(
            "INSERT INTO sale_items VALUES (?,?,?,?)",
            (sale_id, pid, qty, price)
        )
        c.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id=?",
            (qty, pid)
        )

    conn.commit()
    conn.close()
    return total