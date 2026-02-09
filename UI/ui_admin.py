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

def ar(text):
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def rtl_safe(text):
    text = str(text)

    # If text contains Arabic letters → reshape
    if re.search(r'[\u0600-\u06FF]', text):
        return ar(text)

    # Otherwise (English / numbers) → leave as-is
    return text


username = ""

def getUsername(username_from_login):
    global username
    username = username_from_login


def open_add_product():
    win = Toplevel()
    win.title("إضافة صنف جديد")
    win.geometry("520x640")
    win.grab_set()
    
    
    appearance = customtkinter.get_appearance_mode()
    bg_color = "#121212" if appearance == "Dark" else "#f4f6f8"
    card_color = "#1e1e1e" if appearance == "Dark" else "#ffffff"
    text_color = "#ffffff" if appearance == "Dark" else "#000000"

    win.configure(bg=bg_color)

    # ================= VARIABLES =================
    min_qty_var = StringVar()
    price_var = StringVar()
    qty_var = StringVar()
    total_var = StringVar(value="0.00")

    # ================= HELPERS =================
    def calculate_total(*args):
        try:
            total_var.set(f"{float(price_var.get()) * int(qty_var.get()):.2f}")
        except:
            total_var.set("0.00")

    def save():
        global username
        created_at = dateEntry.get().strip()
        name = nameEntry.get().strip()
        barcode = barcodeEntry.get().strip()
        price = price_var.get().strip()
        qty = qty_var.get().strip()
        min_qty = min_qty_var.get().strip()

        if not all([created_at, name, barcode, price, qty, min_qty]):
            messagebox.showerror("خطأ", "جميع الحقول مطلوبة")
            return

        try:
            price = float(price)
            qty = int(qty)
            min_qty = int(min_qty)
        except ValueError:
            messagebox.showerror("خطأ", "السعر أو الكمية غير صحيحة")
            return

        product = Product(created_at, name, barcode, price, qty, min_qty)
        add_product(
            product.created_at,
            product.name,
            product.barcode,
            product.price,
            product.qty,
            product.min_qty,
            user_id=get_user_id(username)
        )

        messagebox.showinfo("تم", "تم حفظ الصنف بنجاح")
        win.destroy()

    def scan():
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            for barcode in decode(frame):
                barcodeEntry.delete(0, END)
                barcodeEntry.insert(0, barcode.data.decode("utf-8"))
                cap.release()
                cv2.destroyAllWindows()
                return
            cv2.imshow("Scan Barcode (Q to cancel)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()

    # ================= CARD =================
    card = customtkinter.CTkFrame(
        win,
        fg_color=card_color,
        corner_radius=18
    )
    card.pack(fill=BOTH, expand=True, padx=20, pady=20)

    card.grid_columnconfigure(0, weight=1)
    card.grid_columnconfigure(1, weight=2)

    def field(label, row, var=None, readonly=False):
        customtkinter.CTkLabel(
            card,
            text=label,
            anchor="e",
            font=("Arial", 20),
            text_color=text_color
        ).grid(row=row, column=1, sticky="e", padx=10, pady=10)

        entry = customtkinter.CTkEntry(
            card,
            textvariable=var,
            height=42,
            font=("Arial", 22),
            justify="center",
            state="readonly" if readonly else "normal"
        )
        entry.grid(row=row, column=0, sticky="ew", padx=10, pady=10)
        return entry

    # ================= FIELDS =================
    dateEntry = field("الوقت", 0)
    dateEntry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    nameEntry = field("اسم الصنف", 1)
    barcodeEntry = field("الباركود", 2)
    priceEntry = field("السعر", 3, price_var)
    qtyEntry = field("الكمية", 4, qty_var)
    minQtyEntry = field("الحد الأدنى", 5, min_qty_var)
    totalEntry = field("الإجمالي", 6, total_var, readonly=True)

    # ================= FOOTER =================
    footer = customtkinter.CTkFrame(
        win,
        fg_color="transparent"
    )
    footer.pack(fill=X, padx=20, pady=(0, 20))

    footer.grid_columnconfigure(0, weight=1)
    footer.grid_columnconfigure(1, weight=1)
    footer.grid_columnconfigure(2, weight=1)

    customtkinter.CTkButton(
        footer,
        text="📷 امسح الباركود",
        height=44,
        font=("Arial", 20, "bold"),
        fg_color="#2a7fff",
        command=scan
    ).grid(row=0, column=1, padx=5, sticky="ew")

    customtkinter.CTkButton(
        footer,
        text="💾 حفظ",
        height=44,
        font=("Arial", 20, "bold"),
        fg_color="#22c55e",
        command=save
    ).grid(row=0, column=2, padx=5, sticky="ew")

    # ================= TRACES =================
    price_var.trace_add("write", calculate_total)
    qty_var.trace_add("write", calculate_total)





def open_add_to_storage():
    win = Toplevel()
    win.title("إضافة الي المخزن")
    win.geometry("500x600")
    win.grab_set()
    appearance = customtkinter.get_appearance_mode()
    bg_color = "#121212" if appearance == "Dark" else "#f4f6f8"
    card_color = "#1e1e1e" if appearance == "Dark" else "#ffffff"
    text_color = "#ffffff" if appearance == "Dark" else "#000000"

    win.configure(bg=bg_color)

    win.grid_columnconfigure(0, weight=1)
    win.grid_columnconfigure(1, weight=1)

    price_var = StringVar()
    qty_var = StringVar()
    total_var = StringVar(value="0.00")
    min_qty_var = StringVar()
    value_inside = customtkinter.StringVar(win)

    def setPrice(*args):
        try:
            name = value_inside.get().strip()
            
            if name == "اختر صنف":
                return
                
            product_price = get_product_price(name)
            if product_price is not None:
 
                price_var.set(f"{float(product_price):.2f}")
        except Exception as e:
            print(f"Error updating price: {e}")
            price_var.set("0.00")
    def calculate_total(*args):
        try:
            price = float(price_var.get())
            qty = int(qty_var.get())
            total_var.set(f"{price * qty:.2f}")
        except ValueError:
            total_var.set("0.00")

    
    def save():
        global username
        option = value_inside.get().strip()
        barcode = barcodeEntry.get().strip()
        price = price_var.get().strip()
        qty = qty_var.get().strip()
        min_qty = min_qty_var.get().strip()

        if option == "اختر صنف" or not qty:
            messagebox.showerror("خطأ", "يجب اختيار الصنف والكمية")
            return

        try:
            qty = int(qty)
            price = float(price) if price else None
            min_qty = int(min_qty) if min_qty else None
        except ValueError:
            messagebox.showerror("خطأ", "البيانات غير صحيحة")
            return

        try:
            admin_add_stock(
                product_name=option,
                added_qty=qty,
                new_price=price,
                new_barcode=barcode,
                new_min_qty=min_qty,
                user_id=get_user_id(username),   # TODO: replace with logged-in admin ID
                note="إضافة مخزن"
            )
        except Exception as e:
            messagebox.showerror("خطأ", str(e))
            return

        messagebox.showinfo("تم", "تمت إضافة الكمية بنجاح")
        win.destroy()

    def scan():
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            for barcode in decode(frame):
                barcode_data = barcode.data.decode("utf-8")
                barcodeEntry.delete(0, END)
                barcodeEntry.insert(0, barcode_data)

                cap.release()
                cv2.destroyAllWindows()
                return
            cv2.imshow("Scan Barcode - Press Q to cancel", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()

    card = customtkinter.CTkFrame(
        win,
        fg_color=card_color,
        corner_radius=18
    )
    card.pack(fill=BOTH, expand=True, padx=20, pady=20)

    card.grid_columnconfigure(0, weight=1)
    card.grid_columnconfigure(1, weight=2)

    def field(label, row, var=None, readonly=False):
        customtkinter.CTkLabel(
            card,
            text=label,
            anchor="e",
            font=("Arial", 20),
            text_color=text_color
        ).grid(row=row, column=1, sticky="e", padx=10, pady=10)

        entry = customtkinter.CTkEntry(
            card,
            textvariable=var,
            height=42,
            font=("Arial", 22),
            justify="center",
            corner_radius=8,
            state="readonly" if readonly else "normal"
        )
        entry.grid(row=row, column=0, sticky="ew", padx=10, pady=10)
        return entry

    

    option_list = get_number_of_products()
    dateEntry = field("الوقت", 0)
    dateEntry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    customtkinter.CTkLabel(
        card,
        text=" اختر الصنف ",
        anchor="e",
        font=("Arial", 20),
        text_color=text_color
    ).grid(row=1, column=1,sticky="ew" ,padx=10, pady=10)

    

    value_inside.set("اختر صنف")

    optionMenu = customtkinter.CTkOptionMenu(
        card,
        variable=value_inside,
        values=option_list,
        height=42,
        font=("Arial", 22),
        anchor="center",
        corner_radius=8,
    )
    optionMenu.grid(row=1, column=0,sticky="ew" ,padx=10, pady=10)

    barcodeEntry = field("الباركود", 2)
    priceEntry = field("السعر", 3, price_var)
    qtyEntry = field("الكمية", 4, qty_var)
    minQtyEntry = field("الحد الأدنى", 5, min_qty_var)
    totalEntry = field("الإجمالي", 6, total_var, readonly=True)


    footer = customtkinter.CTkFrame(win, fg_color="transparent")
    footer.pack(fill=X, padx=20, pady=(0, 20))

    footer.grid_columnconfigure(0, weight=1)
    footer.grid_columnconfigure(1, weight=1)
    footer.grid_columnconfigure(2, weight=1)

    customtkinter.CTkButton(
        footer,
        text="📷 امسح الباركود",
        height=44,
        font=("Arial", 20, "bold"),
        fg_color="#2a7fff",
        command=scan
    ).grid(row=0, column=1, padx=5, sticky="ew")

    customtkinter.CTkButton(
        footer,
        text="💾 حفظ",
        height=44,
        font=("Arial", 20, "bold"),
        fg_color="#22c55e",
        command=save
    ).grid(row=0, column=2, padx=5, sticky="ew")


    price_var.trace_add("write", calculate_total)
    qty_var.trace_add("write", calculate_total)
    value_inside.trace_add("write", setPrice)



def open_search_update_page():
    win = Toplevel()
    win.title("البحث وتعديل البيانات")
    win.geometry("1100x750") # Slightly wider for better breathing room
    win.grid_columnconfigure(0, weight=2)
    win.grid_columnconfigure(1, weight=1)

    bg_color = ("#ffffff", "#121212") 
    card_color = ("#f8f9fa", "#1e1e1e") 
    text_color = ("#000000", "#ffffff")         
    appearance = customtkinter.get_appearance_mode()

    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]

    win.configure(bg=bg)

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


    min_qty_var = StringVar()
    price_var = StringVar()
    qty_var = StringVar()
    total_var = StringVar(value="0.0")

    get_id = {}

    def searchProduct(event=None): 
        name = nameEntry.get().strip()
        barcode = barcodeEntry.get().strip()

       
        if not name and not barcode:
            load_all_products()
            return

       
        products = get_product_by_name_or_barcode(name, barcode)
        load_results(products)


    def deleteProduct():
        global username
        if not selected_product_id:
            messagebox.showwarning("تنبيه", "من فضلك اختر منتج أولاً")
            return

        confirm = messagebox.askyesno(
            "تأكيد الحذف",
            "هل أنت متأكد من حذف هذا المنتج نهائيًا؟\nسيتم تسجيل العملية في سجل المخزون."
        )

        if not confirm:
            return

        try:
            delete_product(
                pid=selected_product_id,
                user_id=get_user_id(username)  # TODO: admin id الحقيقي
            )

            messagebox.showinfo("تم", "تم حذف المنتج بنجاح")

            # refresh UI
            load_all_products()

            # clear fields
            nameEntry.delete(0, END)
            barcodeEntry.delete(0, END)
            price_var.set("")
            qty_var.set("")
            min_qty_var.set("")
            total_var.set("0.00")

        except Exception as e:
            messagebox.showerror("خطأ", str(e))

        
    def calculate_total(*args):
        try:
            price = float(price_var.get())
            qty = int(qty_var.get())
            total_var.set(f"{price * qty:.2f}")
        except ValueError:
            total_var.set("0.00")
            
    price_var.trace_add("write", calculate_total)
    qty_var.trace_add("write", calculate_total)


    main_container = customtkinter.CTkFrame(win, fg_color="transparent")
    main_container.pack(fill=BOTH, expand=True, padx=20, pady=20)


    leftFrame = customtkinter.CTkFrame(main_container, fg_color=card_color, corner_radius=15)
    leftFrame.pack(side=LEFT, fill=BOTH, expand=TRUE, padx=(0, 10))

    selected_product_id = None
    def on_select(event):
        nonlocal selected_product_id

        selected = tree.focus()
        if not selected:
            return

        values = tree.item(selected, "values")

        selected_product_id = values[0]

        nameEntry.delete(0, END)
        nameEntry.insert(0, values[1])

        barcodeEntry.delete(0, END)
        barcodeEntry.insert(0, values[2])

        price_var.set(values[3])
        qty_var.set(values[4])
        min_qty_var.set(values[5])

        


    def load_results(products):
        tree.delete(*tree.get_children())
        for p in products:
            tree.insert("", END, values=p)

    def load_all_products():
        products_from_database = get_products()
        load_results(products_from_database)


    columns = ("id", "name", "barcode", "price", "qty", "min_qty")

    tree = ttk.Treeview(leftFrame, columns=columns, show="headings")

    tree.heading("id", text="ID")
    tree.heading("name", text="الاسم")
    tree.heading("barcode", text="الباركود")
    tree.heading("price", text="السعر")
    tree.heading("qty", text="الكمية")
    tree.heading("min_qty", text="الحد الادني")

    tree.column("id", width=50, anchor=CENTER)
    tree.column("name", width=150)
    tree.column("barcode", width=120)
    tree.column("price", width=80, anchor=CENTER)
    tree.column("qty", width=80, anchor=CENTER)
    tree.column("min_qty", width=80, anchor=CENTER)

    tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

    tree.bind("<<TreeviewSelect>>", on_select)

    load_all_products()

    rightFrame = customtkinter.CTkFrame(main_container, fg_color=card_color, width=350, corner_radius=15)
    rightFrame.pack(side=RIGHT, fill=Y, padx=(10, 0))

    def update_product():
        global username
        if not selected_product_id:
            messagebox.showwarning("Error", "No product selected")
            return
        name = nameEntry.get().strip()
        barcode = barcodeEntry.get().strip()
        price = price_var.get().strip()
        qty = qty_var.get().strip()
        min_qty = min_qty_var.get().strip()
        update_product_data(
            pid=selected_product_id,
            name=name,
            barcode=barcode,
            price=price,
            new_qty=qty,
            min_qty=min_qty,
            user_id=get_user_id(username)  # TODO: replace with logged-in admin
        )
        
        messagebox.showinfo("Success", "Product updated")


    def on_barcode_enter(event):
        barcode = barcodeEntry.get().strip()
        if barcode:
            products = get_product_by_name_or_barcode("", barcode)
            load_results(products)

   


    def on_name_enter(event):
        name = nameEntry.get().strip()
        if name:
            products = get_product_by_name_or_barcode(name, "")  # empty barcode
            load_results(products)
    

    customtkinter.CTkLabel(
        rightFrame,
        text=" الوقت ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=0, column=1,sticky="ew" ,padx=5, pady=5)
    dateEntry = customtkinter.CTkEntry(
        rightFrame,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
    )
    dateEntry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)


    dateEntry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    customtkinter.CTkLabel(
        rightFrame,
        text="اسم الصنف",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=1, column=1,sticky="ew" ,padx=5, pady=5)
    nameEntry = customtkinter.CTkEntry(
        rightFrame,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
    )
    nameEntry.grid(row=1, column=0, sticky="ew", padx=5, pady=5)


    customtkinter.CTkLabel(
        rightFrame,
        text=" الباركود ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=2, column=1,sticky="ew" ,padx=5, pady=5)
    barcodeEntry = customtkinter.CTkEntry(
        rightFrame,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
    )
    barcodeEntry.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        rightFrame,
        text=" السعر ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=3, column=1,  sticky="ew", padx=5, pady=5)
    
    
    priceEntry = customtkinter.CTkEntry(
        rightFrame,
        textvariable=price_var,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
    )
    priceEntry.grid(row=3, column=0,  sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        rightFrame,
        text=" الكمية ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=4, column=1,  sticky="ew", padx=5, pady=5)
    quantityEntry = customtkinter.CTkEntry(
        rightFrame,
        textvariable=qty_var,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
        
    )
    quantityEntry.grid(row=4, column=0,  sticky="ew", padx=5, pady=5)
    
    
    customtkinter.CTkLabel(
        rightFrame,
        text=" الحد الادني ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=5, column=1,  sticky="ew", padx=5, pady=5)
    minQuantityEntry = customtkinter.CTkEntry(
        rightFrame,
        textvariable=min_qty_var,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER
        
    )
    minQuantityEntry.grid(row=5, column=0,  sticky="ew", padx=5, pady=5)


    customtkinter.CTkLabel(
        rightFrame,
        text=" الاجمالي ",
        width=150,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        text_color=text_color,
        corner_radius=8,
        font=("Arial", 20)
    ).grid(row=6, column=1,  sticky="ew", padx=5, pady=5)
    totalEntry = customtkinter.CTkEntry(
        rightFrame,
        textvariable=total_var,
        font=("Arial", 22),
        width=250,
        height=50,
        fg_color=("#ffffff", "#2b2b2b"),
        border_color=("#000000", "#ffffff"),
        justify=CENTER,
        state="readonly"
        
    )
    totalEntry.grid(row=6, column=0,  sticky="ew", padx=5, pady=5)



    buttons_frame = customtkinter.CTkFrame(rightFrame)
    buttons_frame.grid(
        row=7,
        column=0,
        columnspan=2,
        sticky="ew",
        pady=15
    )

    buttons_frame.grid_columnconfigure(0, weight=1)

    customtkinter.CTkButton(
        buttons_frame,
        text=" مسح ",
        height=50,
        fg_color=("#000000", "#ffffff"), 
        text_color=("#ffffff", "#000000"),
        hover_color="#333333",
        command=deleteProduct
    ).grid(row=1, column=0, padx=5, pady=5, sticky="ew")

    customtkinter.CTkButton(
        buttons_frame,
        text="حفظ التعديلات", 
        fg_color=("#000000", "#ffffff"), 
        text_color=("#ffffff", "#000000"), 
        hover_color="#333333",
        height=50,
        command=update_product
    ).grid(row=0, column=0, padx=5, pady=5, sticky="ew")


    barcodeEntry.bind("<Return>", on_barcode_enter)
    nameEntry.bind("<Return>", on_name_enter)
    nameEntry.bind("<KeyRelease>", lambda event: searchProduct())
    barcodeEntry.bind("<KeyRelease>", lambda event: searchProduct())






def open_statistics_storage_page():
    win = Toplevel()
    win.title("ارصدة المخزن")
    win.geometry("500x600")
    win.grab_set()
    bg_color = ("#ffffff", "#121212") 
    card_color = ("#f8f9fa", "#1e1e1e") 
    text_color = ("#000000", "#ffffff") 
    appearance = customtkinter.get_appearance_mode()

    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]

    win.configure(bg=bg)

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
    
    total_var = StringVar(value="0.00")
    
    def load_results(products):
        tree.delete(*tree.get_children())
        grand_total = 0.0

        for p in products:
            price = float(p[4])
            qty = int(p[5])
            row_total = price * qty
            grand_total += row_total

            tree.insert("", END, values=(
                p[0], p[1], p[2], p[3],
                f"{price:.2f}",
                qty,
                p[6],
                f"{row_total:.2f}"
            ))

        total_var.set(f"{grand_total:.2f}")

    def export_to_pdf():
        c = canvas.Canvas("storage_report.pdf", pagesize=A4)
        width, height = A4

        c.setFont("Amiri", 15)
        y = height - 50
        c.drawRightString(width - 40, y, ar("تقرير أرصدة المخزن"))

        y -= 40
        c.setFont("Amiri", 11)

        # RTL order (right ➜ left)
        headers = [
            "الإجمالي", "الحد الأدنى", "الكمية", "السعر",
            "الباركود", "الاسم", "وقت الإضافة", "المعرف"
        ]

        header_line = (
            f"{headers[7]:>6}   "    # المعرف
            f"{headers[6]:>20}   "   # وقت الإضافة
            f"{headers[5]:>18}   "   # الاسم
            f"{headers[4]:>14}   "   # الباركود
            f"{headers[3]:>8}   "    # السعر
            f"{headers[2]:>8}   "    # الكمية
            f"{headers[1]:>10}   "   # الحد الأدنى
            f"{headers[0]:>10}"      # الإجمالي
        )

        c.drawRightString(width - 40, y, ar(header_line))
        y -= 10
        c.line(40, y, width - 40, y)

        y -= 20
        c.setFont("Amiri", 10)
        row_height = 22

        for item in tree.get_children():
            v = tree.item(item)["values"]

            row = (
                f"{rtl_safe(v[7]):>10}   "   # الإجمالي
                f"{rtl_safe(v[6]):>10}   "   # الحد الأدنى
                f"{rtl_safe(v[5]):>8}   "    # الكمية
                f"{rtl_safe(v[4]):>8}   "    # السعر
                f"{rtl_safe(v[3]):>14}   "   # الباركود
                f"{rtl_safe(v[2]):>18}   "             # الاسم (English OK)
                f"{rtl_safe(v[1]):>20}   "   # وقت الإضافة
                f"{rtl_safe(v[0]):>6}"       # المعرف
            )

            c.drawRightString(width - 40, y, row)
            y -= row_height

            if y < 70:
                c.showPage()
                c.setFont("Amiri", 10)
                y = height - 50

        y -= 10
        c.setFont("Amiri", 13)
        c.drawRightString(
            width - 40,
            y,
            ar(f"الإجمالي الكلي: {total_var.get()}")
        )

        c.save()
        messagebox.showinfo("تم", "تم إنشاء ملف PDF عربي بنجاح")




    def load_all_products_storage():
        products_from_database = get_products_storage()
        load_results(products_from_database)

    
    columns = ("id", "created_at","name", "barcode", "price", "qty", "min_qty", "total")

    table_frame = Frame(win)
    table_frame.pack(fill=BOTH, expand=True)
    
    

    tree = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings"
    )

    tree.heading("id", text="ID")
    tree.heading("created_at", text="وقت الاضافة")
    tree.heading("name", text="الاسم")
    tree.heading("barcode", text="الباركود")
    tree.heading("price", text="السعر")
    tree.heading("qty", text="الكمية")
    tree.heading("min_qty", text="الحد الادني")
    tree.heading("total", text="الاجمالي")

    tree.column("id", width=50, anchor=CENTER)
    tree.column("created_at", width=50, anchor=CENTER)
    tree.column("name", width=150)
    tree.column("barcode", width=120)
    tree.column("price", width=80, anchor=CENTER)
    tree.column("qty", width=80, anchor=CENTER)
    tree.column("min_qty", width=80, anchor=CENTER)
    tree.column("total", width=100, anchor=CENTER)

    tree.pack(fill=BOTH, expand=True)

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)

    footer = customtkinter.CTkFrame(
        win,
        fg_color=card,
        corner_radius=12
    )
    footer.pack(fill=X, padx=10, pady=10)

    footer.grid_columnconfigure(0, weight=1)
    footer.grid_columnconfigure(1, weight=0)
    footer.grid_columnconfigure(2, weight=0)

    customtkinter.CTkLabel(
        footer,
        text="إجمالي قيمة المخزن :",
        font=("Arial", 20, "bold"),
        text_color=text
    ).grid(row=0, column=2, padx=10, pady=10, sticky="e")

    customtkinter.CTkEntry(
        footer,
        textvariable=total_var,
        font=("Arial", 22),
        justify="center",
        state="readonly",
        width=160,   # ✅ real width
        height=36
    ).grid(row=0, column=1, padx=10, pady=10)

    pdfButton = customtkinter.CTkButton(
        footer,
        text="📄 تصدير PDF",
        command=export_to_pdf,
        font=("Arial", 20, "bold"),
        width=180,
        height=40,
        fg_color="#1f3b4d",
        hover_color="#2a4f6b"
    )
    pdfButton.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    load_all_products_storage()



def open_products_shortage_page():
    win = Toplevel()
    win.title("ارصدة المخزن")
    win.geometry("500x600")
    win.grab_set()
    bg_color = ("#ffffff", "#121212") 
    card_color = ("#f8f9fa", "#1e1e1e") 
    text_color = ("#000000", "#ffffff") 
    appearance = customtkinter.get_appearance_mode()

    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]

    win.configure(bg=bg)

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
    
    total_var = StringVar(value="0.00")
    
    def load_results(products):
        tree.delete(*tree.get_children())
        grand_total = 0.0

        for p in products:
            price = float(p[4])
            qty = int(p[5])
            row_total = price * qty
            grand_total += row_total

            tree.insert("", END, values=(
                p[0], p[1], p[2], p[3],
                f"{price:.2f}",
                qty,
                p[6],
                f"{row_total:.2f}"
            ))

        total_var.set(f"{grand_total:.2f}")

    def export_to_pdf():
        c = canvas.Canvas("storage_report.pdf", pagesize=A4)
        width, height = A4

        c.setFont("Amiri", 15)
        y = height - 50
        c.drawRightString(width - 40, y, ar("تقرير أرصدة المخزن"))

        y -= 40
        c.setFont("Amiri", 11)

        # RTL order (right ➜ left)
        headers = [
            "الإجمالي", "الحد الأدنى", "الكمية", "السعر",
            "الباركود", "الاسم", "وقت الإضافة", "المعرف"
        ]

        header_line = (
            f"{headers[7]:>6}   "    # المعرف
            f"{headers[6]:>20}   "   # وقت الإضافة
            f"{headers[5]:>18}   "   # الاسم
            f"{headers[4]:>14}   "   # الباركود
            f"{headers[3]:>8}   "    # السعر
            f"{headers[2]:>8}   "    # الكمية
            f"{headers[1]:>10}   "   # الحد الأدنى
            f"{headers[0]:>10}"      # الإجمالي
        )

        c.drawRightString(width - 40, y, ar(header_line))
        y -= 10
        c.line(40, y, width - 40, y)

        y -= 20
        c.setFont("Amiri", 10)
        row_height = 22

        for item in tree.get_children():
            v = tree.item(item)["values"]

            row = (
                f"{rtl_safe(v[7]):>10}   "   # الإجمالي
                f"{rtl_safe(v[6]):>10}   "   # الحد الأدنى
                f"{rtl_safe(v[5]):>8}   "    # الكمية
                f"{rtl_safe(v[4]):>8}   "    # السعر
                f"{rtl_safe(v[3]):>14}   "   # الباركود
                f"{rtl_safe(v[2]):>18}   "             # الاسم (English OK)
                f"{rtl_safe(v[1]):>20}   "   # وقت الإضافة
                f"{rtl_safe(v[0]):>6}"       # المعرف
            )

            c.drawRightString(width - 40, y, row)
            y -= row_height

            if y < 70:
                c.showPage()
                c.setFont("Amiri", 10)
                y = height - 50

        y -= 10
        c.setFont("Amiri", 13)
        c.drawRightString(
            width - 40,
            y,
            ar(f"الإجمالي الكلي: {total_var.get()}")
        )

        c.save()
        messagebox.showinfo("تم", "تم إنشاء ملف PDF عربي بنجاح")




    def load_all_products_storage():
        products_from_database = get_low_stock_products()
        load_results(products_from_database)

    
    columns = ("id", "created_at","name", "barcode", "price", "qty", "min_qty", "total")

    table_frame = Frame(win)
    table_frame.pack(fill=BOTH, expand=True)
    
    

    tree = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings"
    )

    tree.heading("id", text="ID")
    tree.heading("created_at", text="وقت الاضافة")
    tree.heading("name", text="الاسم")
    tree.heading("barcode", text="الباركود")
    tree.heading("price", text="السعر")
    tree.heading("qty", text="الكمية")
    tree.heading("min_qty", text="الحد الادني")
    tree.heading("total", text="الاجمالي")

    tree.column("id", width=50, anchor=CENTER)
    tree.column("created_at", width=50, anchor=CENTER)
    tree.column("name", width=150)
    tree.column("barcode", width=120)
    tree.column("price", width=80, anchor=CENTER)
    tree.column("qty", width=80, anchor=CENTER)
    tree.column("min_qty", width=80, anchor=CENTER)
    tree.column("total", width=100, anchor=CENTER)

    tree.pack(fill=BOTH, expand=True)

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)

    footer = customtkinter.CTkFrame(
        win,
        fg_color=card,
        corner_radius=12
    )
    footer.pack(fill=X, padx=10, pady=10)

    footer.grid_columnconfigure(0, weight=1)
    footer.grid_columnconfigure(1, weight=0)
    footer.grid_columnconfigure(2, weight=0)

    customtkinter.CTkLabel(
        footer,
        text="إجمالي قيمة المخزن :",
        font=("Arial", 20, "bold"),
        text_color=text
    ).grid(row=0, column=2, padx=10, pady=10, sticky="e")

    customtkinter.CTkEntry(
        footer,
        textvariable=total_var,
        font=("Arial", 22),
        justify="center",
        state="readonly",
        width=160,   # ✅ real width
        height=36
    ).grid(row=0, column=1, padx=10, pady=10)

    pdfButton = customtkinter.CTkButton(
        footer,
        text="📄 تصدير PDF",
        command=export_to_pdf,
        font=("Arial", 20, "bold"),
        width=180,
        height=40,
        fg_color="#1f3b4d",
        hover_color="#2a4f6b"
    )
    pdfButton.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    load_all_products_storage()

def open_inventory_history_page():
    win = Toplevel()
    win.title("سجل حركة المخزون")
    win.geometry("900x600")
    win.grab_set()

    bg_color = ("#ffffff", "#121212")
    card_color = ("#f8f9fa", "#1e1e1e")
    text_color = ("#000000", "#ffffff")

    appearance = customtkinter.get_appearance_mode()
    win.configure(bg=bg_color[1] if appearance == "Dark" else bg_color[0])

    def export_excel():
        rows = get_inventory_history(
            from_var.get() or None,
            to_var.get() or None
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Inventory History"

        headers = [
            "ID", "Date", "Product", "Action",
            "Old Qty", "Change", "New Qty",
            "Old Price", "New Price", "Note"
        ]
        ws.append(headers)

        for r in rows:
            ws.append(r)

        filename = "inventory_history.xlsx"
        wb.save(filename)

        messagebox.showinfo("تم", "تم تصدير ملف Excel بنجاح")
    def export_pdf():
        rows = get_inventory_history(
            from_var.get() or None,
            to_var.get() or None
        )

        c = canvas.Canvas("inventory_history.pdf", pagesize=A4)
        width, height = A4
        y = height - 45

        # ---------- TITLE ----------
        c.setFont("Amiri", 16)
        c.drawCentredString(width / 2, y, ar("سجل حركة المخزون"))
        y -= 30

        # ---------- TABLE STRUCTURE ----------
        c.setFont("Amiri", 9)

        columns = [
            ("ID",          width - 560, lambda r: r[0]),
            ("الوقت",       width - 460, lambda r: r[1]),
            ("المنتج",      width - 380, lambda r: r[2]),
            ("العملية",     width - 340, lambda r: r[3]),
            ("الكمية قبل",  width - 280, lambda r: r[4]),
            ("التغير",      width - 230, lambda r: r[5]),
            ("الكمية بعد",  width - 180, lambda r: r[6]),
            ("السعر قبل",   width - 130, lambda r: f"{r[7]:.2f}" if r[7] is not None else ""),
            ("السعر بعد",   width - 80,  lambda r: f"{r[8]:.2f}" if r[8] is not None else ""),
            ("ملاحظة",      width - 20,  lambda r: r[9]),
        ]

        # ---------- HEADER ----------
        for title, x, _ in columns:
            c.drawRightString(x, y, ar(title))

        y -= 12
        c.line(20, y, width - 20, y)
        y -= 12

        # ---------- ROWS ----------
        for r in rows:
            for _, x, getter in columns:
                c.drawRightString(x, y, rtl_safe(getter(r)))

            y -= 16

            if y < 60:
                c.showPage()
                c.setFont("Amiri", 9)
                y = height - 45

        c.save()
        messagebox.showinfo("تم", "تم تصدير ملف PDF بنجاح")

        
   
    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]

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

    columns = (
        "id",
        "created_at",
        "name",
        "action",
        "old_qty",
        "change",
        "new_qty",
        "old_price",
        "new_price",
        "note"
    )

    filter_frame = customtkinter.CTkFrame(
    win,
    fg_color=card_color[1] if appearance == "Dark" else card_color[0],
    corner_radius=12
    )
    filter_frame.pack(fill=X, padx=10, pady=10)

    from_var = StringVar()
    to_var = StringVar()

    customtkinter.CTkLabel(
        filter_frame, text="من:", font=("Arial", 16)
    ).grid(row=0, column=0, padx=8, pady=8)

    from_entry = customtkinter.CTkEntry(
        filter_frame,
        textvariable=from_var,
        placeholder_text="YYYY-MM-DD",
        width=140
    )
    from_entry.grid(row=0, column=1, padx=8)

    customtkinter.CTkLabel(
        filter_frame, text="إلى:", font=("Arial", 16)
    ).grid(row=0, column=2, padx=8)

    to_entry = customtkinter.CTkEntry(
        filter_frame,
        textvariable=to_var,
        placeholder_text="YYYY-MM-DD",
        width=140
    )
    to_entry.grid(row=0, column=3, padx=8)


    table_frame = Frame(win)
    table_frame.pack(fill=BOTH, expand=True)

    tree = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings"
    )

    tree.heading("id", text="ID")
    tree.heading("created_at", text="الوقت")
    tree.heading("name", text="المنتج")
    tree.heading("action", text="العملية")
    tree.heading("old_qty", text="الكمية قبل")
    tree.heading("change", text="التغير")
    tree.heading("new_qty", text="الكمية بعد")
    tree.heading("old_price", text="السعر قبل")
    tree.heading("new_price", text="السعر بعد")
    tree.heading("note", text="ملاحظة")

    tree.column("id", width=50, anchor=CENTER)
    tree.column("created_at", width=150, anchor=CENTER)
    tree.column("name", width=160)
    tree.column("action", width=90, anchor=CENTER)
    tree.column("old_qty", width=90, anchor=CENTER)
    tree.column("change", width=90, anchor=CENTER)
    tree.column("new_qty", width=90, anchor=CENTER)
    tree.column("old_price", width=90, anchor=CENTER)
    tree.column("new_price", width=90, anchor=CENTER)
    tree.column("note", width=200)

    tree.pack(side=LEFT, fill=BOTH, expand=True)

    scrollbar = ttk.Scrollbar(
        table_frame,
        orient="vertical",
        command=tree.yview
    )
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=RIGHT, fill=Y)

    def load_history():
        tree.delete(*tree.get_children())

        rows = get_inventory_history(
            from_var.get() or None,
            to_var.get() or None
        )

        for r in rows:
            tree.insert("", END, values=(
                r[0], r[1], r[2], r[3],
                r[4], r[5], r[6],
                f"{r[7]:.2f}" if r[7] is not None else "",
                f"{r[8]:.2f}" if r[8] is not None else "",
                r[9] or ""
            ))

    customtkinter.CTkButton(
        filter_frame,
        text="تطبيق",
        width=120,
        height=36,
        font=("Arial", 16, "bold"),
        fg_color="#1f3b4d",
        command=load_history
    ).grid(row=0, column=4, padx=10)

    export_frame = customtkinter.CTkFrame(win, corner_radius=12)
    export_frame.pack(fill=X, padx=10, pady=10)

    customtkinter.CTkButton(
        export_frame,
        text="📄 تصدير PDF",
        width=160,
        height=40,
        font=("Arial", 18, "bold"),
        command=export_pdf,
        fg_color="#1f3b4d"
    ).pack(side=LEFT, padx=10)

    customtkinter.CTkButton(
        export_frame,
        text="📊 تصدير Excel",
        width=160,
        height=40,
        font=("Arial", 18, "bold"),
        command=export_excel,
        fg_color="#2a7f62"
    ).pack(side=LEFT, padx=10)

    load_history()


def open_statistics_page():
    win = Toplevel()
    win.title("التقارير")
    win.geometry("500x600")
    win.grab_set()

    bg_color = ("#ffffff", "#121212")
    card_color = ("#f8f9fa", "#1e1e1e")
    text_color = ("#000000", "#ffffff")

    appearance = customtkinter.get_appearance_mode()
    win.configure(bg=bg_color[1] if appearance == "Dark" else bg_color[0])

    win.grid_columnconfigure(0, weight=1)
    win.grid_columnconfigure(1, weight=1)

    buttons = [
        ("ارصدة النواقص", open_products_shortage_page),
        ("ارصدة المخزن", open_statistics_storage_page),
        ("سجل حركة المخزون", open_inventory_history_page),
        # TO DO  1 - customers log
        #        2 - sale_items
        #        3 - sales
    ]

    row = col = 0

    for text, cmd in buttons:
        btn = customtkinter.CTkButton(
            win,
            text=text,
            width=180,
            height=100,
            font=("Arial", 20, "bold"),
            command=cmd,
            text_color="white",
            fg_color="#1f3b4d"
        )
        btn.grid(row=row, column=col, padx=15, pady=15)

        col += 1
        if col > 1:
            col = 0
            row += 1



def open_sells_admin():
    win = Toplevel()
    win.title("صفحة البيع ")
    win.geometry("900x600")
    win.grab_set()

    bg_color = ("#ffffff", "#121212")
    card_color = ("#f8f9fa", "#1e1e1e")
    text_color = ("#000000", "#ffffff")
   

    appearance = customtkinter.get_appearance_mode()
    bg = bg_color[1] if appearance == "Dark" else bg_color[0]
    card = card_color[1] if appearance == "Dark" else card_color[0]
    text = text_color[1] if appearance == "Dark" else text_color[0]
    win.configure(bg=bg_color[1] if appearance == "Dark" else bg_color[0])

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
        dialog = customtkinter.CTkToplevel()
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
        text=" البيع تأكيد",
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





def open_admin(root):
    # This now updates specific labels instead of a Listbox

    appearance = customtkinter.get_appearance_mode()
    theme = {
        "Dark": {
            "bg": "#121212",
            "card": "#1e1e1e",
            "text": "#ffffff",
            "subtext": "#cccccc",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "success": "#27ae60",
            "danger": "#e74c3c",
            "bottom_bg": "#1e1e1e",
        },
        "Light": {
            "bg": "#f4f6f8",
            "card": "#ffffff",
            "text": "#000000",
            "subtext": "#555555",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "success": "#27ae60",
            "danger": "#e74c3c",
            "bottom_bg": "#ffffff",
        }
    }

    colors = theme[appearance]

    for widget in root.winfo_children():
        widget.destroy()

    def update_information():
        try:
            products = get_number_of_products()
            total_qty = get_total_quantity()

            # Handle if num_products is a list or an integer
            count = len(products) if isinstance(products, list) else products
            
            prod_count_label.configure(text=str(count))
            total_qty_label.configure(text=str(total_qty))
        except Exception as e:
            print(f"Error updating stats: {e}")

    global username
    # Main container with a clean, light background
    admin = customtkinter.CTkFrame(root, bg_color=colors['bg'], corner_radius=0)
    admin.pack(fill=BOTH, expand=True)

    # --- Header ---
    header = customtkinter.CTkFrame(admin, height=80, fg_color=colors["button_fg"], corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)

    header.grid_columnconfigure(0, weight=1)
    header.grid_columnconfigure(1, weight=3)
    header.grid_columnconfigure(2, weight=1)

    customtkinter.CTkLabel(
        header,
        text="لوحة التحكم",
        font=("Segoe UI", 32, "bold"),
        text_color=colors["text"]
    ).grid(row=0, column=1)

    customtkinter.CTkLabel(
        header,
        text=f"👤 {username}",
        font=("Segoe UI", 20),
         text_color=colors["text"]
    ).grid(row=0, column=2, sticky="e", padx=20)


    # Main content area
    content = customtkinter.CTkFrame(admin, fg_color="transparent")
    content.pack(fill=BOTH, expand=True, padx=25, pady=25)

    # --- Left Sidebar (Statistics Cards) ---
    left = customtkinter.CTkFrame(content, fg_color="transparent", width=260)
    left.pack(side=LEFT, fill=Y, padx=(0, 20))

    customtkinter.CTkLabel(
        left, text="إحصائيات المخزن",
        font=("Arial", 26, "bold"), 
        text_color=colors["text"]
    ).pack(pady=(0, 15), anchor="c")

    # Card 1: Product Count
    card1 = customtkinter.CTkFrame(left, fg_color=colors["card"], corner_radius=15, height=110)
    card1.pack(fill=X, pady=10)
    card1.pack_propagate(False)
    customtkinter.CTkLabel(card1, text="عدد الأصناف", font=("Arial", 18), text_color=colors["subtext"]).pack(pady=(15, 0))
    prod_count_label = customtkinter.CTkLabel(card1, text="0", font=("Arial", 30, "bold"), text_color=colors["button_fg"])
    prod_count_label.pack()

    # Card 2: Total Quantities
    card2 = customtkinter.CTkFrame(left, fg_color=colors["card"], corner_radius=15, height=110)
    card2.pack(fill=X, pady=10)
    card2.pack_propagate(False)
    customtkinter.CTkLabel(card2, text="إجمالي الكميات", font=("Arial", 18), text_color=colors["subtext"]).pack(pady=(15, 0))
    total_qty_label = customtkinter.CTkLabel(card2, text="0", font=("Arial", 30, "bold"), text_color=colors["success"])
    total_qty_label.pack()

    customtkinter.CTkButton(
        left, text="تحديث البيانات", 
        command=update_information, 
        fg_color=colors["button_fg"],
        hover_color=colors["button_hover"],
        height=45, 
        font=("Arial", 24, "bold")
    ).pack(fill=X, pady=20)

    # --- Right Panel (Navigation Grid) ---
    right = customtkinter.CTkFrame(content, fg_color="transparent")
    right.pack(side=RIGHT, fill=BOTH, expand=True)

    for i in range(3): right.grid_columnconfigure(i, weight=1)
    for i in range(2): right.grid_rowconfigure(i, weight=1)

    BASE_DIR = os.path.dirname(__file__)
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")


    add_image = customtkinter.CTkImage(
        Image.open(os.path.join(ASSETS_DIR, "add.png")),
        size=(50, 50)
    )
    search_image = customtkinter.CTkImage(
        Image.open( os.path.join(ASSETS_DIR, "search.png")),
        size=(50, 50)
    )
    statistics_image = customtkinter.CTkImage(
        Image.open(os.path.join(ASSETS_DIR, "statistics.png") ),
        size=(50, 50)
    )
    storage_image = customtkinter.CTkImage(
        Image.open( os.path.join(ASSETS_DIR, "storage.png")),
        size=(50, 50)
    )
    users_image = customtkinter.CTkImage(
        Image.open(os.path.join(ASSETS_DIR, "users.png")),
        size=(50, 50)
    )


    buttons = [
        ("إضافة صنف", open_add_product, add_image),
        ("إضافة للمخزن", open_add_to_storage, storage_image),
        ("بحث وتعديل", open_search_update_page, search_image),
        ("مبيعات", open_sells_admin, None),
        ("المستخدمين", None, users_image), # USERS
        ("التقارير", open_statistics_page, statistics_image),
    ]

    row = col = 0
    for text, cmd, image in buttons:
        btn = customtkinter.CTkButton(
            right, text=text, font=("Arial", 26, "bold"),
            command=cmd, fg_color=colors["button_fg"], hover_color=colors["button_hover"],
            corner_radius=15,
            image=image,
            compound=BOTTOM
        )
        btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        col += 1
        if col == 3:
            col = 0
            row += 1

    # --- Bottom Bar ---
    bottom_frame = customtkinter.CTkFrame(admin, fg_color=colors["bottom_bg"], height=60, corner_radius=0)
    bottom_frame.pack(side=BOTTOM, fill=X)
    bottom_frame.pack_propagate(False)

    customtkinter.CTkButton(
        bottom_frame, text="X خروج", command=root.destroy,
        fg_color=colors["danger"], hover_color="#c0392b", text_color="white",
        width=120, height=35, font=("Arial", 24, "bold")
    ).pack(side=LEFT, padx=15, pady=10)

    customtkinter.CTkButton(
        bottom_frame, text="تبديل المستخدم",
        command=lambda: [admin.destroy(), go_login(root)],
        fg_color="#95a5a6", hover_color="#7f8c8d", text_color="white",
        width=120, height=35, font=("Arial", 24, "bold")
    ).pack(side=LEFT, padx=10, pady=10)

    customtkinter.CTkLabel(
        bottom_frame, text=f" {username} :أهلاً بك", 
        font=("Arial", 24, "bold"), text_color=colors["text"]
    ).pack(side=RIGHT, padx=25, pady=10)

    # Initial load
    update_information()