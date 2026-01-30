from tkinter import *
from tkinter import messagebox
from Services.auth import Auth
from UI.ui_admin import open_admin
from UI.ui_cashier import open_cashier

auth_service = Auth()

def login_ui(root, entry_username, entry_password):
    username = entry_username.get().strip()
    password = entry_password.get().strip()

    success, role = auth_service.login(username, password)

    if not success:
        messagebox.showerror("خطأ", "اسم المستخدم أو كلمة المرور غير صحيحة")
        return

    messagebox.showinfo("نجاح", f"تم تسجيل الدخول كـ {role}")
    root.destroy()

    if role == "Admin":
        open_admin()
    else:
        open_cashier(username)