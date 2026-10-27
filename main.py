from tkinter import *
from UI.basewindow import BaseWindow
from UI.router import go_login
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from tkinter import messagebox
from Database.Schema import db, DatabaseError
from Database.migrator import MigrationError
from Database.keystore import KeyStoreError
from Services.bootstrap import ensure_first_admin

pdfmetrics.registerFont(TTFont("Amiri", "Amiri-Regular.ttf"))

APP_DB_VERSION = 2   # bumped because of the new products.section column

try:
    db.initialize()
    first_password = ensure_first_admin()
except (DatabaseError, MigrationError, KeyStoreError) as e:
    messagebox.showerror("Database error", str(e))
    raise SystemExit(1)

root = BaseWindow("Log In")

if first_password:
    messagebox.showinfo(
        "First run",
        f"Admin account created.\n\nUsername: admin\nPassword: {first_password}\n\n"
        "Write it down now. You will be asked to change it at first login."
    )

go_login(root)
root.mainloop()