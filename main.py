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


"""Seeds the print-shop catalog:
category -> size -> face -> colour mode -> 4 products each (144 products).

Run once from main:
    from Services.seed_catalog import seed_print_catalog
    seed_print_catalog()
Safe to run again: existing sections (same name + parent) and SKUs are skipped.
NOTE: skipped SKUs keep their old prices/stock, so use a fresh DB to apply mock data.
"""

# =============================================================================
# EDIT THESE VARIABLES  (money = smallest currency unit, 100 = 1.00 EGP)
# =============================================================================
CATEGORY = ["جملة", "خدمة", "كتب"]
SIZES = ["A4", "A3", "A3+"]
FACES = ["one face", "double face"]
COLOR_MODES = ["black and white", "colorful"]
PAPERS = ["normal", "glossy", "sticker", "double glossy"]

BASE_SELL_PRICE = {
    "A4":  {"normal": 100, "glossy": 200, "sticker": 300, "double glossy": 350},
    "A3":  {"normal": 200, "glossy": 400, "sticker": 600, "double glossy": 700},
    "A3+": {"normal": 250, "glossy": 500, "sticker": 750, "double glossy": 850},
}
BASE_COST_PRICE = {
    "A4":  {"normal": 50,  "glossy": 100, "sticker": 150, "double glossy": 180},
    "A3":  {"normal": 100, "glossy": 200, "sticker": 300, "double glossy": 360},
    "A3+": {"normal": 125, "glossy": 250, "sticker": 375, "double glossy": 430},
}
FACE_MULTIPLIER = {"one face": 1.0, "double face": 1.8}
COLOR_MULTIPLIER = {"black and white": 1.0, "colorful": 2.5}

# Per-category rules (missing category -> 1.0 / tracked).
CATEGORY_SELL_MULTIPLIER = {"جملة": 0.8, "خدمة": 1.0, "كتب": 1.25}
CATEGORY_TRACK_STOCK = {"جملة": 1, "خدمة": 0, "كتب": 1}   # services: no stock

DEFAULT_QUANTITY = 0
MIN_QUANTITY = 10
UNIT_NAME = "ورقة"

# ---- Mock data ---------------------------------------------------------------
# Gives every product a deterministic quantity that cycles through the cases
# you want to test: out of stock, low stock, exactly at the threshold, normal, huge.
USE_MOCK_DATA = True
MOCK_QUANTITY_CYCLE = [0, 3, 8, 10, 25, 120, 500, 2500]

# Exceptions. Key: (category, size, face, color_mode, paper) -> value.
"""Full mock data: one explicit price + quantity for EVERY product (144).
Paste over SELL_PRICE_OVERRIDES / QUANTITY_OVERRIDES in seed_catalog.py.
Key: (category, size, face, color_mode, paper). Quantity cycle includes 0, low (<10),
exactly 10 (threshold), normal and large values.
NOTE: set CATEGORY_TRACK_STOCK["خدمة"] = 1 or the service quantities are ignored."""

SELL_PRICE_OVERRIDES: dict[tuple[str, str, str, str, str], int] = {
    ("جملة", "A4", "one face", "black and white", "normal"): 80,
    ("جملة", "A4", "one face", "black and white", "glossy"): 160,
    ("جملة", "A4", "one face", "black and white", "sticker"): 240,
    ("جملة", "A4", "one face", "black and white", "double glossy"): 280,
    ("جملة", "A4", "one face", "colorful", "normal"): 200,
    ("جملة", "A4", "one face", "colorful", "glossy"): 400,
    ("جملة", "A4", "one face", "colorful", "sticker"): 600,
    ("جملة", "A4", "one face", "colorful", "double glossy"): 700,
    ("جملة", "A4", "double face", "black and white", "normal"): 144,
    ("جملة", "A4", "double face", "black and white", "glossy"): 288,
    ("جملة", "A4", "double face", "black and white", "sticker"): 432,
    ("جملة", "A4", "double face", "black and white", "double glossy"): 504,
    ("جملة", "A4", "double face", "colorful", "normal"): 360,
    ("جملة", "A4", "double face", "colorful", "glossy"): 720,
    ("جملة", "A4", "double face", "colorful", "sticker"): 1080,
    ("جملة", "A4", "double face", "colorful", "double glossy"): 1260,

    ("جملة", "A3", "one face", "black and white", "normal"): 160,
    ("جملة", "A3", "one face", "black and white", "glossy"): 320,
    ("جملة", "A3", "one face", "black and white", "sticker"): 480,
    ("جملة", "A3", "one face", "black and white", "double glossy"): 560,
    ("جملة", "A3", "one face", "colorful", "normal"): 400,
    ("جملة", "A3", "one face", "colorful", "glossy"): 800,
    ("جملة", "A3", "one face", "colorful", "sticker"): 1200,
    ("جملة", "A3", "one face", "colorful", "double glossy"): 1400,
    ("جملة", "A3", "double face", "black and white", "normal"): 288,
    ("جملة", "A3", "double face", "black and white", "glossy"): 576,
    ("جملة", "A3", "double face", "black and white", "sticker"): 864,
    ("جملة", "A3", "double face", "black and white", "double glossy"): 1008,
    ("جملة", "A3", "double face", "colorful", "normal"): 720,
    ("جملة", "A3", "double face", "colorful", "glossy"): 1440,
    ("جملة", "A3", "double face", "colorful", "sticker"): 2160,
    ("جملة", "A3", "double face", "colorful", "double glossy"): 2520,

    ("جملة", "A3+", "one face", "black and white", "normal"): 200,
    ("جملة", "A3+", "one face", "black and white", "glossy"): 400,
    ("جملة", "A3+", "one face", "black and white", "sticker"): 600,
    ("جملة", "A3+", "one face", "black and white", "double glossy"): 680,
    ("جملة", "A3+", "one face", "colorful", "normal"): 500,
    ("جملة", "A3+", "one face", "colorful", "glossy"): 1000,
    ("جملة", "A3+", "one face", "colorful", "sticker"): 1500,
    ("جملة", "A3+", "one face", "colorful", "double glossy"): 1700,
    ("جملة", "A3+", "double face", "black and white", "normal"): 360,
    ("جملة", "A3+", "double face", "black and white", "glossy"): 720,
    ("جملة", "A3+", "double face", "black and white", "sticker"): 1080,
    ("جملة", "A3+", "double face", "black and white", "double glossy"): 1224,
    ("جملة", "A3+", "double face", "colorful", "normal"): 900,
    ("جملة", "A3+", "double face", "colorful", "glossy"): 1800,
    ("جملة", "A3+", "double face", "colorful", "sticker"): 2700,
    ("جملة", "A3+", "double face", "colorful", "double glossy"): 3060,

    ("خدمة", "A4", "one face", "black and white", "normal"): 100,
    ("خدمة", "A4", "one face", "black and white", "glossy"): 200,
    ("خدمة", "A4", "one face", "black and white", "sticker"): 300,
    ("خدمة", "A4", "one face", "black and white", "double glossy"): 350,
    ("خدمة", "A4", "one face", "colorful", "normal"): 250,
    ("خدمة", "A4", "one face", "colorful", "glossy"): 500,
    ("خدمة", "A4", "one face", "colorful", "sticker"): 750,
    ("خدمة", "A4", "one face", "colorful", "double glossy"): 875,
    ("خدمة", "A4", "double face", "black and white", "normal"): 180,
    ("خدمة", "A4", "double face", "black and white", "glossy"): 360,
    ("خدمة", "A4", "double face", "black and white", "sticker"): 540,
    ("خدمة", "A4", "double face", "black and white", "double glossy"): 630,
    ("خدمة", "A4", "double face", "colorful", "normal"): 450,
    ("خدمة", "A4", "double face", "colorful", "glossy"): 900,
    ("خدمة", "A4", "double face", "colorful", "sticker"): 1350,
    ("خدمة", "A4", "double face", "colorful", "double glossy"): 1575,

    ("خدمة", "A3", "one face", "black and white", "normal"): 200,
    ("خدمة", "A3", "one face", "black and white", "glossy"): 400,
    ("خدمة", "A3", "one face", "black and white", "sticker"): 600,
    ("خدمة", "A3", "one face", "black and white", "double glossy"): 700,
    ("خدمة", "A3", "one face", "colorful", "normal"): 500,
    ("خدمة", "A3", "one face", "colorful", "glossy"): 1000,
    ("خدمة", "A3", "one face", "colorful", "sticker"): 1500,
    ("خدمة", "A3", "one face", "colorful", "double glossy"): 1750,
    ("خدمة", "A3", "double face", "black and white", "normal"): 360,
    ("خدمة", "A3", "double face", "black and white", "glossy"): 720,
    ("خدمة", "A3", "double face", "black and white", "sticker"): 1080,
    ("خدمة", "A3", "double face", "black and white", "double glossy"): 1260,
    ("خدمة", "A3", "double face", "colorful", "normal"): 900,
    ("خدمة", "A3", "double face", "colorful", "glossy"): 1800,
    ("خدمة", "A3", "double face", "colorful", "sticker"): 2700,
    ("خدمة", "A3", "double face", "colorful", "double glossy"): 3150,

    ("خدمة", "A3+", "one face", "black and white", "normal"): 250,
    ("خدمة", "A3+", "one face", "black and white", "glossy"): 500,
    ("خدمة", "A3+", "one face", "black and white", "sticker"): 750,
    ("خدمة", "A3+", "one face", "black and white", "double glossy"): 850,
    ("خدمة", "A3+", "one face", "colorful", "normal"): 625,
    ("خدمة", "A3+", "one face", "colorful", "glossy"): 1250,
    ("خدمة", "A3+", "one face", "colorful", "sticker"): 1875,
    ("خدمة", "A3+", "one face", "colorful", "double glossy"): 2125,
    ("خدمة", "A3+", "double face", "black and white", "normal"): 450,
    ("خدمة", "A3+", "double face", "black and white", "glossy"): 900,
    ("خدمة", "A3+", "double face", "black and white", "sticker"): 1350,
    ("خدمة", "A3+", "double face", "black and white", "double glossy"): 1530,
    ("خدمة", "A3+", "double face", "colorful", "normal"): 1125,
    ("خدمة", "A3+", "double face", "colorful", "glossy"): 2250,
    ("خدمة", "A3+", "double face", "colorful", "sticker"): 3375,
    ("خدمة", "A3+", "double face", "colorful", "double glossy"): 3825,

    ("كتب", "A4", "one face", "black and white", "normal"): 125,
    ("كتب", "A4", "one face", "black and white", "glossy"): 250,
    ("كتب", "A4", "one face", "black and white", "sticker"): 375,
    ("كتب", "A4", "one face", "black and white", "double glossy"): 438,
    ("كتب", "A4", "one face", "colorful", "normal"): 313,
    ("كتب", "A4", "one face", "colorful", "glossy"): 625,
    ("كتب", "A4", "one face", "colorful", "sticker"): 938,
    ("كتب", "A4", "one face", "colorful", "double glossy"): 1094,
    ("كتب", "A4", "double face", "black and white", "normal"): 225,
    ("كتب", "A4", "double face", "black and white", "glossy"): 450,
    ("كتب", "A4", "double face", "black and white", "sticker"): 675,
    ("كتب", "A4", "double face", "black and white", "double glossy"): 788,
    ("كتب", "A4", "double face", "colorful", "normal"): 563,
    ("كتب", "A4", "double face", "colorful", "glossy"): 1125,
    ("كتب", "A4", "double face", "colorful", "sticker"): 1688,
    ("كتب", "A4", "double face", "colorful", "double glossy"): 1969,

    ("كتب", "A3", "one face", "black and white", "normal"): 250,
    ("كتب", "A3", "one face", "black and white", "glossy"): 500,
    ("كتب", "A3", "one face", "black and white", "sticker"): 750,
    ("كتب", "A3", "one face", "black and white", "double glossy"): 875,
    ("كتب", "A3", "one face", "colorful", "normal"): 625,
    ("كتب", "A3", "one face", "colorful", "glossy"): 1250,
    ("كتب", "A3", "one face", "colorful", "sticker"): 1875,
    ("كتب", "A3", "one face", "colorful", "double glossy"): 2188,
    ("كتب", "A3", "double face", "black and white", "normal"): 450,
    ("كتب", "A3", "double face", "black and white", "glossy"): 900,
    ("كتب", "A3", "double face", "black and white", "sticker"): 1350,
    ("كتب", "A3", "double face", "black and white", "double glossy"): 1575,
    ("كتب", "A3", "double face", "colorful", "normal"): 1125,
    ("كتب", "A3", "double face", "colorful", "glossy"): 2250,
    ("كتب", "A3", "double face", "colorful", "sticker"): 3375,
    ("كتب", "A3", "double face", "colorful", "double glossy"): 3938,

    ("كتب", "A3+", "one face", "black and white", "normal"): 313,
    ("كتب", "A3+", "one face", "black and white", "glossy"): 625,
    ("كتب", "A3+", "one face", "black and white", "sticker"): 938,
    ("كتب", "A3+", "one face", "black and white", "double glossy"): 1063,
    ("كتب", "A3+", "one face", "colorful", "normal"): 781,
    ("كتب", "A3+", "one face", "colorful", "glossy"): 1563,
    ("كتب", "A3+", "one face", "colorful", "sticker"): 2344,
    ("كتب", "A3+", "one face", "colorful", "double glossy"): 2656,
    ("كتب", "A3+", "double face", "black and white", "normal"): 563,
    ("كتب", "A3+", "double face", "black and white", "glossy"): 1125,
    ("كتب", "A3+", "double face", "black and white", "sticker"): 1688,
    ("كتب", "A3+", "double face", "black and white", "double glossy"): 1913,
    ("كتب", "A3+", "double face", "colorful", "normal"): 1406,
    ("كتب", "A3+", "double face", "colorful", "glossy"): 2813,
    ("كتب", "A3+", "double face", "colorful", "sticker"): 4219,
    ("كتب", "A3+", "double face", "colorful", "double glossy"): 4781,

}

QUANTITY_OVERRIDES: dict[tuple[str, str, str, str, str], float] = {
    ("جملة", "A4", "one face", "black and white", "normal"): 3,
    ("جملة", "A4", "one face", "black and white", "glossy"): 8,
    ("جملة", "A4", "one face", "black and white", "sticker"): 10,
    ("جملة", "A4", "one face", "black and white", "double glossy"): 25,
    ("جملة", "A4", "one face", "colorful", "normal"): 120,
    ("جملة", "A4", "one face", "colorful", "glossy"): 500,
    ("جملة", "A4", "one face", "colorful", "sticker"): 2500,
    ("جملة", "A4", "one face", "colorful", "double glossy"): 60,
    ("جملة", "A4", "double face", "black and white", "normal"): 0,
    ("جملة", "A4", "double face", "black and white", "glossy"): 3,
    ("جملة", "A4", "double face", "black and white", "sticker"): 8,
    ("جملة", "A4", "double face", "black and white", "double glossy"): 10,
    ("جملة", "A4", "double face", "colorful", "normal"): 25,
    ("جملة", "A4", "double face", "colorful", "glossy"): 120,
    ("جملة", "A4", "double face", "colorful", "sticker"): 500,
    ("جملة", "A4", "double face", "colorful", "double glossy"): 2500,

    ("جملة", "A3", "one face", "black and white", "normal"): 60,
    ("جملة", "A3", "one face", "black and white", "glossy"): 0,
    ("جملة", "A3", "one face", "black and white", "sticker"): 3,
    ("جملة", "A3", "one face", "black and white", "double glossy"): 8,
    ("جملة", "A3", "one face", "colorful", "normal"): 10,
    ("جملة", "A3", "one face", "colorful", "glossy"): 25,
    ("جملة", "A3", "one face", "colorful", "sticker"): 120,
    ("جملة", "A3", "one face", "colorful", "double glossy"): 500,
    ("جملة", "A3", "double face", "black and white", "normal"): 2500,
    ("جملة", "A3", "double face", "black and white", "glossy"): 60,
    ("جملة", "A3", "double face", "black and white", "sticker"): 0,
    ("جملة", "A3", "double face", "black and white", "double glossy"): 3,
    ("جملة", "A3", "double face", "colorful", "normal"): 8,
    ("جملة", "A3", "double face", "colorful", "glossy"): 10,
    ("جملة", "A3", "double face", "colorful", "sticker"): 25,
    ("جملة", "A3", "double face", "colorful", "double glossy"): 120,

    ("جملة", "A3+", "one face", "black and white", "normal"): 500,
    ("جملة", "A3+", "one face", "black and white", "glossy"): 2500,
    ("جملة", "A3+", "one face", "black and white", "sticker"): 60,
    ("جملة", "A3+", "one face", "black and white", "double glossy"): 0,
    ("جملة", "A3+", "one face", "colorful", "normal"): 3,
    ("جملة", "A3+", "one face", "colorful", "glossy"): 8,
    ("جملة", "A3+", "one face", "colorful", "sticker"): 10,
    ("جملة", "A3+", "one face", "colorful", "double glossy"): 25,
    ("جملة", "A3+", "double face", "black and white", "normal"): 120,
    ("جملة", "A3+", "double face", "black and white", "glossy"): 500,
    ("جملة", "A3+", "double face", "black and white", "sticker"): 2500,
    ("جملة", "A3+", "double face", "black and white", "double glossy"): 60,
    ("جملة", "A3+", "double face", "colorful", "normal"): 0,
    ("جملة", "A3+", "double face", "colorful", "glossy"): 3,
    ("جملة", "A3+", "double face", "colorful", "sticker"): 8,
    ("جملة", "A3+", "double face", "colorful", "double glossy"): 10,

    ("خدمة", "A4", "one face", "black and white", "normal"): 25,
    ("خدمة", "A4", "one face", "black and white", "glossy"): 120,
    ("خدمة", "A4", "one face", "black and white", "sticker"): 500,
    ("خدمة", "A4", "one face", "black and white", "double glossy"): 2500,
    ("خدمة", "A4", "one face", "colorful", "normal"): 60,
    ("خدمة", "A4", "one face", "colorful", "glossy"): 0,
    ("خدمة", "A4", "one face", "colorful", "sticker"): 3,
    ("خدمة", "A4", "one face", "colorful", "double glossy"): 8,
    ("خدمة", "A4", "double face", "black and white", "normal"): 10,
    ("خدمة", "A4", "double face", "black and white", "glossy"): 25,
    ("خدمة", "A4", "double face", "black and white", "sticker"): 120,
    ("خدمة", "A4", "double face", "black and white", "double glossy"): 500,
    ("خدمة", "A4", "double face", "colorful", "normal"): 2500,
    ("خدمة", "A4", "double face", "colorful", "glossy"): 60,
    ("خدمة", "A4", "double face", "colorful", "sticker"): 0,
    ("خدمة", "A4", "double face", "colorful", "double glossy"): 3,

    ("خدمة", "A3", "one face", "black and white", "normal"): 8,
    ("خدمة", "A3", "one face", "black and white", "glossy"): 10,
    ("خدمة", "A3", "one face", "black and white", "sticker"): 25,
    ("خدمة", "A3", "one face", "black and white", "double glossy"): 120,
    ("خدمة", "A3", "one face", "colorful", "normal"): 500,
    ("خدمة", "A3", "one face", "colorful", "glossy"): 2500,
    ("خدمة", "A3", "one face", "colorful", "sticker"): 60,
    ("خدمة", "A3", "one face", "colorful", "double glossy"): 0,
    ("خدمة", "A3", "double face", "black and white", "normal"): 3,
    ("خدمة", "A3", "double face", "black and white", "glossy"): 8,
    ("خدمة", "A3", "double face", "black and white", "sticker"): 10,
    ("خدمة", "A3", "double face", "black and white", "double glossy"): 25,
    ("خدمة", "A3", "double face", "colorful", "normal"): 120,
    ("خدمة", "A3", "double face", "colorful", "glossy"): 500,
    ("خدمة", "A3", "double face", "colorful", "sticker"): 2500,
    ("خدمة", "A3", "double face", "colorful", "double glossy"): 60,

    ("خدمة", "A3+", "one face", "black and white", "normal"): 0,
    ("خدمة", "A3+", "one face", "black and white", "glossy"): 3,
    ("خدمة", "A3+", "one face", "black and white", "sticker"): 8,
    ("خدمة", "A3+", "one face", "black and white", "double glossy"): 10,
    ("خدمة", "A3+", "one face", "colorful", "normal"): 25,
    ("خدمة", "A3+", "one face", "colorful", "glossy"): 120,
    ("خدمة", "A3+", "one face", "colorful", "sticker"): 500,
    ("خدمة", "A3+", "one face", "colorful", "double glossy"): 2500,
    ("خدمة", "A3+", "double face", "black and white", "normal"): 60,
    ("خدمة", "A3+", "double face", "black and white", "glossy"): 0,
    ("خدمة", "A3+", "double face", "black and white", "sticker"): 3,
    ("خدمة", "A3+", "double face", "black and white", "double glossy"): 8,
    ("خدمة", "A3+", "double face", "colorful", "normal"): 10,
    ("خدمة", "A3+", "double face", "colorful", "glossy"): 25,
    ("خدمة", "A3+", "double face", "colorful", "sticker"): 120,
    ("خدمة", "A3+", "double face", "colorful", "double glossy"): 500,

    ("كتب", "A4", "one face", "black and white", "normal"): 2500,
    ("كتب", "A4", "one face", "black and white", "glossy"): 60,
    ("كتب", "A4", "one face", "black and white", "sticker"): 0,
    ("كتب", "A4", "one face", "black and white", "double glossy"): 3,
    ("كتب", "A4", "one face", "colorful", "normal"): 8,
    ("كتب", "A4", "one face", "colorful", "glossy"): 10,
    ("كتب", "A4", "one face", "colorful", "sticker"): 25,
    ("كتب", "A4", "one face", "colorful", "double glossy"): 120,
    ("كتب", "A4", "double face", "black and white", "normal"): 500,
    ("كتب", "A4", "double face", "black and white", "glossy"): 2500,
    ("كتب", "A4", "double face", "black and white", "sticker"): 60,
    ("كتب", "A4", "double face", "black and white", "double glossy"): 0,
    ("كتب", "A4", "double face", "colorful", "normal"): 3,
    ("كتب", "A4", "double face", "colorful", "glossy"): 8,
    ("كتب", "A4", "double face", "colorful", "sticker"): 10,
    ("كتب", "A4", "double face", "colorful", "double glossy"): 25,

    ("كتب", "A3", "one face", "black and white", "normal"): 120,
    ("كتب", "A3", "one face", "black and white", "glossy"): 500,
    ("كتب", "A3", "one face", "black and white", "sticker"): 2500,
    ("كتب", "A3", "one face", "black and white", "double glossy"): 60,
    ("كتب", "A3", "one face", "colorful", "normal"): 0,
    ("كتب", "A3", "one face", "colorful", "glossy"): 3,
    ("كتب", "A3", "one face", "colorful", "sticker"): 8,
    ("كتب", "A3", "one face", "colorful", "double glossy"): 10,
    ("كتب", "A3", "double face", "black and white", "normal"): 25,
    ("كتب", "A3", "double face", "black and white", "glossy"): 120,
    ("كتب", "A3", "double face", "black and white", "sticker"): 500,
    ("كتب", "A3", "double face", "black and white", "double glossy"): 2500,
    ("كتب", "A3", "double face", "colorful", "normal"): 60,
    ("كتب", "A3", "double face", "colorful", "glossy"): 0,
    ("كتب", "A3", "double face", "colorful", "sticker"): 3,
    ("كتب", "A3", "double face", "colorful", "double glossy"): 8,

    ("كتب", "A3+", "one face", "black and white", "normal"): 10,
    ("كتب", "A3+", "one face", "black and white", "glossy"): 25,
    ("كتب", "A3+", "one face", "black and white", "sticker"): 120,
    ("كتب", "A3+", "one face", "black and white", "double glossy"): 500,
    ("كتب", "A3+", "one face", "colorful", "normal"): 2500,
    ("كتب", "A3+", "one face", "colorful", "glossy"): 60,
    ("كتب", "A3+", "one face", "colorful", "sticker"): 0,
    ("كتب", "A3+", "one face", "colorful", "double glossy"): 3,
    ("كتب", "A3+", "double face", "black and white", "normal"): 8,
    ("كتب", "A3+", "double face", "black and white", "glossy"): 10,
    ("كتب", "A3+", "double face", "black and white", "sticker"): 25,
    ("كتب", "A3+", "double face", "black and white", "double glossy"): 120,
    ("كتب", "A3+", "double face", "colorful", "normal"): 500,
    ("كتب", "A3+", "double face", "colorful", "glossy"): 2500,
    ("كتب", "A3+", "double face", "colorful", "sticker"): 60,
    ("كتب", "A3+", "double face", "colorful", "double glossy"): 0,

}

PRODUCT_COLORS = {
    "A4":  {"normal": "#1F6AA5", "glossy": "#2E86C1", "sticker": "#154B7A", "double glossy": "#3498DB"},
    "A3":  {"normal": "#1E8449", "glossy": "#239B56", "sticker": "#145A32", "double glossy": "#27AE60"},
    "A3+": {"normal": "#7D3C98", "glossy": "#8E44AD", "sticker": "#5B2C6F", "double glossy": "#A569BD"},
}

NAME_TEMPLATE = "{category} | {paper} {size} - {face} - {color}"
# =============================================================================


def _money(x: float) -> int:
    return int(x + 0.5)            # round half up


def _find_section(name, parent_id):
    row = svc._fetch_one(
        "SELECT id FROM sections WHERE name=? AND COALESCE(parent_id,0)=COALESCE(?,0)",
        (name, parent_id))
    return int(row[0]) if row else None


def _ensure_section(name, parent_id, sort_order, user_id) -> int:
    existing = _find_section(name, parent_id)
    if existing:
        return existing
    return svc.save_entity("sections", {
        "name": name, "parent_id": parent_id, "sort_order": sort_order, "is_active": 1,
    }, user_id=user_id)


def _ensure_unit(user_id):
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
        row = svc._fetch_one(
            "SELECT id FROM warehouses WHERE is_active=1 ORDER BY is_default DESC, id LIMIT 1")
        warehouse_id = int(row[0]) if row else None
    if warehouse_id is None:
        print("WARNING: no active warehouse - opening stock will be skipped.")

    unit_id = _ensure_unit(user_id)
    created = skipped = stocked = 0
    index = 0                                   # running product counter for mock cycle

    for cat_idx, cat in enumerate(CATEGORY, start=1):
        cat_id = _ensure_section(cat, None, cat_idx, user_id)
        for s_idx, size in enumerate(SIZES, start=1):
            size_id = _ensure_section(size, cat_id, s_idx, user_id)
            for f_idx, face in enumerate(FACES, start=1):
                face_id = _ensure_section(face, size_id, f_idx, user_id)
                for c_idx, color in enumerate(COLOR_MODES, start=1):
                    leaf_id = _ensure_section(color, face_id, c_idx, user_id)
                    for paper in PAPERS:
                        key = (cat, size, face, color, paper)
                        index += 1
                        sku = "-".join(_slug(x) for x in key)
                        if svc._fetch_one("SELECT id FROM products WHERE sku=?", (sku,)):
                            skipped += 1
                            continue

                        mult = FACE_MULTIPLIER[face] * COLOR_MULTIPLIER[color]
                        cat_mult = CATEGORY_SELL_MULTIPLIER.get(cat, 1.0)
                        sell = SELL_PRICE_OVERRIDES.get(
                            key, _money(BASE_SELL_PRICE[size][paper] * mult * cat_mult))
                        cost = _money(BASE_COST_PRICE[size][paper] * mult)

                        track = CATEGORY_TRACK_STOCK.get(cat, 1)
                        if not track:
                            qty = 0
                        elif key in QUANTITY_OVERRIDES:
                            qty = QUANTITY_OVERRIDES[key]
                        elif USE_MOCK_DATA:
                            qty = MOCK_QUANTITY_CYCLE[index % len(MOCK_QUANTITY_CYCLE)]
                        else:
                            qty = DEFAULT_QUANTITY

                        product_id = svc.save_entity("products", {
                            "sku": sku,
                            "name": NAME_TEMPLATE.format(category=cat, paper=paper, size=size,
                                                         face=face, color=color),
                            "section_id": leaf_id,
                            "unit_id": unit_id,
                            "color": PRODUCT_COLORS[size][paper],
                            "cost_price": cost,
                            "sell_price": sell,
                            "min_quantity": MIN_QUANTITY,
                            "track_stock": track,
                            "is_active": 1,
                        }, user_id=user_id)

                        if qty and warehouse_id:
                            svc.add_stock_adjustment(product_id, warehouse_id, qty, "OPENING",
                                                     cost, user_id, "Opening stock (catalog seed)")
                            stocked += 1
                        created += 1

    return {"created": created, "skipped": skipped, "with_stock": stocked}

print(seed_print_catalog())

root = BaseWindow("Log In")

if first_password:
    messagebox.showinfo(
        "First run",
        f"Admin account created.\n\nUsername: admin\nPassword: {first_password}\n\n"
        "Write it down now. You will be asked to change it at first login."
    )


go_login(root)
root.mainloop()