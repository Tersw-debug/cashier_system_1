from tkinter import *
import customtkinter
from Services.admin_service import *
from UI.router import go_login
from tkinter import messagebox
import customtkinter as ctk
import os

from .sell_ui import build_sell_ui


def open_cashier(root, username):
    appearance = customtkinter.get_appearance_mode()

    theme = {
        "Dark": {
            "bg": "#121212",
            "card": "#1e1e1e",
            "text": "#ffffff",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "danger": "#e74c3c",
            "bottom_bg": "#1e1e1e",
        },
        "Light": {
            "bg": "#f4f6f8",
            "card": "#ffffff",
            "text": "#000000",
            "button_fg": "#1f3b4d",
            "button_hover": "#2c526a",
            "danger": "#e74c3c",
            "bottom_bg": "#ffffff",
        }
    }

    colors = theme[appearance]

    # clear root
    for widget in root.winfo_children():
        widget.destroy()

    # ===== MAIN FRAME =====
    cashier = customtkinter.CTkFrame(root, fg_color=colors['bg'])
    cashier.pack(fill=BOTH, expand=True)

    # ===== HEADER =====
    header = customtkinter.CTkFrame(
        cashier,
        height=80,
        fg_color=colors["button_fg"]
    )
    header.pack(fill="x")

    customtkinter.CTkLabel(
        header,
        text="صفحة الكاشير",
        font=("Segoe UI", 30, "bold"),
        text_color=colors["text"]
    ).pack(side=LEFT, padx=20)

    customtkinter.CTkLabel(
        header,
        text=f"👤 {username}",
        font=("Segoe UI", 20),
        text_color=colors["text"]
    ).pack(side=RIGHT, padx=20)

    # ===== CONTENT =====
    content = customtkinter.CTkFrame(cashier, fg_color="transparent")
    content.pack(fill=BOTH, expand=True, padx=20, pady=20)

    # 🔥 HERE IS THE MAGIC
    """  try:
        initialized = build_sell_ui(content, username)
    except Exception as exc:
        messagebox.showerror(
            "تعذر فتح الكاشير",
            f"{type(exc).__name__}: {exc}",
            parent=root,
        )
        initialized = False

    if not initialized:
        # Don't leave an empty POS area.
        for widget in content.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            content,
            text="تعذر تحميل نقطة البيع. راجع رسالة الخطأ ثم حاول مرة أخرى.",
            font=("Segoe UI", 16),
            wraplength=600,
        ).pack(padx=20, pady=30) """

    build_sell_ui(content, username)
    # ===== BOTTOM BAR =====
    bottom = customtkinter.CTkFrame(
        cashier,
        fg_color=colors["bottom_bg"],
        height=60
    )
    bottom.pack(fill=X, side=BOTTOM)

    customtkinter.CTkButton(
        bottom,
        text="X خروج",
        command=root.destroy,
        fg_color=colors["danger"],
        text_color="white",
        font=("Arial", 18)
    ).pack(side=LEFT, padx=10, pady=10)

    customtkinter.CTkButton(
        bottom,
        text="تبديل المستخدم",
        command=lambda: [cashier.destroy(), go_login(root)],
        fg_color="gray",
        text_color="white",
        font=("Arial", 18)
    ).pack(side=LEFT, padx=10, pady=10)

    customtkinter.CTkLabel(
        bottom,
        text=f"{username} : أهلاً بك",
        font=("Arial", 18),
        text_color=colors["text"]
    ).pack(side=RIGHT, padx=20)