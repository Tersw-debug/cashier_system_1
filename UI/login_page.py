from tkinter import *
import customtkinter
from UI.login_ui import login_ui

def show_login(root):

    def on_enter(event):
        loginButton.invoke()


    frame = customtkinter.CTkFrame(root, corner_radius=8, fg_color="white", width=500, height=400)
    frame.place(relx=0.5, rely=0.5, anchor=CENTER)

    Label(frame, text="Log In", font=("Arial", 22, "bold"), fg="black", bg="white").pack(pady=20)

    font_style = ("Arial", 14)

    Label(frame, text="Username", font=("Arial", 11, "bold"), fg="black", bg="white").pack(anchor=W)
    e1 = Entry(frame, justify=CENTER, width=30, font=font_style)
    e1.pack(pady=10)

    Label(frame, text="Password", font=("Arial", 11, "bold"), fg="black", bg="white").pack(anchor=W)
    e2 = Entry(frame, justify=CENTER, show="*", width=30, font=font_style)
    e2.pack(pady=10)

    loginButton = customtkinter.CTkButton(
        frame,
        text="Login",
        command=lambda: login_ui(root, e1, e2, frame),
        width=200,
        height=40,
        corner_radius=10,
        font=("Arial", 18),
        fg_color="black",
        text_color="white"
    )
    loginButton.pack(pady=20)

    root.bind('<Return>', on_enter)

    return frame