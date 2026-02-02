from tkinter import *
import customtkinter
from UI.login_ui import login_ui

def show_login(root):
    frame = Frame(root)
    frame.place(relx=0.5, rely=0.5, anchor=CENTER)

    Label(frame, text="Log In", font=("Arial", 22, "bold")).pack(pady=20)

    font_style = ("Arial", 14)

    Label(frame, text="Username", font=("Arial", 11, "bold")).pack(anchor=W)
    e1 = Entry(frame, justify=CENTER, width=25, font=font_style)
    e1.pack(pady=10)

    Label(frame, text="Password", font=("Arial", 11, "bold")).pack(anchor=W)
    e2 = Entry(frame, justify=CENTER, show="*", width=25, font=font_style)
    e2.pack(pady=10)

    customtkinter.CTkButton(
        frame,
        text="Login",
        command=lambda: login_ui(root, e1, e2, frame),
        width=200,
        height=40,
        corner_radius=10,
        font=("Arial", 18)
    ).pack(pady=20)

    return frame