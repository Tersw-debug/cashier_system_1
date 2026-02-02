from tkinter import *
import customtkinter
from Services.admin_service import *
from UI.router import go_login

def open_admin(root):

    frame = Frame(root)
    frame.pack(fill=BOTH, expand=True)

    lst = Listbox(frame, width=90)
    lst.pack(pady=10)

    def refresh():
        lst.delete(0, END)
        for p in get_products():
            lst.insert(END, f"{p[0]} | {p[1]} | {p[2]} | {p[3]} | {p[4]}")

    refresh()

    e1 = Entry(frame); e1.pack()
    e2 = Entry(frame); e2.pack()
    e3 = Entry(frame); e3.pack()
    e4 = Entry(frame); e4.pack()

    Button(
        frame,
        text="Add",
        command=lambda: [
            add_product(e1.get(), e2.get(), float(e3.get()), int(e4.get())),
            refresh()
        ]
    ).pack()

    Button(
        frame,
        text="Delete",
        command=lambda: [
            delete_product(int(lst.get(ACTIVE).split("|")[0])),
            refresh()
        ]
    ).pack()

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
