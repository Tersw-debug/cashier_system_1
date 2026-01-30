from tkinter import *
from tkinter import messagebox
from Services.admin_service import *

def open_admin():
    win = Tk()
   # win.attributes('-fullscreen', True)
    win.title("Admin Panel")
    win.geometry("700x500")
    width = win.winfo_screenwidth()
    height = win.winfo_screenheight()
    win.geometry("%dx%d" % (width,height))
    lst = Listbox(win, width=90)
    lst.pack(pady=10)

    def refresh():
        lst.delete(0, END)
        for p in get_products():
            lst.insert(END, f"{p[0]} | {p[1]} | {p[2]} | {p[3]} | {p[4]}")

    refresh()

    e1 = Entry(win); e1.pack()
    e2 = Entry(win); e2.pack()
    e3 = Entry(win); e3.pack()
    e4 = Entry(win); e4.pack()

    Button(win, text="Add",
           command=lambda: [add_product(e1.get(), e2.get(), float(e3.get()), int(e4.get())), refresh()]
           ).pack()

    Button(win, text="Delete",
           command=lambda: [delete_product(int(lst.get(ACTIVE).split("|")[0])), refresh()]
           ).pack()

    win.mainloop()
