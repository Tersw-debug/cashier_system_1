from tkinter import *
import tkinter as tk
from tkinter import simpledialog, messagebox
from Services.cashier_service import *
from Domain.cart import Cart
from Domain.sale import Sale
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def open_cashier(username):
        win = Tk()
        win.title("Cashier")
        width = win.winfo_screenwidth()
        height = win.winfo_screenheight()
        win.geometry("%dx%d" % (width,height))
        menu = tk.Menu(win)
        win.config(menu=menu)
                
        filemenu = tk.Menu(menu)
        menu.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label='New')
        filemenu.add_command(label="Open...")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=menu.quit)
        helpmenu = tk.Menu(menu)
        menu.add_cascade(label="Help", menu=helpmenu)
        helpmenu.add_command(label="About")



        cart = Cart()

        lst = Listbox(win, width=80)
        lst.pack()

        e = Entry(win)
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

        Button(win, text="Add", command=add).pack()
        Button(win, text="Checkout", command=checkout).pack()
        win.mainloop()
