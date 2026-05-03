from tkinter import *
import customtkinter
from Services.admin_service import *
from UI.router import go_login
import cv2
from pyzbar.pyzbar import decode
from tkinter import messagebox
from Domain.product import Product
from datetime import datetime
from tkinter import ttk
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image
import os
import re
import openpyxl

def build_sell_ui(parent, username):
    
    bg_color = ("#ffffff", "#121212")
    card_color = ("#f8f9fa", "#1e1e1e")
    text_color = ("#000000", "#ffffff")
    win = customtkinter.CTkFrame(parent, fg_color="transparent")
    win.pack(fill=BOTH, expand=True, padx=15, pady=15)

    appearance = customtkinter.get_appearance_mode()
    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]


    main = customtkinter.CTkFrame(win, fg_color="transparent")
    main.pack(fill=BOTH, expand=True, padx=15, pady=15)


    # ================= LEFT (SALE FORM) =================
    left = customtkinter.CTkFrame(main, fg_color=card, corner_radius=15)
    left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))


    

    style = ttk.Style()
    style.theme_use("default")

    style.configure(
        "Treeview",
        background=card,
        foreground=text,
        rowheight=35,
        fieldbackground=card,
        bordercolor="#333333",
        font=("Arial", 18)
    )

    style.configure(
        "Treeview.Heading",
        background=bg,
        foreground=text,
        font=("Arial", 18, "bold")
    )

    style.map(
        "Treeview",
        background=[("selected", "#333333")],
        foreground=[("selected", "#ffffff")]
    )

    tree = ttk.Treeview(
        left,
        columns=("id","name", "barcode", "price", "qty","total"),
        show="headings"
    )

    for col, txt, w in [
        ("id", "ID", 40),
        ("name", "الاسم", 150),
        ("barcode", "باركود", 120),
        ("price", "السعر", 80),
        ("qty", "الكمية", 80),
        ("total", "الاجمالي", 80),
    ]:
        tree.heading(col, text=txt)
        tree.column(col, width=w, anchor=CENTER)

    tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

    
    

    right = customtkinter.CTkFrame(main, fg_color=card, corner_radius=15, width=380)
    right.pack(side=RIGHT, fill=Y)
    right.pack_propagate(False)


    product_id = None
    qty_var = StringVar(value="1")
    paid_var = StringVar()
    customer_name = StringVar()
    customer_phone = StringVar()
    customer_paid_var = StringVar()
    is_customer = BooleanVar(value=False)


    def search_and_add(event=None):
        value = name_entry.get().strip()
        if not value:
            return

        products = get_product_by_name_or_barcode_sells(value)

        if not products:
            messagebox.showwarning("تنبيه", "المنتج غير موجود")
            return

        product = products[0]  # take first match
        add_or_increase_product(product)

        name_entry.delete(0, END)

    def add_or_increase_product(product, qty=1):
        product_id, name, barcode, price, stock, _ = product

        for item in tree.get_children():
            values = list(tree.item(item, "values"))
            if int(values[0]) == product_id:
                new_qty = int(values[4]) + qty
                total = new_qty * float(values[3])
                values[4] = new_qty
                values[5] = f"{total:.2f}"
                tree.item(item, values=values)
                return

        tree.insert(
            "",
            END,
            values=(
                product_id,
                name,
                barcode,
                f"{price:.2f}",
                qty,
                f"{price * qty:.2f}"
            )
        )


    def increase_quantity(event=None):
        item = tree.focus()
        if not item:
            return

        values = list(tree.item(item, "values"))

        price = float(values[3])
        qty = int(values[4]) + 1
        total = price * qty
        paid_var.set(total)
        values[4] = qty
        values[5] = f"{total:.2f}"

        tree.item(item, values=values)

    def delete_selected_item(event=None):
        item = tree.focus()
        if not item:
            return
        tree.delete(item)


    def select_product(event):
        nonlocal product_id
        item = tree.focus()
        if not item:
            return

        values = tree.item(item, "values")
        product_id = int(values[0])

        tree.focus_set()

    tree.bind("<<TreeviewSelect>>", select_product)
    name_entry = customtkinter.CTkEntry(
        right, placeholder_text="اسم المنتج أو الباركود",
        font=("Arial", 18)
    )
    

   


    def toggle_customer():
        if is_customer.get():
            customer_frame.pack(
                before=confirmation_button,
                fill=X,
                padx=15,
                pady=10
            )
        else:
            customer_frame.pack_forget()
            customer_name.set("")
            customer_phone.set("")
            customer_paid_var.set("")


    name_entry.pack(fill=X, padx=10, pady=5)

    customtkinter.CTkCheckBox(
        right,
        text="عميل",
        variable=is_customer,
        command=toggle_customer,
        font=("Arial", 18)
    ).pack(pady=10)

    customer_frame = customtkinter.CTkFrame(right, fg_color="transparent")

    


    customerNameEntry = customtkinter.CTkEntry(
        customer_frame,
        textvariable=customer_name,
        placeholder_text= "",
        font=("Arial", 18)
    )
    
    customerPhoneEntry = customtkinter.CTkEntry(
        customer_frame,
        textvariable=customer_phone,
        placeholder_text= "رقم العميل",
        font=("Arial", 18)
    )
    
    paid_amount = customtkinter.CTkEntry(
        customer_frame,
        textvariable=customer_paid_var,
        placeholder_text= "المبلغ المدفوع",
        font=("Arial", 18)
    )

    customtkinter.CTkLabel(
        customer_frame,
        text="اسم العميل",
        font=("Arial", 18)
    ).pack(fill=X, padx=10, pady=5)

    customerNameEntry.pack(fill=X, padx=10, pady=5)

    customtkinter.CTkLabel(
        customer_frame,
        text="رقم العميل",
        font=("Arial", 18)
    ).pack(fill=X, padx=10, pady=5)

    customerPhoneEntry.pack(fill=X, padx=10, pady=5)

    customtkinter.CTkLabel(
        customer_frame,
        text="المبلغ المدفوع",
        font=("Arial", 18)
    ).pack(fill=X, padx=10, pady=5)
    paid_amount.pack(fill=X, padx=10, pady=5)

    def confirm_sale():
        global username

        if is_customer.get():
            if not customer_name.get().strip():
                messagebox.showerror("خطأ", "يرجى إدخال اسم العميل")
                return

            if not customer_phone.get().strip():
                messagebox.showerror("خطأ", "يرجى إدخال رقم العميل")
                return

            if not customer_paid_var.get().strip():
                messagebox.showerror("خطأ", "يرجى إدخال المبلغ المدفوع")
                return


        items = []
        total_amount = 0.0

        for item in tree.get_children():
            values = tree.item(item, "values")

            pid = int(values[0])
            qty = int(values[4])
            total = float(values[5])

            items.append((pid, qty))
            total_amount += total

        if not items:
            messagebox.showerror("خطأ", "لا يوجد منتجات في الفاتورة")
            return

        cashier_id = get_user_id(username)

        customer_id = None
        if is_customer.get():
            customer_id = get_or_create_customer(
                customer_name.get().strip(),
                customer_phone.get().strip()
            )
        amount_paid = float(customer_paid_var.get()) if is_customer.get() else total_amount
        ok, msg = Database.sell_product(
            cashier_id=cashier_id,
            items=items,
            amount_paid=amount_paid,
            customer_id=customer_id
        )

        messagebox.showinfo("النتيجة", msg)


        tree.delete(*tree.get_children())
        customer_paid_var.set("")
        customer_name.set("")
        customer_phone.set("")
        is_customer.set(False)
        customer_frame.pack_forget()

    def open_restore_dialog():
        dialog = customtkinter.CTkToplevel(parent)
        dialog.title("استرجاع بيع")
        dialog.geometry("400x250")
        dialog.grab_set()

        customtkinter.CTkLabel(dialog, text="رقم البيع").pack(pady=(20, 5))
        sale_id_entry = customtkinter.CTkEntry(dialog)
        sale_id_entry.pack(pady=5)

        customtkinter.CTkLabel(dialog, text="اسم العميل (اختياري)").pack(pady=(15, 5))
        customer_entry = customtkinter.CTkEntry(dialog)
        customer_entry.pack(pady=5)

        def submit():
            restore_sale(
                sale_id_entry.get(),
                customer_entry.get().strip(),
                dialog
            )

        customtkinter.CTkButton(
            dialog,
            text="استرجاع",
            command=submit
        ).pack(pady=20)


    def restore_sale(sale_id_input, customer_name_input, dialog):

        try:
            sale_id = int(sale_id_input)
        except (ValueError, TypeError):
            messagebox.showerror("خطأ", "رقم البيع غير صالح")
            return

        cashier_id = get_user_id(username)  # make sure 'username' is defined

        # Fetch items
        items = get_sale_items(sale_id)
        if not items:
            messagebox.showerror("خطأ", f"لا يوجد بيع بالرقم {sale_id}")
            return

        
       
        conn = Database.get_connection()
        try:
            c = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_amount = 0

            for item in items:
                total_amount += item['price'] * item['qty']

                c.execute("UPDATE products SET quantity = quantity + ? WHERE id=?", (item['qty'], item['product_id']))

                # Log inventory restoration
                c.execute("""INSERT INTO inventory_log
                             (product_id, created_at, old_price, new_price, old_quantity, quantity_change, new_quantity, action, user_id, note)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (item['product_id'], now, item['price'], item['price'], 0, item['qty'], 0,
                           "RESTORE", cashier_id, f"Restored sale ID {sale_id}"))
                
                products = get_product_by_id(item['product_id'])
                print(products)
                if products:
                    tree.insert(
                        "",
                        END,
                        values=(
                            products[0],          # product_id
                            products[1],          # name
                            products[2],          # barcode
                            f"{item['price']:.2f}",
                            item['qty'],
                            f"{item['price'] * item['qty']:.2f}"
                        )
                    )
            if customer_name_input:
                print(customer_name_input)
                c.execute("SELECT id FROM customers WHERE name = ?", (customer_name_input,))
                
                row = c.fetchone()
                if not row:
                    messagebox.showerror("خطأ", "العميل غير موجود")
                    return

                customer_id = row[0]

                c.execute("""
                    SELECT amount_paid, total 
                    FROM sales 
                    WHERE id = ? AND customer_id = ?
                """, (sale_id, customer_id,))

                row = c.fetchone()
                if not row:
                    messagebox.showerror("خطأ", "هذا البيع لا يخص هذا العميل")
                    return

                amount_paid, total = row
                
                c.execute("""
                    UPDATE customers SET current_debt = current_debt - ? WHERE name = ?
                """, ((total - amount_paid), customer_name_input,))



            c.execute("DELETE FROM sale_items WHERE sale_id=?", (sale_id,))
            c.execute("DELETE FROM sales WHERE id=?", (sale_id,))


            conn.commit()
        finally:
            conn.close()

        # 4️⃣ Now the inventory is as if nothing was sold
        messagebox.showinfo("نجاح", f"تم استرجاع البيع ID {sale_id}. يمكنك الآن تعديل وإعادة البيع.")
       
    confirmation_button = customtkinter.CTkButton(
        right,
        text="البيع تأكيد",
        height=45,
        command=confirm_sale
    )

    confirmation_button.pack(pady=15, padx=10, fill=X)

    restore_button = customtkinter.CTkButton(
        right,
        text="المشتريات استرجاع",
        height=45,
        command=open_restore_dialog
    )

    restore_button.pack(pady=15, padx=10, fill=X)

    tree.bind("<Return>", increase_quantity)
    tree.bind("<Delete>", delete_selected_item)
    name_entry.bind("<Return>", lambda e: search_and_add())



def open_cashier(root, username):
    appearance = customtkinter.get_appearance_mode()

    theme = {
        "Dark": {
            "bg": "#121212",
            "card": "#1e1e1e",
            "text": "#ffffff",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "danger": "#e74c3c",
            "bottom_bg": "#1e1e1e",
        },
        "Light": {
            "bg": "#f4f6f8",
            "card": "#ffffff",
            "text": "#000000",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "danger": "#e74c3c",
            "bottom_bg": "#ffffff",
        }
    }

    colors = theme[appearance]

    # clear root
    for widget in root.winfo_children():
        widget.destroy()

    # ===== MAIN FRAME =====
    cashier = customtkinter.CTkFrame(root, fg_color=colors['bg'])
    cashier.pack(fill=BOTH, expand=True)

    # ===== HEADER =====
    header = customtkinter.CTkFrame(
        cashier,
        height=80,
        fg_color=colors["button_fg"]
    )
    header.pack(fill="x")

    customtkinter.CTkLabel(
        header,
        text="صفحة الكاشير",
        font=("Segoe UI", 30, "bold"),
        text_color=colors["text"]
    ).pack(side=LEFT, padx=20)

    customtkinter.CTkLabel(
        header,
        text=f"👤 {username}",
        font=("Segoe UI", 20),
        text_color=colors["text"]
    ).pack(side=RIGHT, padx=20)

    # ===== CONTENT =====
    content = customtkinter.CTkFrame(cashier, fg_color="transparent")
    content.pack(fill=BOTH, expand=True, padx=20, pady=20)

    # 🔥 HERE IS THE MAGIC
    build_sell_ui(content, username)

    # ===== BOTTOM BAR =====
    bottom = customtkinter.CTkFrame(
        cashier,
        fg_color=colors["bottom_bg"],
        height=60
    )
    bottom.pack(fill=X, side=BOTTOM)

    customtkinter.CTkButton(
        bottom,
        text="X خروج",
        command=root.destroy,
        fg_color=colors["danger"],
        text_color="white",
        font=("Arial", 18)
    ).pack(side=LEFT, padx=10, pady=10)

    customtkinter.CTkButton(
        bottom,
        text="تبديل المستخدم",
        command=lambda: [cashier.destroy(), go_login(root)],
        fg_color="gray",
        text_color="white",
        font=("Arial", 18)
    ).pack(side=LEFT, padx=10, pady=10)

    customtkinter.CTkLabel(
        bottom,
        text=f"{username} : أهلاً بك",
        font=("Arial", 18),
        text_color=colors["text"]
    ).pack(side=RIGHT, padx=20)