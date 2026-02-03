from tkinter import *
from tkinter import messagebox
from Services.auth import login
from UI.router import go_admin, go_cashier
from UI.ui_admin import getUsername


def login_ui(root, entry_username, entry_password, login_frame):
    username = entry_username.get().strip()
    password = entry_password.get().strip()

    success, role = login(username, password)
    getUsername(username)
    if success:
        login_frame.destroy()

        if role == "Admin":
            go_admin(root)
        else:
            go_cashier(root, username)