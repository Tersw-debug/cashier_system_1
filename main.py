from tkinter import *
from tkinter import messagebox
from Database.Schema import Database # init_db, add_default_users, get_connection
from UI.ui_admin import open_admin
from UI.ui_cashier import open_cashier

Database.init_db()
Database.add_default_users()

root = Tk()
root.title("Login")
#root.attributes('-fullscreen', True)
width = root.winfo_screenwidth()
height = root.winfo_screenheight()
root.geometry("%dx%d" % (width,height))
e1 = Entry(root)
e2 = Entry(root, show="*")
e1.pack(); e2.pack()

def login():
    conn = Database.get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (e1.get(), e2.get()))
    r = c.fetchone()
    conn.close()
    if r:
        root.destroy()
        if r[0] == "Admin":
            open_admin()
        else:
            open_cashier(e1.get())
    else:
        messagebox.showerror("Error", "Login Failed")

Button(root, text="Login", command=login).pack()
#root.bind('<Escape>', lambda event: root.attributes('-fullscreen', False))
root.mainloop()
