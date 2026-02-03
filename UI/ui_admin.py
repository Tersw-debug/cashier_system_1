from tkinter import *
import customtkinter
from Services.admin_service import *
from UI.router import go_login
import cv2
from pyzbar.pyzbar import decode
from tkinter import messagebox
from Domain.product import Product
from datetime import datetime

username = ""

def getUsername(username_from_login):
    global username
    username = username_from_login


def open_add_product():
    win = Toplevel()
    win.title("إضافة صنف جديد")
    win.geometry("500x500")
    win.grab_set()
    win.configure(bg="#3a4247")

    win.grid_columnconfigure(0, weight=1)
    win.grid_columnconfigure(1, weight=1)


    price_var = StringVar()
    qty_var = StringVar()
    total_var = StringVar(value="0.00")


    def calculate_total(*args):
        try:
            price = float(price_var.get())
            qty = int(qty_var.get())
            total_var.set(f"{price * qty:.2f}")
        except ValueError:
            total_var.set("0.00")

    def save():
        time = dateEntry.get().strip()
        name = nameEntry.get().strip()
        barcode = barcodeEntry.get().strip()
        price = price_var.get().strip()
        qty = qty_var.get().strip()
        total = total_var.get().strip()


        if not all([time,name, barcode, price, qty]):
            messagebox.showerror("خطأ", "جميع الحقول مطلوبة")
            return

        try:
            price = float(price)
            qty = int(qty)
            
        except ValueError:
            messagebox.showerror("خطأ", "السعر أو الكمية غير صحيحة")
            return

        
        product = Product(time,name, barcode, price, qty, total)
        add_product(product.time ,product.name, product.barcode, product.price, product.qty, product.total)

        messagebox.showinfo("تم", "تم حفظ الصنف بنجاح")
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

    customtkinter.CTkLabel(
        win,
        text=" الوقت ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=0, column=1,sticky="ew" ,padx=5, pady=5)
    dateEntry = customtkinter.CTkEntry(
        win,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    dateEntry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)


    dateEntry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    customtkinter.CTkLabel(
        win,
        text="اسم الصنف",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=1, column=1,sticky="ew" ,padx=5, pady=5)
    nameEntry = customtkinter.CTkEntry(
        win,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    nameEntry.grid(row=1, column=0, sticky="ew", padx=5, pady=5)


    customtkinter.CTkLabel(
        win,
        text=" الباركود ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=2, column=1,sticky="ew" ,padx=5, pady=5)
    barcodeEntry = customtkinter.CTkEntry(
        win,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    barcodeEntry.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" السعر ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=3, column=1,  sticky="ew", padx=5, pady=5)
    
    
    priceEntry = customtkinter.CTkEntry(
        win,
        textvariable=price_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    priceEntry.grid(row=3, column=0,  sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" الكمية ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=4, column=1,  sticky="ew", padx=5, pady=5)
    quantityEntry = customtkinter.CTkEntry(
        win,
        textvariable=qty_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
        
    )
    quantityEntry.grid(row=4, column=0,  sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" الاجمالي ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=5, column=1,  sticky="ew", padx=5, pady=5)
    totalEntry = customtkinter.CTkEntry(
        win,
        textvariable=total_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER,
        state="readonly"
        
    )
    totalEntry.grid(row=5, column=0,  sticky="ew", padx=5, pady=5)



    bottom_Frame = Frame(win, bg="#3a4247")
    bottom_Frame.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor=SE)


    bottom_Frame.grid_columnconfigure(0, weight=1)
    bottom_Frame.grid_columnconfigure(1, weight=1)
    bottom_Frame.grid_columnconfigure(2, weight=1)

    customtkinter.CTkButton(
        bottom_Frame,
        text='Scan',
        corner_radius=4,
        fg_color="#1f3b4d",
        text_color='white',
        width=120,
        command=scan
    ).grid(row=0, column=1, padx=5, pady=5)


    customtkinter.CTkButton(
        bottom_Frame,
        text='Save',
        corner_radius=4,
        fg_color="green",
        text_color='white',
        width=120,
        command=save
    ).grid(row=0, column=2, padx=5, pady=5)


    price_var.trace_add("write", calculate_total)
    qty_var.trace_add("write", calculate_total)




def open_add_to_storage():
    win = Toplevel()
    win.title("إضافة الي المخزن")
    win.geometry("500x500")
    win.grab_set()
    win.configure(bg="#3a4247")

    win.grid_columnconfigure(0, weight=1)
    win.grid_columnconfigure(1, weight=1)

    price_var = StringVar()
    qty_var = StringVar()
    total_var = StringVar(value="0.00")


    def calculate_total(*args):
        try:
            price = float(price_var.get())
            qty = int(qty_var.get())
            total_var.set(f"{price * qty:.2f}")
        except ValueError:
            total_var.set("0.00")

    def save():
        time = dateEntry.get().strip()
        option = value_inside.get().strip()
        barcode = barcodeEntry.get().strip()
        price = price_var.get().strip()
        qty = qty_var.get().strip()
        total = total_var.get().strip()


        if not all([time,option, barcode, price, qty]):
            messagebox.showerror("خطأ", "جميع الحقول مطلوبة")
            return

        try:
            price = float(price)
            qty = int(qty)
            
        except ValueError:
            messagebox.showerror("خطأ", "السعر أو الكمية غير صحيحة")
            return

        
        product = Product(time,option, barcode, price, qty, total)
        add_quantity_product(product.time ,product.name, product.barcode, product.price, product.qty, product.total)

        messagebox.showinfo("تم", "تم حفظ الصنف بنجاح")
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

    customtkinter.CTkLabel(
        win,
        text=" الوقت ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=0, column=1,sticky="ew" ,padx=5, pady=5)
    dateEntry = customtkinter.CTkEntry(
        win,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    dateEntry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)


    dateEntry.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    option_list = get_number_of_products()
    
    customtkinter.CTkLabel(
        win,
        text=" اختر الصنف ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=1, column=1,sticky="ew" ,padx=5, pady=5)

    value_inside = customtkinter.StringVar(win)

    value_inside.set("اختر صنف")

    optionMenu =  customtkinter.CTkOptionMenu(
        win,
        variable=value_inside,
        values=option_list,
        width=150,
        height=50,
        fg_color="white",
        text_color='black',
        anchor=CENTER,
        corner_radius=8,
        font=("Arial", 14)
    )
    optionMenu.grid(row=1, column=0,sticky="ew" ,padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" الباركود ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=2, column=1,sticky="ew" ,padx=5, pady=5)
    barcodeEntry = customtkinter.CTkEntry(
        win,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    barcodeEntry.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" السعر ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=3, column=1,  sticky="ew", padx=5, pady=5)
    
    
    priceEntry = customtkinter.CTkEntry(
        win,
        textvariable=price_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
    )
    priceEntry.grid(row=3, column=0,  sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" الكمية ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=4, column=1,  sticky="ew", padx=5, pady=5)
    quantityEntry = customtkinter.CTkEntry(
        win,
        textvariable=qty_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER
        
    )
    quantityEntry.grid(row=4, column=0,  sticky="ew", padx=5, pady=5)

    customtkinter.CTkLabel(
        win,
        text=" الاجمالي ",
        width=150,
        height=50,
        fg_color='#1f3b4d',
        text_color='white',
        corner_radius=8,
        font=("Arial", 14)
    ).grid(row=5, column=1,  sticky="ew", padx=5, pady=5)
    totalEntry = customtkinter.CTkEntry(
        win,
        textvariable=total_var,
        font=("Arial", 20),
        width=250,
        height=50,
        fg_color="white",
        text_color='black',
        justify=CENTER,
        state="readonly"
        
    )
    totalEntry.grid(row=5, column=0,  sticky="ew", padx=5, pady=5)


    bottom_Frame = Frame(win, bg="#3a4247")
    bottom_Frame.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor=SE)


    bottom_Frame.grid_columnconfigure(0, weight=1)
    bottom_Frame.grid_columnconfigure(1, weight=1)
    bottom_Frame.grid_columnconfigure(2, weight=1)

    customtkinter.CTkButton(
        bottom_Frame,
        text='Scan',
        corner_radius=4,
        fg_color="#1f3b4d",
        text_color='white',
        width=120,
        command=scan
    ).grid(row=0, column=1, padx=5, pady=5)


    customtkinter.CTkButton(
        bottom_Frame,
        text='Save',
        corner_radius=4,
        fg_color="green",
        text_color='white',
        width=120,
        command=save
    ).grid(row=0, column=2, padx=5, pady=5)


    price_var.trace_add("write", calculate_total)
    qty_var.trace_add("write", calculate_total)



def open_admin(root):

    def update_information():
        stats.delete(0, END)

        num_products = get_number_of_products()
        total_qty = get_total_quantity()

        stats.insert(END, f" {len(num_products)} :عدد الأصناف")
        stats.insert(END, f" {total_qty}  :اجمالي كميات الاصناف")




    global username
    admin = Frame(root, bg="#e9eef3")
    admin.pack(fill=BOTH, expand=True)

    header = Frame(admin, bg="#1f3b4d", height=80)
    header.pack(fill=X)

    Label(
        header,
        text="برنامج إدارة قطع غيار السيارات",
        bg="#1f3b4d",
        fg="white",
        font=("Arial", 22, "bold")
    ).pack(pady=20)

    content = Frame(admin, bg="#e9eef3")
    content.pack(fill=BOTH, expand=True, padx=10, pady=10)

    left = Frame(content, bg="#dbe4ec", width=300)
    left.pack(side=LEFT, fill=Y)

    right = Frame(content, bg="#e9eef3")
    right.pack(side=RIGHT, fill=BOTH, expand=True)



    Label(
        left,
        text="إحصائيات",
        bg="#dbe4ec",
        font=("Arial", 18, "bold")
    ).pack(pady=10)

    customtkinter.CTkButton(
        left,
        text="تحديث البيانات",
        text_color='white',
        fg_color='#1f3b4d',
        width=50,
        height=20,
        command=update_information,
        font=("Arial", 18, "bold")
    ).pack(pady=3)

    stats = Listbox(left, font=("Arial", 14), height=15)
    stats.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    update_information()

    buttons = [
        ("إضافة صنف", open_add_product),
        (" اضافة الي المخازن", open_add_to_storage),
        ("بحث", None),
        ("فاتورة بيع", None),
        ("المستخدمين", None),
        ("التقارير", None),
    ]

    row = col = 0

    for text, cmd in buttons:
        btn = customtkinter.CTkButton(
            right,
            text=text,
            width=180,
            height=100,
            font=("Arial", 16),
            command=cmd,
            text_color="white",
            fg_color="#1f3b4d"
        )
        btn.grid(row=row, column=col, padx=15, pady=15)

        col += 1
        if col == 3:
            col = 0
            row += 1


    bottom_frame = Frame(admin, bg='darkgreen')
    bottom_frame.pack(side=BOTTOM, fill=X)

    customtkinter.CTkButton(
        bottom_frame,
        text="X خروج",
        command=root.destroy,
        fg_color="red",
        text_color="white",
        width=140,
        height=40,
        font=("Arial", 18)
    ).pack(side=LEFT, padx=7, pady=7)

    customtkinter.CTkButton(
        bottom_frame,
        text="تبديل المستخدم",
        command=lambda: [admin.destroy(), go_login(root)],
        fg_color="lightblue",
        text_color="black",
        width=140,
        height=40,
        font=("Arial", 18)
    ).pack(side=LEFT, padx=7, pady=7)


   
    customtkinter.CTkLabel(
        bottom_frame,
        text= f"  {username}   اهلا بيك",
        font=("Arial", 20)
    ).pack(side=LEFT, padx=7, pady=7)




