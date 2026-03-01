import tkinter as tk
import keyring

root = tk.Tk()
root.title("Password")
root.geometry("400x400")
root.configure(bg="#f0f0f0")
password = keyring.get_password("myapp", "admin")
def copy_to_clipboard():
    root.clipboard_clear()
    root.clipboard_append(password)
    root.update()

label_pass = tk.Label(root, text="Your password: ")
label_pass.grid(row=0, column=0)

button = tk.Button(root, text="Copy Password", command=copy_to_clipboard)
button.grid(row=1, column=0)

root.mainloop()

"""
import os
from sqlcipher3 import dbapi2 as sqlite3
import hashlib

app_data = os.path.join(os.getenv("APPDATA"), "MyShop")
os.makedirs(app_data, exist_ok=True)

DB_NAME = os.path.join(app_data, "shop.db")

conn = sqlite3.connect(DB_NAME)
key = hashlib.sha256((password).encode()).hexdigest()
conn.execute("PRAGMA foreign_keys = ON")

conn.execute(f"PRAGMA key = '{key}';")

c = conn.cursor()
c.execute("SELECT * FROM users")
data = c.fetchall()
for row in data:
    print(row) """