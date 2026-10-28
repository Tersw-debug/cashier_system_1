from __future__ import annotations
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
from UI import rtl 
from Services import admin_service as svc

pdfmetrics.registerFont(TTFont("Amiri", "Amiri-Regular.ttf"))

APP_DB_VERSION = 2   # bumped because of the new products.section column

try:
    db.initialize()
    first_password = ensure_first_admin()
except (DatabaseError, MigrationError, KeyStoreError) as e:
    messagebox.showerror("Database error", str(e))
    raise SystemExit(1)


"""Seeds the print-shop catalog: sizes -> faces -> colour modes -> 4 products each.

Run once from main:
    from Services.seed_catalog import seed_print_catalog
    seed_print_catalog()
Safe to run again: existing sections (same name + parent) and SKUs are skipped.
"""


# =============================================================================
# EDIT THESE VARIABLES
# =============================================================================
# All money values are in the SMALLEST currency unit (100 = 1.00 EGP).

SIZES = ["A4", "A3", "A3+"]
FACES = ["one face", "double face"]
COLOR_MODES = ["black and white", "colorful"]
PAPERS = ["normal", "glossy", "sticker", "double glossy"]

# Base SELL price per sheet, for one face + black and white.
BASE_SELL_PRICE = {
    "A4":  {"normal": 100, "glossy": 200, "sticker": 300, "double glossy": 350},
    "A3":  {"normal": 200, "glossy": 400, "sticker": 600, "double glossy": 700},
    "A3+": {"normal": 250, "glossy": 500, "sticker": 750, "double glossy": 850},
}
# Base COST price per sheet (same shape).
BASE_COST_PRICE = {
    "A4":  {"normal": 50,  "glossy": 100, "sticker": 150, "double glossy": 180},
    "A3":  {"normal": 100, "glossy": 200, "sticker": 300, "double glossy": 360},
    "A3+": {"normal": 125, "glossy": 250, "sticker": 375, "double glossy": 430},
}
# Multipliers applied on top of the base prices.
FACE_MULTIPLIER = {"one face": 1.0, "double face": 1.8}
COLOR_MULTIPLIER = {"black and white": 1.0, "colorful": 2.5}

# Opening stock per product (0 = don't create a stock movement).
DEFAULT_QUANTITY = 0
MIN_QUANTITY = 10          # low-stock alert threshold
UNIT_NAME = "ورقة"          # set to None to leave products without a unit

# Per-product exceptions. Key: (size, face, color_mode, paper) -> value.
SELL_PRICE_OVERRIDES: dict[tuple[str, str, str, str], int] = {
    # ("A4", "one face", "colorful", "normal"): 500,
}
QUANTITY_OVERRIDES: dict[tuple[str, str, str, str], float] = {
    # ("A4", "one face", "black and white", "normal"): 5000,
}

# Product box colours: one hue family per size, one shade per paper type.
PRODUCT_COLORS = {
    "A4":  {"normal": "#1F6AA5", "glossy": "#2E86C1", "sticker": "#154B7A", "double glossy": "#3498DB"},
    "A3":  {"normal": "#1E8449", "glossy": "#239B56", "sticker": "#145A32", "double glossy": "#27AE60"},
    "A3+": {"normal": "#7D3C98", "glossy": "#8E44AD", "sticker": "#5B2C6F", "double glossy": "#A569BD"},
}

# Product name / SKU patterns.
NAME_TEMPLATE = "{paper} {size} - {face} - {color}"
# =============================================================================


def _find_section(name: str, parent_id: int | None):
    row = svc._fetch_one(
        "SELECT id FROM sections WHERE name=? AND COALESCE(parent_id,0)=COALESCE(?,0)",
        (name, parent_id))
    return int(row[0]) if row else None


def _ensure_section(name: str, parent_id: int | None, sort_order: int, user_id) -> int:
    existing = _find_section(name, parent_id)
    if existing:
        return existing
    return svc.save_entity("sections", {
        "name": name, "parent_id": parent_id, "sort_order": sort_order, "is_active": 1,
    }, user_id=user_id)


def _ensure_unit(user_id) -> int | None:
    if not UNIT_NAME:
        return None
    row = svc._fetch_one("SELECT id FROM units WHERE name=?", (UNIT_NAME,))
    if row:
        return int(row[0])
    return svc.save_entity("units", {"name": UNIT_NAME, "is_active": 1}, user_id=user_id)


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "+" else "-" for ch in text.upper()).strip("-")


def seed_print_catalog(username: str = "admin", warehouse_id: int | None = None) -> dict:
    user_id = svc.get_username_id(username)
    if warehouse_id is None:
        row = svc._fetch_one("SELECT id FROM warehouses WHERE is_active=1 ORDER BY is_default DESC, id LIMIT 1")
        warehouse_id = int(row[0]) if row else None

    unit_id = _ensure_unit(user_id)
    created = skipped = 0

    for s_idx, size in enumerate(SIZES, start=1):
        size_id = _ensure_section(size, None, s_idx, user_id)
        for f_idx, face in enumerate(FACES, start=1):
            face_id = _ensure_section(face, size_id, f_idx, user_id)
            for c_idx, color in enumerate(COLOR_MODES, start=1):
                leaf_id = _ensure_section(color, face_id, c_idx, user_id)
                for paper in PAPERS:
                    key = (size, face, color, paper)
                    sku = "-".join(_slug(x) for x in key)
                    if svc._fetch_one("SELECT id FROM products WHERE sku=?", (sku,)):
                        skipped += 1
                        continue

                    multiplier = FACE_MULTIPLIER[face] * COLOR_MULTIPLIER[color]
                    sell = SELL_PRICE_OVERRIDES.get(key, round(BASE_SELL_PRICE[size][paper] * multiplier))
                    cost = round(BASE_COST_PRICE[size][paper] * multiplier)
                    qty = QUANTITY_OVERRIDES.get(key, DEFAULT_QUANTITY)

                    product_id = svc.save_entity("products", {
                        "sku": sku,
                        "name": NAME_TEMPLATE.format(paper=paper, size=size, face=face, color=color),
                        "section_id": leaf_id,
                        "unit_id": unit_id,
                        "color": PRODUCT_COLORS[size][paper],
                        "cost_price": cost,
                        "sell_price": sell,
                        "min_quantity": MIN_QUANTITY,
                        "track_stock": 1,
                        "is_active": 1,
                    }, user_id=user_id)

                    if qty and warehouse_id:
                        svc.add_stock_adjustment(product_id, warehouse_id, qty, "OPENING",
                                                 cost, user_id, "Opening stock (catalog seed)")
                    created += 1

    return {"created": created, "skipped": skipped}

#print(seed_print_catalog())

root = BaseWindow("Log In")

if first_password:
    messagebox.showinfo(
        "First run",
        f"Admin account created.\n\nUsername: admin\nPassword: {first_password}\n\n"
        "Write it down now. You will be asked to change it at first login."
    )


go_login(root)
root.mainloop()