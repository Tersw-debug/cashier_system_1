from tkinter import *
import tkinter as tk
import customtkinter
from tkinter import messagebox
from Database.Schema import Database # init_db, add_default_users, get_connection
from UI.basewindow import BaseWindow
from UI.router import go_login
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from Services.admin_service import get_products
pdfmetrics.registerFont(TTFont("Amiri", "Amiri-Regular.ttf"))
Database.init_db()
Database.add_default_users()




root = BaseWindow("Log In")

go_login(root)

root.mainloop()
