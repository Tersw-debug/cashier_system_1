from tkinter import *
import tkinter as tk
from tkinter import simpledialog, messagebox
from Services.cashier_service import *
from Domain.cart import Cart
from Domain.sale import Sale
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import customtkinter
from UI.router import go_login


def open_cashier(root,username):
    

    frame = Frame(root)
    frame.pack(fill=BOTH, expand=True)
    cart = Cart()

    lst = Listbox(frame, width=80)
    lst.pack()

    e = Entry(frame)
    e.pack()

    def add():
        p = find_product_by_barcode(e.get())
        if not p:
            messagebox.showerror("Error", "Not Found")
            return
        qty = simpledialog.askinteger("Qty", "Enter quantity")
        if qty:
            cart.add(p[0], p[1], qty, p[2])
            lst.insert(END, f"{p[1]} x{qty} = {qty*p[2]}")

    def checkout():
        sale = Sale(username)
        total = save_sale(cart, username, sale.date)
        pdf = canvas.Canvas("invoice.pdf", pagesize=A4)
        pdf.drawString(100, 800, f"Total: {total}")
        pdf.save()
        messagebox.showinfo("Done", f"Total = {total}")
        cart.clear()
        lst.delete(0, END)

    Button(frame, text="Add", command=add).pack()
    Button(frame, text="Checkout", command=checkout).pack()
    bottom_frame = Frame(frame, bg='darkgreen')
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
        command=lambda: [frame.destroy(), go_login(root)],
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


    frame.mainloop()
