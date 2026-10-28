"""Arabic point-of-sale UI backed by the current MyShop ERP schema."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from tkinter import BOTH, CENTER, END, LEFT, RIGHT, X, Y, StringVar, BooleanVar
from tkinter import ttk, messagebox
import os
import subprocess
import sys
import customtkinter as ctk
from UI.rtl import fix

from Services.cashier_service import (
    close_cashier_shift,
    create_cashier_return,
    create_cashier_sale,
    export_cashier_sale_to_excel,
    get_cashier_session_folder,
    get_cashier_context,
    get_cashier_product_groups,
    get_cashier_products,
    get_open_shift,
    get_returnable_sales_items,
    get_username_id,
    minor_to_money,
    money_to_minor,
    open_cashier_shift,
)


WALK_IN_LABEL = "عميل نقدي"


def _valid_hex(color):
    c = (color or "").strip()
    if len(c) == 7 and c[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in c[1:]):
        return c
    return None


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _shade(color, factor):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * factor))) for v in _rgb(color))


def _text_on(color):
    r, g, b = _rgb(color)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def _quantity(value) -> Decimal:
    try:
        qty = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise ValueError("أدخل كمية رقمية صحيحة") from None
    if not qty.is_finite() or qty <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    return qty


def _qty_text(value) -> str:
    return f"{value.normalize():f}" if isinstance(value, Decimal) else str(value)


def _line_totals(product, quantity: Decimal):
    """Return base, tax, and total in integer minor currency units."""
    price_minor = int(product[4])
    tax_bp = int(product[9] or 0)
    base = int(
        (quantity * Decimal(price_minor)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    tax = int(
        (Decimal(base) * Decimal(tax_bp) / Decimal(10000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return base, tax, base + tax


def _unique_labels(rows, label_builder):
    """Create display labels without silently overwriting duplicate IDs."""
    labels = {}
    for row in rows:
        label = label_builder(row)
        if label in labels:
            label = f"{label} (#{int(row[0])})"
        labels[label] = int(row[0])
    return labels


def build_sell_ui(parent, username):
    """Mount the cashier UI; return True on success, False on setup failure."""
    top = parent.winfo_toplevel()

    try:
        cashier_id = get_username_id(str(username))
    except Exception as exc:
        messagebox.showerror(
            "تعذر فتح الكاشير",
            f"تعذر الوصول إلى حساب الكاشير:\n{type(exc).__name__}: {exc}",
            parent=top,
        )
        return False

    if cashier_id is None:
        messagebox.showerror(
            "خطأ تسجيل الدخول",
            f"لم يتم العثور على حساب مستخدم نشط باسم: {username}",
            parent=top,
        )
        return False

    appearance = ctk.get_appearance_mode()
    bg = "#121212" if appearance == "Dark" else "#f4f6f8"
    card = "#1e1e1e" if appearance == "Dark" else "#ffffff"
    text = "#ffffff" if appearance == "Dark" else "#101820"
    muted = "#aab4be" if appearance == "Dark" else "#59636e"

    for widget in parent.winfo_children():
        widget.destroy()

    try:
        context = get_cashier_context(cashier_id)
    except Exception as exc:
        messagebox.showerror(
            "خطأ قاعدة البيانات",
            f"تعذر تحميل بيانات الكاشير:\n{type(exc).__name__}: {exc}",
            parent=top,
        )
        return False

    warehouses = context.get("warehouses", [])
    methods = context.get("payment_methods", [])
    if not warehouses:
        messagebox.showerror(
            "لا يوجد مخزن",
            "أضف مخزنًا نشطًا من صفحة الإدارة قبل البيع.",
            parent=top,
        )
        return False
    if not methods:
        messagebox.showerror(
            "لا توجد طرق دفع",
            "أضف طريقة دفع نشطة مرتبطة بحساب أستاذ نشط.",
            parent=top,
        )
        return False

    warehouse_labels = {
        f"{int(row[0])} — {row[1]}": int(row[0]) for row in warehouses
    }
    default_wh = next((row for row in warehouses if row[2]), warehouses[0])
    warehouse_var = StringVar(value=f"{int(default_wh[0])} — {default_wh[1]}")

    method_labels = {}
    for row in methods:
        label = f"{row[1]} ({row[2]})"
        if label in method_labels:
            label = f"{label} (#{int(row[0])})"
        method_labels[label] = int(row[0])
    method_var = StringVar(value=next(iter(method_labels)))

    initial_shift = context.get("open_shift")
    last_shift = context.get("last_shift")
    remembered_shift = initial_shift or last_shift
    current_shift = {
        "row": initial_shift,
        "last_id": int(remembered_shift[0]) if remembered_shift else None,
    }
    customers = list(context.get("customers", []))
    customer_labels = {WALK_IN_LABEL: None}
    for cid, cname, phone in customers:
        label = f"{cname} — {phone}" if phone else str(cname)
        if label in customer_labels:
            label = f"{label} (#{cid})"
        customer_labels[label] = int(cid)

    customer_var = StringVar(value=WALK_IN_LABEL)
    new_customer_var = BooleanVar(value=False)
    new_customer_name = StringVar()
    new_customer_phone = StringVar()
    paid_var = StringVar(value="0")
    qty_var = StringVar(value="1")
    search_var = StringVar()
    total_var = StringVar(value=minor_to_money(0))
    shift_text_var = StringVar(value="جاري تحميل حالة الوردية...")
    cart: dict[int, dict] = {}

    # ---------------- main layout ----------------
    main = ctk.CTkFrame(parent, fg_color="transparent")
    main.pack(fill=BOTH, expand=True, padx=12, pady=12)

    toolbar = ctk.CTkFrame(main, fg_color=card, corner_radius=12)
    toolbar.pack(fill=X, pady=(0, 10))
    ctk.CTkLabel(
        toolbar, text="نقطة البيع", font=("Segoe UI", 23, "bold"), text_color=text
    ).pack(side=RIGHT, padx=14, pady=8)
    ctk.CTkLabel(toolbar, text="المخزن", text_color=text).pack(
        side=RIGHT, padx=(8, 2)
    )
    warehouse_menu = ctk.CTkComboBox(
        toolbar,
        variable=warehouse_var,
        values=list(warehouse_labels),
        state="readonly",
        width=190,
    )
    warehouse_menu.pack(side=RIGHT, padx=4, pady=8)
    shift_status_label = ctk.CTkLabel(
        toolbar, textvariable=shift_text_var, text_color=muted
    )
    shift_status_label.pack(side=LEFT, padx=8)
    shift_button = ctk.CTkButton(toolbar, text=fix("الوردية بدء"), width=120)
    shift_button.pack(side=LEFT, padx=10, pady=8)

    content = ctk.CTkFrame(main, fg_color="transparent")
    content.pack(fill=BOTH, expand=True)

    quick = ctk.CTkFrame(content, fg_color=card, corner_radius=12, width=250)
    quick.pack(side=LEFT, fill=Y, padx=(0, 8))
    quick.pack_propagate(False)
    ctk.CTkLabel(
        quick, text="الأصناف السريعة", font=("Arial", 18, "bold"), text_color=text
    ).pack(pady=(10, 2))
    quick_scroll = ctk.CTkScrollableFrame(quick, fg_color="transparent")
    quick_scroll.pack(fill=BOTH, expand=True, padx=6, pady=6)

    center = ctk.CTkFrame(content, fg_color=card, corner_radius=12)
    center.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))

    # Keep the fixed-width panel separate from its scrolling content. Applying
    # pack_propagate(False) directly to a CTkScrollableFrame can leave its inner
    # canvas/window with an unusable requested size on some CustomTkinter versions,
    # making the panel look empty even though its child widgets were created.
    controls = ctk.CTkFrame(
        content, fg_color=card, corner_radius=12, width=320
    )
    # Pack the fixed right panel before the expanding center panel. Otherwise,
    # the center panel can claim the available width first and squeeze the
    # checkout panel out of view on some window sizes.
    controls.pack(side=RIGHT, fill=Y, padx=(8, 0), before=center)
    controls.pack_propagate(False)

    controls_body = ctk.CTkScrollableFrame(
        controls, fg_color="transparent", corner_radius=12
    )
    controls_body.pack(fill=BOTH, expand=True, padx=0, pady=0)

    style = ttk.Style()
    style.configure(
        "Cashier.Treeview",
        background=card,
        foreground=text,
        fieldbackground=card,
        rowheight=32,
        font=("Arial", 11),
    )
    style.configure("Cashier.Treeview.Heading", font=("Arial", 11, "bold"))
    style.map(
        "Cashier.Treeview",
        background=[("selected", "#265777")],
        foreground=[("selected", "#ffffff")],
    )

    search_frame = ctk.CTkFrame(center, fg_color="transparent")
    search_frame.pack(fill=X, padx=10, pady=10)
    search_entry = ctk.CTkEntry(
        search_frame,
        textvariable=search_var,
        placeholder_text="امسح الباركود أو ابحث باسم المنتج / SKU",
        font=("Arial", 14),
        height=38,
        justify="right",
    )
    search_entry.pack(side=RIGHT, fill=X, expand=True, padx=(0, 6))
    add_button = ctk.CTkButton(search_frame, text="إضافة", width=75, height=38)
    add_button.pack(side=LEFT)

    columns = ("name", "barcode", "price", "qty", "total", "stock")
    tree = ttk.Treeview(
        center,
        columns=columns,
        show="headings",
        style="Cashier.Treeview",
        selectmode="browse",
        displaycolumns=columns[::-1],
    )
    headings = [
        ("name", "الصنف", 180),
        ("barcode", "الباركود", 100),
        ("price", "سعر الوحدة", 90),
        ("qty", "الكمية", 65),
        ("total", "الإجمالي", 95),
        ("stock", "المتاح", 65),
    ]
    for col, title, width in headings:
        tree.heading(col, text=title)
        tree.column(col, width=width, anchor=CENTER, stretch=(col == "name"))
    tree.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

    cart_actions = ctk.CTkFrame(center, fg_color="transparent")
    cart_actions.pack(fill=X, padx=10, pady=(0, 10))
    ctk.CTkButton(
        cart_actions,
        text=fix("زيادة الكمية +"),
        command=lambda: change_selected_qty(1),
        width=115,
    ).pack(side=RIGHT, padx=3)
    ctk.CTkButton(
        cart_actions,
        text=fix("تقليل الكمية −"),
        command=lambda: change_selected_qty(-1),
        width=115,
    ).pack(side=RIGHT, padx=3)
    ctk.CTkButton(
        cart_actions,
        text=fix("حذف الصنف"),
        command=lambda: remove_selected(),
        width=95,
        fg_color="#a93226",
        hover_color="#922b21",
    ).pack(side=LEFT, padx=3)
    ctk.CTkButton(
        cart_actions,
        text=fix("تفريغ السلة"),
        command=lambda: clear_cart(),
        width=95,
        fg_color="#555555",
        hover_color="#444444",
    ).pack(side=LEFT, padx=3)

    # ---------------- control panel ----------------
    ctk.CTkLabel(
        controls_body,
        text="إتمام البيع",
        font=("Arial", 20, "bold"),
        text_color=text,
    ).pack(padx=12, pady=(12, 8), anchor="e")
    ctk.CTkLabel(
        controls_body, text="العميل", text_color=text,
        anchor="e", font=("Arial", 12, "bold"),
    ).pack(fill=X, anchor="e", padx=12, pady=(3, 4))
    customer_menu = ctk.CTkComboBox(
        controls_body,
        variable=customer_var,
        values=list(customer_labels),
        state="readonly",
        height=36,
    )
    customer_menu.pack(fill=X, padx=12, pady=(0, 2))

    customer_mode_row = ctk.CTkFrame(controls_body, fg_color="transparent")
    customer_mode_row.pack(fill=X, padx=12, pady=(8, 4))
    new_customer_check = ctk.CTkCheckBox(
        customer_mode_row,
        text="تسجيل عميل جديد",
        variable=new_customer_var,
        text_color=text,
        font=("Arial", 12, "bold"),
        checkbox_width=20,
        checkbox_height=20,
    )
    new_customer_check.pack(side=RIGHT, anchor="e")

    # Keep each Arabic label directly above its matching entry in one form card.
    new_customer_frame = ctk.CTkFrame(controls_body, fg_color=bg, corner_radius=10)
    new_customer_frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        new_customer_frame, text="اسم العميل *", text_color=text,
        anchor="e", font=("Arial", 12, "bold"),
    ).pack(fill=X, padx=10, pady=(10, 2))
    new_customer_entry = ctk.CTkEntry(
        new_customer_frame,
        textvariable=new_customer_name,
        placeholder_text="اكتب اسم العميل",
        height=35,
        justify="right",
    )
    new_customer_entry.pack(fill=X, padx=10, pady=(0, 8))
    ctk.CTkLabel(
        new_customer_frame, text="رقم الهاتف (اختياري)", text_color=text,
        anchor="e", font=("Arial", 12, "bold"),
    ).pack(fill=X, padx=10, pady=(0, 2))
    new_customer_phone_entry = ctk.CTkEntry(
        new_customer_frame,
        textvariable=new_customer_phone,
        placeholder_text="اكتب رقم الهاتف",
        height=35,
        justify="right",
    )
    new_customer_phone_entry.pack(fill=X, padx=10, pady=(0, 10))

    payment_label = ctk.CTkLabel(
        controls_body, text="طريقة الدفع", text_color=text,
        anchor="e", font=("Arial", 12, "bold"),
    )
    payment_label.pack(fill=X, anchor="e", padx=12, pady=(8, 4))
    payment_menu = ctk.CTkComboBox(
        controls_body,
        variable=method_var,
        values=list(method_labels),
        state="readonly",
        height=36,
    )
    payment_menu.pack(fill=X, padx=12)

    ctk.CTkLabel(
        controls_body, text="المبلغ المدفوع", text_color=text,
        anchor="e", font=("Arial", 12, "bold"),
    ).pack(fill=X, anchor="e", padx=12, pady=(10, 4))
    paid_entry = ctk.CTkEntry(
        controls_body, textvariable=paid_var, height=36, justify=CENTER
    )
    paid_entry.pack(fill=X, padx=12)
    ctk.CTkLabel(
        controls_body,
        text="بالوحدة النقدية الرئيسية؛ المبالغ تحفظ كوحدات صغرى.",
        text_color=muted,
        font=("Arial", 10),
        wraplength=260,
    ).pack(anchor="e", padx=12, pady=(3, 8))

    ctk.CTkLabel(
        controls_body, text="إجمالي الفاتورة", text_color=muted, anchor="e"
    ).pack(fill=X, anchor="e", padx=12, pady=(8, 0))
    ctk.CTkLabel(
        controls_body,
        textvariable=total_var,
        font=("Arial", 26, "bold"),
        text_color=text,
    ).pack(anchor="e", padx=12, pady=(0, 8))

    def is_credit_customer() -> bool:
        return new_customer_var.get() or customer_labels.get(customer_var.get()) is not None

    def current_warehouse_id() -> int:
        try:
            return warehouse_labels[warehouse_var.get()]
        except KeyError:
            raise ValueError("اختر مخزنًا صحيحًا") from None

    def current_total_minor() -> int:
        total = 0
        for entry in cart.values():
            _base, _tax, line_total = _line_totals(
                entry["product"], entry["quantity"]
            )
            total += line_total
        return total

    def refresh_customer_mode(reset_payment: bool = False):
        """Switch between walk-in (full payment) and named-customer modes."""
        if new_customer_var.get():
            customer_menu.configure(state="disabled")
            new_customer_frame.pack(
                fill=X, padx=12, pady=(0, 8), before=payment_label
            )
        else:
            customer_menu.configure(state="readonly")
            new_customer_frame.pack_forget()

        if not is_credit_customer():
            # Walk-in sales must be paid in full.
            paid_var.set(minor_to_money(current_total_minor()))
        elif reset_payment or not paid_var.get().strip():
            # A named customer may buy on credit; do not carry over the
            # previous walk-in invoice amount as an accidental payment.
            paid_var.set(minor_to_money(0))

    def repaint_cart():
        tree.delete(*tree.get_children())
        for pid, entry in cart.items():
            product = entry["product"]
            qty = entry["quantity"]
            _base, _tax, line_total = _line_totals(product, qty)
            stock_text = f"{float(product[5]):g}" if product[7] else "—"
            tree.insert(
                "",
                END,
                iid=str(pid),
                values=(
                    product[1],
                    product[3],
                    minor_to_money(product[4]),
                    _qty_text(qty),
                    minor_to_money(line_total),
                    stock_text,
                ),
            )
        total = current_total_minor()
        total_var.set(minor_to_money(total))
        if not is_credit_customer():
            paid_var.set(minor_to_money(total))
        elif not paid_var.get().strip():
            paid_var.set(minor_to_money(0))

    def ask_product_quantity(product, on_confirm=None):
        """Ask for a product quantity before adding it to the cart."""
        dialog = ctk.CTkToplevel(top)
        dialog.title("تحديد الكمية")
        dialog.geometry("360x220")
        dialog.resizable(False, False)
        dialog.transient(top)
        dialog.grab_set()

        product_name = str(product[1])
        ctk.CTkLabel(
            dialog,
            text=f"المنتج: {product_name}",
            font=("Arial", 14, "bold"),
            anchor="e",
            justify="right",
            wraplength=320,
        ).pack(fill=X, padx=16, pady=(18, 8))

        ctk.CTkLabel(
            dialog,
            text="أدخل الكمية المطلوبة:",
            font=("Arial", 13),
            anchor="e",
            justify="right",
        ).pack(fill=X, padx=16, pady=(0, 5))

        quantity_var = StringVar(value="1")
        quantity_entry = ctk.CTkEntry(
            dialog,
            textvariable=quantity_var,
            justify="center",
            height=38,
        )
        quantity_entry.pack(fill=X, padx=16, pady=4)

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill=X, padx=16, pady=(12, 14))

        def confirm_quantity():
            try:
                qty = _quantity(quantity_var.get())
            except ValueError as exc:
                messagebox.showerror(
                    "كمية غير صحيحة",
                    str(exc),
                    parent=dialog,
                )
                quantity_entry.focus_set()
                return

            quantity_text = _qty_text(qty)

            dialog.grab_release()
            dialog.destroy()

            if on_confirm is not None:
                on_confirm(product, quantity_text)
            else:
                add_product_to_cart(product, quantity_text)

        ctk.CTkButton(
            buttons, text="إضافة للسلة", command=confirm_quantity
        ).pack(side=RIGHT, padx=(4, 0))
        ctk.CTkButton(
            buttons, text="إلغاء", fg_color="#555555",
            hover_color="#444444", command=dialog.destroy
        ).pack(side=LEFT, padx=(0, 4))

        quantity_entry.bind("<Return>", lambda _event: confirm_quantity())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.after(100, quantity_entry.focus_set)

    def add_product_to_cart(product, raw_qty="1"):
        try:
            qty = _quantity(raw_qty)
        except ValueError as exc:
            messagebox.showerror(
                "كمية غير صحيحة", str(exc), parent=top
            )
            return
        pid = int(product[0])
        if pid in cart:
            cart[pid]["quantity"] += qty
            # Refresh product data when an item is added from search or quick access.
            cart[pid]["product"] = product
        else:
            cart[pid] = {"product": product, "quantity": qty}
        repaint_cart()
        search_var.set("")
        search_entry.focus_set()

    def choose_product(products, raw_qty=None):
        if len(products) == 1:
            ask_product_quantity(products[0])
            return
        picker = ctk.CTkToplevel(parent)
        picker.title("اختر الصنف")
        picker.geometry("560x400")
        picker.transient(top)
        picker.grab_set()
        ctk.CTkLabel(
            picker, text=f"نتائج البحث: {len(products)}", font=("Arial", 16, "bold")
        ).pack(pady=8)
        scroller = ctk.CTkScrollableFrame(picker)
        scroller.pack(fill=BOTH, expand=True, padx=10, pady=10)
        def select_from_picker(product):
            picker.destroy()
            ask_product_quantity(product)

        for product in products:
            label = (
                f"{product[1]} | {product[3] or product[2] or '-'} | "
                f"{minor_to_money(product[4])} | مخزون {float(product[5]):g}"
            )
            ctk.CTkButton(
                scroller,
                text=label,
                anchor="e",
                command=lambda p=product: select_from_picker(p),
            ).pack(fill=X, pady=3)

    def search_and_add(event=None):
        value = search_var.get().strip()
        if not value:
            return "break"
        try:
            products = get_cashier_products(value, current_warehouse_id())
        except Exception as exc:
            messagebox.showerror("خطأ", str(exc), parent=top)
            return "break"
        if not products:
            messagebox.showwarning(
                "غير موجود",
                "لم يتم العثور على منتج نشط بهذا الاسم أو الباركود أو SKU.",
                parent=top,
            )
            return "break"
        try:
            raw_qty = qty_var.get().strip() or "1"
            _quantity(raw_qty)
        except ValueError as exc:
            messagebox.showerror("كمية غير صحيحة", str(exc), parent=top)
            return "break"
        # Prefer exact SKU/barcode matches. Partial-name matches need a picker.
        exact = [
            product
            for product in products
            if value == str(product[3] or "") or value == str(product[2] or "")
        ]
        choose_product(exact[:1] if exact else products, raw_qty)
        qty_var.set("1")
        return "break"

    def selected_product_id():
        selected = tree.selection()
        if not selected:
            selected = (tree.focus(),) if tree.focus() else ()
        if not selected:
            return None
        try:
            pid = int(selected[0])
        except (TypeError, ValueError):
            return None
        return pid if pid in cart else None

    def change_selected_qty(delta):
        pid = selected_product_id()
        if pid is None:
            return
        new_qty = cart[pid]["quantity"] + Decimal(delta)
        if new_qty <= 0:
            cart.pop(pid, None)
        else:
            cart[pid]["quantity"] = new_qty
        repaint_cart()
        if str(pid) in tree.get_children():
            tree.selection_set(str(pid))
            tree.focus(str(pid))

    def remove_selected():
        pid = selected_product_id()
        if pid is not None:
            cart.pop(pid, None)
            repaint_cart()

    def clear_cart():
        cart.clear()
        repaint_cart()

    def customer_id_from_form():
        if new_customer_var.get():
            name = new_customer_name.get().strip()
            if not name:
                raise ValueError("أدخل اسم العميل الجديد")
            return None, name, new_customer_phone.get().strip() or None
        selected = customer_var.get()
        if selected not in customer_labels:
            raise ValueError("اختر عميلًا صحيحًا")
        return customer_labels[selected], None, None

    def refresh_customers():
        nonlocal customers, customer_labels
        try:
            fresh = get_cashier_context(cashier_id)
            customers = list(fresh["customers"])
            old = customer_var.get()
            customer_labels = {WALK_IN_LABEL: None}
            for cid, cname, phone in customers:
                label = f"{cname} — {phone}" if phone else str(cname)
                if label in customer_labels:
                    label = f"{label} (#{cid})"
                customer_labels[label] = int(cid)
            customer_menu.configure(values=list(customer_labels))
            customer_var.set(old if old in customer_labels else WALK_IN_LABEL)
            refresh_customer_mode()
        except Exception as exc:
            messagebox.showerror("خطأ", str(exc), parent=top)

    def build_quick_access():
        for child in quick_scroll.winfo_children():
            child.destroy()
        try:
            groups, ungrouped = get_cashier_product_groups(current_warehouse_id())
        except Exception as exc:
            ctk.CTkLabel(
                quick_scroll,
                text=f"تعذر تحميل الأصناف: {exc}",
                text_color="#e74c3c",
                wraplength=220,
            ).pack(padx=6, pady=8)
            return

        sections = list(groups)
        if ungrouped:
            sections.append(("بدون قسم", ungrouped))
        for section_name, products in sections:
            ctk.CTkLabel(
                quick_scroll,
                text=section_name,
                text_color=text,
                font=("Arial", 14, "bold"),
                anchor="e",
            ).pack(fill=X, padx=5, pady=(10, 3))
            for product in products:

                btn_text = f"{product[1]}\n{minor_to_money(product[4])}"

                color = _valid_hex(product[11]) if len(product) > 11 else None

                ctk.CTkButton(
                    quick_scroll,
                    text=btn_text,
                    height=54,
                    anchor="e",
                    fg_color=color or "#1f3b4d",
                    hover_color=_shade(color, 0.85) if color else "#2c526a",
                    text_color=_text_on(color) if color else "#ffffff",
                    command=lambda p=product: ask_product_quantity(p),
                ).pack(fill=X, padx=4, pady=3)
        if not groups and not ungrouped:
            ctk.CTkLabel(
                quick_scroll, text="لا توجد منتجات نشطة", text_color=muted
            ).pack(pady=12)

    def refresh_shift_ui():
        try:
            row = get_open_shift(cashier_id)
        except Exception as exc:
            current_shift["row"] = None
            shift_text_var.set("تعذر تحميل حالة الوردية")
            shift_button.configure(state="disabled")
            messagebox.showerror(
                "خطأ قاعدة البيانات",
                f"تعذر تحميل حالة الوردية:\n{exc}",
                parent=top,
            )
            return False

        current_shift["row"] = row
        shift_button.configure(state="normal")
        if row:
            current_shift["last_id"] = int(row[0])
            shift_text_var.set(f"الوردية #{row[0]} مفتوحة منذ {row[2]}")
            shift_button.configure(
                text="إغلاق الوردية",
                command=ask_close_shift,
                fg_color="#a93226",
                hover_color="#922b21",
            )
        else:
            shift_text_var.set("لا توجد وردية مفتوحة")
            shift_button.configure(
                text="بدء الوردية",
                command=ask_open_shift,
                fg_color="#1f7a4d",
                hover_color="#17613d",
            )
        return True

    def confirm_sale():
        if not cart:
            messagebox.showwarning(
                "السلة فارغة", "أضف صنفًا واحدًا على الأقل.", parent=top
            )
            return

        shift_row = current_shift["row"]
        if not shift_row:
            messagebox.showwarning(
                "لا توجد وردية مفتوحة",
                "ابدأ وردية الكاشير قبل إتمام البيع.",
                parent=top,
            )
            return

        try:
            selected_customer, new_name, new_phone = customer_id_from_form()
            total_minor = current_total_minor()
            # Always parse the field. The previous implementation silently replaced
            # the entered amount with the total for walk-in customers.
            paid_minor = money_to_minor(paid_var.get() or "0")
            if paid_minor > total_minor:
                raise ValueError("المبلغ المدفوع أكبر من إجمالي الفاتورة")
            if selected_customer is None and not new_name and paid_minor != total_minor:
                raise ValueError("يجب دفع فاتورة العميل النقدي بالكامل")
            if not method_var.get() or method_var.get() not in method_labels:
                raise ValueError("اختر طريقة دفع")

            sale = create_cashier_sale(
                items=[
                    {"product_id": pid, "quantity": str(entry["quantity"])}
                    for pid, entry in cart.items()
                ],
                cashier_id=cashier_id,
                warehouse_id=current_warehouse_id(),
                payment_method_id=method_labels[method_var.get()],
                amount_paid_minor=paid_minor,
                customer_id=selected_customer,
                new_customer_name=new_name,
                new_customer_phone=new_phone,
                shift_id=int(shift_row[0]),
            )
        except Exception as exc:
            messagebox.showerror("تعذر إتمام البيع", str(exc), parent=top)
            return

        export_path = None
        export_error = None
        try:
            export_path = export_cashier_sale_to_excel(
                int(sale["sale_id"]), shift_id=int(shift_row[0])
            )
        except Exception as exc:
            # The sale is already committed. Do not report checkout as failed merely
            # because Excel/file-system export failed; show a separate warning.
            export_error = f"{type(exc).__name__}: {exc}"

        message = (
            f"تم حفظ الفاتورة {sale['number']} بنجاح\n"
            f"رقم العملية للاستخدام عند المرتجع: {sale['number']}\n"
            f"الإجمالي: {minor_to_money(sale['total'])}\n"
            f"المدفوع: {minor_to_money(sale['amount_paid'])}\n"
            f"المتبقي: {minor_to_money(sale['remaining'])}"
        )
        if export_path:
            message += f"\n\nتم تحديث سجل المبيعات في ملف Excel الموحد:\n{export_path}"
        elif export_error:
            message += f"\n\nتعذر إنشاء تقرير Excel، لكن الفاتورة محفوظة بالفعل:\n{export_error}"
        messagebox.showinfo("تم البيع", message, parent=top)
        cart.clear()
        paid_var.set(minor_to_money(0))
        new_customer_var.set(False)
        new_customer_name.set("")
        new_customer_phone.set("")
        customer_var.set(WALK_IN_LABEL)
        refresh_customer_mode()
        refresh_customers()
        repaint_cart()
        build_quick_access()
        search_entry.focus_set()

    def amount_dialog(title, prompt, callback, default="0"):
        dialog = ctk.CTkToplevel(parent)
        dialog.title(title)
        dialog.geometry("340x190")
        dialog.transient(top)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=prompt, font=("Arial", 14)).pack(
            padx=14, pady=(18, 8)
        )
        var = StringVar(value=default)
        entry = ctk.CTkEntry(dialog, textvariable=var, justify=CENTER)
        entry.pack(fill=X, padx=18, pady=6)
        entry.focus_set()

        def submit():
            try:
                amount = money_to_minor(var.get())
                callback(amount)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("خطأ", str(exc), parent=dialog)

        ctk.CTkButton(dialog, text="تأكيد", command=submit).pack(pady=12)
        entry.bind("<Return>", lambda _event: submit())

    def ask_open_shift():
        def open_it(amount):
            try:
                shift_id = open_cashier_shift(cashier_id, amount)
                current_shift["last_id"] = int(shift_id)
                refresh_shift_ui()
                messagebox.showinfo(
                    "الوردية", "بدأت الوردية بنجاح وتم تجهيز مجلد تقاريرها.", parent=top
                )
            except Exception as exc:
                # Re-read the DB in case the shift row was committed before a
                # file-system error happened while preparing its report directory.
                refresh_shift_ui()
                messagebox.showerror(
                    "تعذر بدء الوردية", f"{type(exc).__name__}: {exc}", parent=top
                )

        amount_dialog("بدء الوردية", "رصيد النقدية عند بداية الوردية", open_it)

    def ask_close_shift():
        row = current_shift["row"]
        if not row:
            refresh_shift_ui()
            return

        def close_it(amount):
            expected = close_cashier_shift(int(row[0]), amount, cashier_id)
            refresh_shift_ui()
            messagebox.showinfo(
                "إغلاق الوردية",
                f"تم إغلاق الوردية.\n"
                f"النقدية المتوقعة: {minor_to_money(expected)}\n"
                f"النقدية الفعلية: {minor_to_money(amount)}\n"
                f"الفرق: {minor_to_money(amount - expected)}",
                parent=top,
            )

        amount_dialog("إغلاق الوردية", "أدخل النقدية الفعلية في الدرج", close_it)

    def open_return_dialog():
        dialog = ctk.CTkToplevel(parent)
        dialog.title("مرتجع بيع")
        dialog.geometry("520x390")
        dialog.transient(top)
        dialog.grab_set()
        sale_ref_var = StringVar()
        item_var = StringVar()
        return_qty_var = StringVar(value="1")
        resolved = {
            "sale_id": None,
            "items": [],
            "labels": {},
            "identifier": None,
        }
        ctk.CTkLabel(
            dialog, text="رقم العملية/الفاتورة (من سجل المبيعات) أو معرف البيع", font=("Arial", 13)
        ).pack(anchor="e", padx=15, pady=(15, 3))
        ref_entry = ctk.CTkEntry(dialog, textvariable=sale_ref_var)
        ref_entry.pack(fill=X, padx=15)
        item_menu = ctk.CTkComboBox(
            dialog, variable=item_var, values=[], state="readonly"
        )
        ctk.CTkLabel(
            dialog, text="المنتج القابل للإرجاع", font=("Arial", 13)
        ).pack(anchor="e", padx=15, pady=(12, 3))
        item_menu.pack(fill=X, padx=15)
        ctk.CTkLabel(
            dialog, text="الكمية المراد إرجاعها", font=("Arial", 13)
        ).pack(anchor="e", padx=15, pady=(12, 3))
        ctk.CTkEntry(dialog, textvariable=return_qty_var).pack(fill=X, padx=15)

        def load_return_items(show_message=True):
            identifier = sale_ref_var.get().strip()
            if not identifier:
                messagebox.showerror(
                    "تعذر تحميل الفاتورة", "أدخل رقم الفاتورة أو معرفها.", parent=dialog
                )
                return False
            try:
                sale_id, sale_number, rows = get_returnable_sales_items(identifier)
                if not rows:
                    raise ValueError(
                        "لا توجد كميات متبقية قابلة للإرجاع لهذه الفاتورة"
                    )
                labels = {}
                for row in rows:
                    pid, name, remaining, _price, _cost = row
                    label = f"{name} — متبقي {remaining:g} (ID {pid})"
                    labels[label] = row
                resolved["sale_id"] = int(sale_id)
                resolved["items"] = rows
                resolved["labels"] = labels
                resolved["identifier"] = identifier
                item_menu.configure(values=list(labels))
                item_var.set(next(iter(labels)))
                if show_message:
                    messagebox.showinfo(
                        "الفاتورة",
                        f"الفاتورة {sale_number} جاهزة للمرتجع.",
                        parent=dialog,
                    )
                return True
            except Exception as exc:
                resolved.update(
                    {"sale_id": None, "items": [], "labels": {}, "identifier": None}
                )
                item_menu.configure(values=[])
                item_var.set("")
                messagebox.showerror(
                    "تعذر تحميل الفاتورة", str(exc), parent=dialog
                )
                return False

        def submit_return():
            try:
                identifier = sale_ref_var.get().strip()
                if (
                    resolved["sale_id"] is None
                    or resolved["identifier"] != identifier
                ):
                    if not load_return_items(show_message=False):
                        return
                row = resolved["labels"].get(item_var.get())
                if not row:
                    raise ValueError("اختر منتجًا صالحًا")
                qty = _quantity(return_qty_var.get())
                if qty > Decimal(str(row[2])):
                    raise ValueError(f"الكمية المتبقية هي {row[2]:g} فقط")
                shift = current_shift["row"]
                if not shift:
                    raise ValueError("ابدأ وردية الكاشير قبل تسجيل المرتجع")
                return_id = create_cashier_return(
                    int(resolved["sale_id"]),
                    int(row[0]),
                    float(qty),
                    cashier_id,
                    int(shift[0]),
                    "مرتجع من صفحة الكاشير",
                )
                dialog.destroy()
                build_quick_access()
                messagebox.showinfo(
                    "تم المرتجع",
                    f"تم إنشاء المرتجع بنجاح. معرف المرتجع: {return_id}",
                    parent=top,
                )
            except Exception as exc:
                messagebox.showerror("تعذر تنفيذ المرتجع", str(exc), parent=dialog)

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill=X, padx=15, pady=18)
        ctk.CTkButton(
            buttons, text="تحميل الفاتورة", command=load_return_items
        ).pack(side=RIGHT, padx=4)
        ctk.CTkButton(
            buttons,
            text="تسجيل المرتجع",
            command=submit_return,
            fg_color="#a93226",
            hover_color="#922b21",
        ).pack(side=LEFT, padx=4)

    def open_session_reports():
        shift_id = current_shift.get("row")
        shift_id = int(shift_id[0]) if shift_id else current_shift.get("last_id")
        if not shift_id:
            messagebox.showinfo(
                "تقارير الوردية", "ابدأ وردية أولًا لإنشاء مجلد التقارير.", parent=top
            )
            return
        try:
            folder = get_cashier_session_folder(int(shift_id), create=True)
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            messagebox.showerror(
                "تعذر فتح مجلد التقارير",
                f"تعذر فتح المجلد الخاص بالوردية:\n{type(exc).__name__}: {exc}",
                parent=top,
            )

    def on_warehouse_change(_value=None):
        try:
            fresh_products = {
                int(product[0]): product
                for product in get_cashier_products("", current_warehouse_id())
            }
            for pid, entry in cart.items():
                if pid in fresh_products:
                    entry["product"] = fresh_products[pid]
            build_quick_access()
            repaint_cart()
        except Exception as exc:
            messagebox.showerror("خطأ", str(exc), parent=top)

    # Bind callbacks after helper declarations.
    add_button.configure(command=search_and_add)
    search_entry.bind("<Return>", search_and_add)
    tree.bind("<Delete>", lambda _event: remove_selected())
    tree.bind("<Double-1>", lambda _event: change_selected_qty(1))
    warehouse_menu.configure(command=on_warehouse_change)
    new_customer_check.configure(
        command=lambda: refresh_customer_mode(reset_payment=True)
    )
    customer_menu.configure(
        command=lambda _value: refresh_customer_mode(reset_payment=True)
    )

    ctk.CTkButton(
        controls_body,
        text="تأكيد البيع",
        command=confirm_sale,
        height=44,
        font=("Arial", 17, "bold"),
        fg_color="#1f7a4d",
        hover_color="#17613d",
    ).pack(fill=X, padx=12, pady=(10, 6))
    ctk.CTkButton(
        controls_body,
        text=fix("مرتجع بيع"),
        command=open_return_dialog,
        height=38,
        fg_color="#a93226",
        hover_color="#922b21",
    ).pack(fill=X, padx=12, pady=5)
    ctk.CTkButton(
        controls_body,
        text=fix("تحديث الأصناف والعملاء"),
        command=lambda: (build_quick_access(), refresh_customers()),
        height=36,
        fg_color="#555555",
        hover_color="#444444",
    ).pack(fill=X, padx=12, pady=5)
    ctk.CTkButton(
        controls_body,
        text=fix("فتح مجلد تقارير الوردية"),
        command=open_session_reports,
        height=36,
        fg_color="#285c8f",
        hover_color="#1f496f",
    ).pack(fill=X, padx=12, pady=5)
    ctk.CTkLabel(
        controls_body,
        text=fix("اختصارات: Enter لإضافة البحث، Delete لحذف الصنف، والنقر المزدوج لزيادة الكمية."),
        text_color=muted,
        font=("Arial", 10),
        wraplength=265,
        justify=RIGHT,
    ).pack(fill=X, padx=12, pady=(10, 8))

    build_quick_access()
    refresh_shift_ui()
    refresh_customer_mode()
    repaint_cart()
    return True
