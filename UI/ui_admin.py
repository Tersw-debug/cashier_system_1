"""Refactored Arabic admin dashboard for the MyShop schema (migrations 1-6).

The dashboard uses the current Database.Schema.db service API and no longer
imports legacy inventory/customer SQL or image assets.
"""
from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from Services import admin_service as svc
from UI.router import go_login


username = ""
_root = None
_dashboard_refresh = None


def getUsername(username_from_login: str):
    global username
    username = username_from_login or ""


def _appearance_colors():
    dark = ctk.get_appearance_mode() == "Dark"
    return {
        "bg": "#121212" if dark else "#f4f6f8",
        "card": "#1e1e1e" if dark else "#ffffff",
        "text": "#ffffff" if dark else "#18212b",
        "subtext": "#b8c0cc" if dark else "#5b6572",
        "accent": "#1f6aa5",
        "accent_hover": "#185785",
        "success": "#218c62",
        "danger": "#c0392b",
        "border": "#333943" if dark else "#dce2e8",
    }


def _style_treeview():
    colors = _appearance_colors()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Admin.Treeview", background=colors["card"], foreground=colors["text"],
                    fieldbackground=colors["card"], rowheight=29, borderwidth=0,
                    font=("Segoe UI", 10))
    style.configure("Admin.Treeview.Heading", background=colors["bg"], foreground=colors["text"],
                    font=("Segoe UI", 10, "bold"), relief="flat")
    style.map("Admin.Treeview", background=[("selected", colors["accent"])],
              foreground=[("selected", "#ffffff")])


# Each group exposes actual schema tables/views; transactional records are
# read-only in the generic browser and changed through explicit workflows.
ADMIN_GROUPS = [
    ("الملخص", [
        ("المنتجات", "products"), ("الأقسام", "sections"), ("وحدات القياس", "units"),
        ("باركود المنتجات", "product_barcodes"), ("الضرائب", "tax_rates"),
    ]),
    ("المخزون", [
        ("أرصدة المخزون", "stock_levels"), ("الأصناف منخفضة المخزون", "low_stock_products"),
        ("حركة المخزون", "stock_movements"), ("تقييم تقريبي للمخزون", "stock_valuation"),
        ("المخازن", "warehouses"), ("التحويلات", "stock_transfers"), ("بنود التحويلات", "stock_transfer_items"),
    ]),
    ("المبيعات والمشتريات", [
        ("العملاء والموردون", "partners"), ("أرصدة العملاء", "customer_balances"),
        ("أرصدة الموردين", "supplier_balances"), ("المبيعات", "sales"), ("بنود البيع", "sale_items"),
        ("أوامر الشراء", "purchase_orders"), ("بنود أوامر الشراء", "purchase_order_items"),
        ("فواتير الشراء", "purchase_invoices"), ("بنود فواتير الشراء", "purchase_invoice_items"),
    ]),
    ("الخزينة والمدفوعات", [
        ("طرق الدفع", "payment_methods"), ("ورديات الخزينة", "cash_shifts"),
        ("المدفوعات", "payments"), ("توزيع المدفوعات", "payment_allocations"),
    ]),
    ("المحاسبة", [
        ("دليل الحسابات", "accounts"), ("قيود اليومية", "journal_entries"),
        ("بنود اليومية", "journal_lines"), ("القيود غير المتوازنة", "unbalanced_entries"),
        ("المصروفات", "expenses"),
    ]),
    ("الموارد البشرية", [
        ("الأقسام الوظيفية", "departments"), ("الموظفون", "employees"),
        ("الحضور والانصراف", "attendance"), ("تسويات الموظفين", "employee_adjustments"),
        ("مسيرات الرواتب", "payroll_runs"), ("قسائم الرواتب", "payslips"),
    ]),
    ("الأمان والإعدادات", [
        ("المستخدمون", "users"), ("الأدوار", "roles"), ("الصلاحيات", "permissions"),
        ("صلاحيات الأدوار", "role_permissions"), ("سجل التدقيق", "audit_log"),
        ("الإعدادات", "settings"), ("ترقيم المستندات", "doc_sequences"),
    ]),
]

_ENUM_CHOICES = {
    "kind": ["CASH", "CARD", "TRANSFER", "WALLET", "OTHER"],
    "type": ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"],
    "salary_type": ["MONTHLY", "DAILY", "HOURLY"],
    "status": ["PRESENT", "ABSENT", "LATE", "LEAVE", "HOLIDAY"],
    "movement_type": ["OPENING", "ADJUSTMENT", "DAMAGE"],
    "kind_adjustment": ["ALLOWANCE", "BONUS", "DEDUCTION", "ADVANCE"],
}


def _parse_record_id(resource: str, value):
    if resource in {"settings", "doc_sequences"}:
        return str(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _field_default(field):
    default = field.get("default", "")
    return date.today().isoformat() if default == "today" else default


def _make_choice_widget(parent, field, current):
    """Returns (widget, display->database value map)."""
    name = field["name"]
    values = []
    display_to_value = {}
    supplied_choices = field.get("choice_values")
    if supplied_choices:
        # A choice may be an enum string or a (database_value, display_label) pair.
        # Preserve IDs as the submitted value while displaying human-readable labels.
        if all(isinstance(item, (tuple, list)) and len(item) == 2 for item in supplied_choices):
            choices = [(item[0], item[1]) for item in supplied_choices]
        else:
            choices = [(item, item) for item in supplied_choices]
    else:
        choices = svc.get_field_choices(name)
    if choices:
        values.append("")
        display_to_value[""] = ""
        for value, label in choices:
            display = f"{value} — {label}"
            values.append(display)
            display_to_value[display] = value
        current_display = ""
        if current not in (None, ""):
            for display, raw in display_to_value.items():
                if str(raw) == str(current):
                    current_display = display
                    break
        widget = ctk.CTkComboBox(parent, values=values, height=34, state="readonly")
        widget.set(current_display)
        return widget, display_to_value

    if name in _ENUM_CHOICES:
        enum_values = _ENUM_CHOICES[name]
        widget = ctk.CTkComboBox(parent, values=enum_values, height=34, state="readonly")
        widget.set(str(current if current not in (None, "") else field.get("default", enum_values[0])))
        return widget, {v: v for v in enum_values}

    widget = ctk.CTkEntry(parent, height=34, show="*" if field.get("secret") else "")
    if current not in (None, ""):
        widget.insert(0, str(current))
    elif _field_default(field) not in (None, ""):
        widget.insert(0, str(_field_default(field)))
    return widget, display_to_value


def _widget_value(widget, display_to_value):
    value = widget.get().strip()
    if display_to_value:
        return display_to_value.get(value, value)
    return value


def _prompt_form(title: str, fields: list[dict], on_submit, record: dict | None = None,
                 parent=None, note: str | None = None):
    parent = parent or _root
    colors = _appearance_colors()
    win = ctk.CTkToplevel(parent)
    win.title(title)
    win.geometry("650x760")
    win.minsize(520, 420)
    win.configure(fg_color=colors["bg"])
    win.transient(parent)
    win.grab_set()

    ctk.CTkLabel(win, text=title, font=("Segoe UI", 22, "bold"), text_color=colors["text"]).pack(padx=18, pady=(16, 8))
    if note:
        ctk.CTkLabel(win, text=note, font=("Segoe UI", 12), text_color=colors["subtext"], wraplength=590, justify="left").pack(fill="x", padx=18, pady=(0, 10))
    body = ctk.CTkScrollableFrame(win, fg_color=colors["card"], corner_radius=12)
    body.pack(fill="both", expand=True, padx=18, pady=8)
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=2)
    widgets = {}
    option_maps = {}
    for row_no, field in enumerate(fields):
        ctk.CTkLabel(body, text=field["label"], anchor="e", text_color=colors["text"], font=("Segoe UI", 12)).grid(row=row_no, column=1, sticky="ew", padx=10, pady=7)
        current = (record or {}).get(field["name"], _field_default(field))
        widget, display_map = _make_choice_widget(body, field, current)
        widget.grid(row=row_no, column=0, sticky="ew", padx=10, pady=7)
        widgets[field["name"]] = widget
        option_maps[field["name"]] = display_map

    footer = ctk.CTkFrame(win, fg_color="transparent")
    footer.pack(fill="x", padx=18, pady=(6, 16))

    def submit():
        values = {name: _widget_value(widget, option_maps[name]) for name, widget in widgets.items()}
        try:
            result = on_submit(values)
        except Exception as exc:
            messagebox.showerror("تعذر الحفظ", str(exc), parent=win)
            return
        if result is False:
            return
        win.destroy()

    ctk.CTkButton(footer, text="حفظ", command=submit, fg_color=colors["success"], height=38).pack(side="right", padx=6)
    ctk.CTkButton(footer, text="إلغاء", command=win.destroy, fg_color="#6b7280", height=38).pack(side="right", padx=6)
    return win


def _refresh_dashboard():
    if _dashboard_refresh:
        try:
            _dashboard_refresh()
        except Exception:
            pass


def _notify_action(success_message: str, action, refresh_resource=None, refresh_callback=None):
    try:
        action()
    except Exception as exc:
        messagebox.showerror("خطأ", str(exc), parent=_root)
        return False
    messagebox.showinfo("تم", success_message, parent=_root)
    _refresh_dashboard()
    if refresh_callback:
        refresh_callback()
    return True


def _open_entity_editor(resource: str, record_id=None, refresh_callback=None):
    fields = svc.FIELD_DEFS[resource]
    record = None
    if record_id is not None:
        record = svc.get_resource_record(resource, record_id)
        if not record:
            messagebox.showerror("خطأ", "لم يتم العثور على السجل", parent=_root)
            return
    title = ("إضافة " if record_id is None else "تعديل ") + svc.RESOURCE_CONFIG[resource]["title"]
    note = None
    if resource == "products":
        note = "الكميات لا تُعدّل من بطاقة المنتج؛ استخدم تسوية المخزون أو التحويل حتى يظل دفتر حركة المخزون هو المصدر الصحيح. الأسعار والمبالغ تُخزن بوحدة العملة الصغرى وفق المخطط."
    elif resource == "users":
        note = "لا يتم عرض كلمة المرور المحفوظة. صيغة كلمات المرور الجديدة هنا PBKDF2-SHA256؛ تأكد أن خدمة تسجيل الدخول تستخدم verify_admin_password من Services.admin_service."
    elif resource == "warehouses":
        note = "يمكن تعيين مخزن افتراضي واحد فقط. لا يمكن تعطيل المخزن الافتراضي قبل تعيين بديل."
    elif resource == "settings":
        note = "تغيير المفاتيح المستخدمة في الحسابات يؤثر على ترحيل القيود. لا تغيّرها إلا إذا كنت تعرف أثرها."

    def save(values):
        svc.save_entity(resource, values, record_id=record_id, user_id=svc.get_username_id(username))
        if refresh_callback:
            refresh_callback()
        _refresh_dashboard()
        messagebox.showinfo("تم", "تم حفظ البيانات بنجاح", parent=_root)

    # For settings, key edits create a new setting because keys are the primary key.
    _prompt_form(title, fields, save, record=record, note=note)


def _selected_row(tree):
    selected = tree.selection()
    if not selected:
        return None
    item = tree.item(selected[0])
    vals = item.get("values", [])
    return vals if vals else None


def _open_stock_adjustment(refresh):
    fields = [
        {"name":"product_id","label":"المنتج ID","type":"int","required":True},
        {"name":"warehouse_id","label":"المخزن ID","type":"int","required":True},
        {"name":"movement_type","label":"نوع الحركة","required":True,"choice_values":_ENUM_CHOICES["movement_type"]},
        {"name":"quantity_change","label":"تغير الكمية (+ إضافة / - سحب)","type":"float","required":True},
        {"name":"unit_cost","label":"التكلفة بوحدة العملة الصغرى (اختياري)","type":"int?"},
        {"name":"note","label":"ملاحظة"},
    ]
    # Mark choice fields with schema-linked choice sources.
    fields[0]["choice_values"] = None
    fields[0]["name"] = "product_id"
    fields[1]["name"] = "warehouse_id"
    def submit(v):
        product_id = int(v["product_id"])
        warehouse_id = int(v["warehouse_id"])
        qty = float(v["quantity_change"])
        unit_cost = int(v["unit_cost"]) if str(v.get("unit_cost", "")).strip() else None
        movement = str(v["movement_type"])
        user_id = svc.get_username_id(username)
        svc.add_stock_adjustment(product_id, warehouse_id, qty, movement, unit_cost, user_id, v.get("note", ""))
        refresh()
        _refresh_dashboard()
        messagebox.showinfo("تم", "تم تسجيل حركة المخزون بنجاح", parent=_root)
    _prompt_form("تسوية المخزون", fields, submit, note="لا تغيّر الكمية مباشرة في جدول المنتجات. ستُضاف حركة جديدة إلى دفتر المخزون.")


def _open_transfer(refresh):
    fields = [
        {"name":"from_warehouse_id","label":"من المخزن ID","type":"int","required":True,"choices_key":"warehouse_id"},
        {"name":"to_warehouse_id","label":"إلى المخزن ID","type":"int","required":True,"choices_key":"warehouse_id"},
        {"name":"product_id","label":"المنتج ID","type":"int","required":True,"choices_key":"product_id"},
        {"name":"quantity","label":"الكمية","type":"float","required":True},
        {"name":"note","label":"ملاحظة"},
    ]
    # _make_choice_widget looks up choices based on field name; linked keys are aliased here.
    fields[0]["name"] = "from_warehouse_id"; fields[0]["choice_values"] = [(x[0], x[1]) for x in svc.get_field_choices("warehouse_id")]
    fields[1]["name"] = "to_warehouse_id"; fields[1]["choice_values"] = [(x[0], x[1]) for x in svc.get_field_choices("warehouse_id")]
    fields[2]["choice_values"] = [(x[0], x[1]) for x in svc.get_field_choices("product_id")]
    def submit(v):
        transfer_id = svc.create_stock_transfer(int(v["from_warehouse_id"]), int(v["to_warehouse_id"]),
                                                [{"product_id": int(v["product_id"]), "quantity": float(v["quantity"])}],
                                                svc.get_username_id(username), v.get("note", ""))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم تسجيل التحويل وإضافة حركتي الصرف والإضافة. رقم السجل: {transfer_id}", parent=_root)
    _prompt_form("تحويل بين المخازن", fields, submit, note="يتم تسجيل التحويل وحركتي المخزون داخل معاملة واحدة. هذه الشاشة تنفذ تحويلًا لصنف واحد في كل مرة.")


def _open_sale_form(refresh):
    fields = [
        {"name":"customer_id","label":"العميل ID (فارغ للبيع النقدي)","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("customer_id")]},
        {"name":"warehouse_id","label":"المخزن ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("warehouse_id")]},
        {"name":"product_id","label":"المنتج ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("product_id")]},
        {"name":"quantity","label":"الكمية","type":"float","required":True},
        {"name":"unit_price","label":"سعر الوحدة بوحدة العملة الصغرى","type":"int","required":True},
        {"name":"discount","label":"خصم البند بوحدة العملة الصغرى","type":"int","default":"0"},
        {"name":"tax_rate_bp","label":"نسبة الضريبة بالنقاط الأساسية (اتركها فارغة لاستخدام ضريبة المنتج)","type":"int?"},
        {"name":"shift_id","label":"الوردية المفتوحة ID (اختياري)","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("shift_id")]},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        current_user_id = svc.get_username_id(username)
        if current_user_id is None:
            raise ValueError("لا يمكن تحديد المستخدم الحالي من اسم الدخول")
        sale_id = svc.create_sale(int(v["customer_id"]) if v.get("customer_id") else None,
                                  int(v["warehouse_id"]), int(v["product_id"]), float(v["quantity"]),
                                  int(v["unit_price"]), int(v.get("discount") or 0), int(v["tax_rate_bp"]) if v.get("tax_rate_bp") else None,
                                  current_user_id, int(v["shift_id"]) if v.get("shift_id") else None,
                                  note=v.get("note", ""), post=True)
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم تسجيل البيع وترحيل القيد. معرف البيع: {sale_id}", parent=_root)
    _prompt_form("تسجيل عملية بيع", fields, submit,
                 note="هذه النسخة تسجل بندًا واحدًا. البيع بعميل مسجل يُرحّل إلى حساب العملاء، والبيع النقدي بدون عميل يُرحّل إلى حساب النقدية. المبالغ بوحدة العملة الصغرى.")


def _open_purchase_order_form(refresh):
    fields = [
        {"name":"supplier_id","label":"المورد ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("supplier_id")]},
        {"name":"product_id","label":"المنتج ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("product_id")]},
        {"name":"quantity","label":"الكمية","type":"float","required":True},
        {"name":"unit_cost","label":"تكلفة الوحدة بوحدة العملة الصغرى","type":"int","required":True},
        {"name":"expected_date","label":"تاريخ التوقع YYYY-MM-DD"},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        order_id = svc.create_purchase_order(int(v["supplier_id"]), int(v["product_id"]), float(v["quantity"]), int(v["unit_cost"]), svc.get_username_id(username), v.get("expected_date") or None, v.get("note", ""))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم إنشاء أمر الشراء كمسودة. المعرف: {order_id}", parent=_root)
    _prompt_form("إنشاء أمر شراء", fields, submit, note="أمر الشراء لا يزيد المخزون؛ يتم الاستلام عبر فاتورة الشراء المرحلة.")


def _open_sale_return_form(refresh):
    fields = [
        {"name":"original_sale_id","label":"فاتورة البيع الأصلية ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("original_sale_id")]},
        {"name":"product_id","label":"المنتج ID الموجود بالفاتورة","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("product_id")]},
        {"name":"quantity","label":"كمية المرتجع","type":"float","required":True},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        current_user_id = svc.get_username_id(username)
        if current_user_id is None:
            raise ValueError("لا يمكن تحديد المستخدم الحالي من اسم الدخول")
        return_id = svc.create_sale_return(int(v["original_sale_id"]), int(v["product_id"]), float(v["quantity"]), current_user_id, note=v.get("note", ""))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم ترحيل مرتجع البيع. المعرف: {return_id}", parent=_root)
    _prompt_form("مرتجع بيع", fields, submit, note="اختر فاتورة بيع مرحلة والمنتج المرتبط بها. يمنع النظام إرجاع كمية تتجاوز الكمية المباعة بعد المرتجعات السابقة.")


def _open_purchase_invoice_form(refresh):
    fields = [
        {"name":"supplier_id","label":"المورد ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("supplier_id")]},
        {"name":"warehouse_id","label":"المخزن ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("warehouse_id")]},
        {"name":"product_id","label":"المنتج ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("product_id")]},
        {"name":"quantity","label":"الكمية","type":"float","required":True},
        {"name":"unit_cost","label":"تكلفة الوحدة بوحدة العملة الصغرى","type":"int","required":True},
        {"name":"tax_rate_bp","label":"نسبة الضريبة بالنقاط الأساسية (اتركها فارغة لاستخدام ضريبة المنتج)","type":"int?"},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        if int(v.get("tax_rate_bp") or 0) > 0:
            ok = messagebox.askyesno("تنبيه محاسبي", "دليل الحسابات الحالي لا يحتوي على حساب ضريبة مدخلات قابلة للاسترداد. ستُضاف الضريبة إلى تكلفة المخزون في القيد. هل تريد المتابعة؟", parent=_root)
            if not ok:
                return False
        invoice_id = svc.create_purchase_invoice(int(v["supplier_id"]), int(v["warehouse_id"]), int(v["product_id"]), float(v["quantity"]), int(v["unit_cost"]), int(v["tax_rate_bp"]) if v.get("tax_rate_bp") else None, svc.get_username_id(username), v.get("note", ""), post=True)
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم ترحيل فاتورة الشراء وزيادة المخزون. المعرف: {invoice_id}", parent=_root)
    _prompt_form("تسجيل فاتورة شراء", fields, submit, note="النسخة الحالية تدعم بندًا واحدًا فقط لكل عملية. ترحيل الفاتورة يزيد المخزون ويُنشئ قيدًا متوازنًا. إذا كانت ضريبة المدخلات قابلة للاسترداد، أضف حساب ضريبة مدخلات قبل استخدام هذا المسار.")


def _open_purchase_return_form(refresh):
    fields = [
        {"name":"original_invoice_id","label":"فاتورة الشراء الأصلية ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("original_invoice_id")]},
        {"name":"product_id","label":"المنتج ID الموجود بالفاتورة","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("product_id")]},
        {"name":"quantity","label":"كمية المرتجع","type":"float","required":True},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        return_id = svc.create_purchase_return(int(v["original_invoice_id"]), int(v["product_id"]), float(v["quantity"]), svc.get_username_id(username), v.get("note", ""))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم ترحيل مرتجع الشراء. المعرف: {return_id}", parent=_root)
    _prompt_form("مرتجع شراء", fields, submit, note="يتحقق النظام من الكمية التي تم شراؤها سابقًا، ويخفض المخزون وينشئ قيدًا متوازنًا. ضريبة الشراء تُعامل ضمن تكلفة المخزون وفق مخطط الحسابات الحالي.")


def _open_payment_form(refresh):
    fields = [
        {"name":"direction","label":"الاتجاه","required":True,"choice_values":[("IN","تحصيل من عميل"),("OUT","سداد لمورد")]},
        {"name":"partner_id","label":"الشريك ID","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("partner_id")]},
        {"name":"method_id","label":"طريقة الدفع ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("method_id")]},
        {"name":"amount","label":"المبلغ بوحدة العملة الصغرى","type":"int","required":True},
        {"name":"shift_id","label":"الوردية المفتوحة ID (اختياري)","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("shift_id")]},
        {"name":"document_type","label":"نوع المستند المراد التوزيع عليه (اختياري)","choice_values":[("SALE","SALE"),("PURCHASE_INVOICE","PURCHASE_INVOICE")]},
        {"name":"document_id","label":"معرف المستند (اتركه فارغًا للدفع غير الموزع)","type":"int?"},
        {"name":"allocated_amount","label":"المبلغ الموزع (اختياري)","type":"int?"},
        {"name":"reference","label":"مرجع التحويل/الإيصال"},
        {"name":"note","label":"ملاحظة"},
    ]
    def submit(v):
        allocations = []
        if v.get("document_id"):
            if not v.get("allocated_amount"):
                raise ValueError("أدخل مبلغ التوزيع عند تحديد مستند")
            allocations.append({"document_type":v["document_type"], "document_id":int(v["document_id"]), "amount":int(v["allocated_amount"])})
        elif v.get("allocated_amount"):
            raise ValueError("أدخل معرف المستند أو اترك مبلغ التوزيع فارغًا")
        payment_id = svc.record_payment(v["direction"], int(v["partner_id"]) if v.get("partner_id") else None, int(v["method_id"]), int(v["amount"]), svc.get_username_id(username), allocations, int(v["shift_id"]) if v.get("shift_id") else None, v.get("reference", ""), v.get("note", ""))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم تسجيل الدفع وإنشاء القيد المحاسبي. المعرف: {payment_id}", parent=_root)
    _prompt_form("تسجيل دفعة أو تحصيل", fields, submit, note="يمكن توزيع الدفع على مستند واحد في هذه الشاشة. أي مبلغ غير موزع يظل رصيدًا على حساب الشريك وفق منطق أرصدة النظام.")


def _open_expense_form(refresh):
    fields = [
        {"name":"expense_date","label":"تاريخ المصروف YYYY-MM-DD","required":True,"default":date.today().isoformat()},
        {"name":"account_id","label":"حساب المصروف ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("account_id")]},
        {"name":"method_id","label":"طريقة الدفع ID","type":"int","required":True,"choice_values":[(x[0],x[1]) for x in svc.get_field_choices("method_id")]},
        {"name":"amount","label":"المبلغ بوحدة العملة الصغرى","type":"int","required":True},
        {"name":"partner_id","label":"الشريك ID (اختياري)","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("partner_id")]},
        {"name":"shift_id","label":"الوردية المفتوحة ID (اختياري)","type":"int?","choice_values":[(x[0],x[1]) for x in svc.get_field_choices("shift_id")]},
        {"name":"description","label":"الوصف"},
    ]
    def submit(v):
        expense_id = svc.record_expense(v["expense_date"], int(v["account_id"]), int(v["method_id"]), int(v["amount"]), svc.get_username_id(username), v.get("description", ""), int(v["partner_id"]) if v.get("partner_id") else None, int(v["shift_id"]) if v.get("shift_id") else None)
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم تسجيل المصروف وإنشاء القيد. المعرف: {expense_id}", parent=_root)
    _prompt_form("تسجيل مصروف", fields, submit, note="اختر حسابًا من نوع EXPENSE وطريقة دفع مرتبطة بحساب أستاذ.")


def _open_journal_form(refresh):
    accounts = [(x[0], x[1]) for x in svc.get_field_choices("account_id")]
    fields = [
        {"name":"entry_date","label":"تاريخ القيد YYYY-MM-DD","required":True,"default":date.today().isoformat()},
        {"name":"description","label":"وصف القيد","required":True},
        {"name":"debit_account","label":"الحساب المدين ID","type":"int","required":True,"choice_values":accounts},
        {"name":"credit_account","label":"الحساب الدائن ID","type":"int","required":True,"choice_values":accounts},
        {"name":"amount","label":"المبلغ بوحدة العملة الصغرى","type":"int","required":True},
    ]
    def submit(v):
        if int(v["debit_account"]) == int(v["credit_account"]):
            raise ValueError("اختر حسابين مختلفين")
        amount = int(v["amount"])
        if amount <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
        entry_id = svc.create_manual_journal(v["entry_date"], v["description"], [
            {"account_id":int(v["debit_account"]),"debit":amount,"credit":0,"description":v["description"]},
            {"account_id":int(v["credit_account"]),"debit":0,"credit":amount,"description":v["description"]},
        ], svc.get_username_id(username))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم إنشاء القيد المتوازن وترحيله. المعرف: {entry_id}", parent=_root)
    _prompt_form("إنشاء قيد يومية متوازن", fields, submit, note="هذا النموذج ينشئ قيدًا من سطر مدين وسطر دائن بالقيمة نفسها. القيود المرحلة غير قابلة للتعديل أو الحذف.")


def _open_payroll_form(refresh):
    fields = [
        {"name":"period_start","label":"بداية الفترة YYYY-MM-DD","required":True,"default":date.today().replace(day=1).isoformat()},
        {"name":"period_end","label":"نهاية الفترة YYYY-MM-DD","required":True,"default":date.today().isoformat()},
    ]
    def submit(v):
        run_id = svc.create_payroll_draft(v["period_start"], v["period_end"], svc.get_username_id(username))
        refresh(); _refresh_dashboard()
        messagebox.showinfo("تم", f"تم إنشاء مسودة رواتب تشمل الموظفين النشطين. المعرف: {run_id}", parent=_root)
    _prompt_form("إنشاء مسودة مسير رواتب", fields, submit, note="تنشأ قسائم أولية على أساس الأجر الأساسي فقط. لم يتم تفعيل ترحيل الرواتب أو الدفع آليًا لأن ذلك يتطلب سياسة خصومات/حضور وحسابات مقابلة محددة.")


def _open_role_permissions():
    colors = _appearance_colors()
    roles = svc.get_field_choices("role_id")
    if not roles:
        messagebox.showerror("خطأ", "لا توجد أدوار", parent=_root); return
    win = ctk.CTkToplevel(_root)
    win.title("إدارة صلاحيات الأدوار")
    win.geometry("600x720")
    win.transient(_root); win.grab_set(); win.configure(fg_color=colors["bg"])
    ctk.CTkLabel(win, text="إدارة صلاحيات الدور", font=("Segoe UI", 22, "bold"), text_color=colors["text"]).pack(pady=12)
    options = [f"{rid} — {name}" for rid, name in roles]
    role_combo = ctk.CTkComboBox(win, values=options, width=450, state="readonly")
    role_combo.pack(pady=8)
    check_area = ctk.CTkScrollableFrame(win, fg_color=colors["card"])
    check_area.pack(fill="both", expand=True, padx=18, pady=12)
    state = {"vars": [], "permission_ids": [], "role_id": None}
    def load_role(_=None):
        for child in check_area.winfo_children(): child.destroy()
        state["vars"].clear(); state["permission_ids"].clear()
        selected = role_combo.get()
        try: role_id = int(selected.split(" — ",1)[0])
        except (ValueError, IndexError): return
        all_permissions, assigned, role = svc.get_role_permissions(role_id)
        state["role_id"] = role_id
        for perm_id, code, description in all_permissions:
            var = tk.BooleanVar(value=perm_id in assigned)
            box = ctk.CTkCheckBox(check_area, text=f"{code} — {description}", variable=var)
            box.pack(fill="x", padx=8, pady=5, anchor="w")
            state["vars"].append(var); state["permission_ids"].append(perm_id)
    role_combo.configure(command=load_role)
    role_combo.set(options[0]); load_role()
    def save():
        if state["role_id"] is None: return
        selected = [pid for pid, var in zip(state["permission_ids"], state["vars"]) if var.get()]
        try: svc.set_role_permissions(state["role_id"], selected, svc.get_username_id(username))
        except Exception as exc:
            messagebox.showerror("خطأ", str(exc), parent=win); return
        messagebox.showinfo("تم", "تم تحديث صلاحيات الدور", parent=win); win.destroy()
    ctk.CTkButton(win, text="حفظ الصلاحيات", command=save, fg_color=colors["success"]).pack(pady=(0,16))


def _resource_action_buttons(resource, toolbar, refresh, tree):
    colors = _appearance_colors()
    def add_action(label, func):
        ctk.CTkButton(toolbar, text=label, command=func, height=34, fg_color=colors["accent"], hover_color=colors["accent_hover"]).pack(side="right", padx=4, pady=4)
    if resource == "stock_levels":
        add_action("تسوية مخزون", lambda: _open_stock_adjustment(refresh))
        add_action("تحويل بين المخازن", lambda: _open_transfer(refresh))
    elif resource == "stock_transfers":
        add_action("تحويل جديد", lambda: _open_transfer(refresh))
    elif resource == "sales":
        add_action("تسجيل بيع", lambda: _open_sale_form(refresh))
        add_action("مرتجع بيع", lambda: _open_sale_return_form(refresh))
    elif resource == "purchase_orders":
        add_action("أمر شراء جديد", lambda: _open_purchase_order_form(refresh))
    elif resource == "purchase_invoices":
        add_action("فاتورة شراء", lambda: _open_purchase_invoice_form(refresh))
        add_action("مرتجع شراء", lambda: _open_purchase_return_form(refresh))
    elif resource == "payments":
        add_action("تسجيل دفعة", lambda: _open_payment_form(refresh))
    elif resource == "cash_shifts":
        def open_shift():
            fields = [{"name":"opening_cash","label":"رصيد بداية الوردية بوحدة العملة الصغرى","type":"int","default":"0","required":True},{"name":"note","label":"ملاحظة"}]
            def submit(v):
                svc.open_cash_shift(svc.get_username_id(username), int(v["opening_cash"]), v.get("note", "")); refresh(); _refresh_dashboard()
                messagebox.showinfo("تم", "تم فتح الوردية", parent=_root)
            _prompt_form("فتح وردية خزينة", fields, submit)
        def close_shift():
            vals = _selected_row(tree)
            if not vals:
                messagebox.showwarning("تنبيه", "اختر وردية أولًا", parent=_root); return
            if str(vals[7]) != "OPEN":
                messagebox.showwarning("تنبيه", "الوردية المحددة ليست مفتوحة", parent=_root); return
            fields = [{"name":"closing_cash","label":"النقد الفعلي عند الإغلاق بوحدة العملة الصغرى","type":"int","required":True}]
            def submit(v):
                expected = svc.close_cash_shift(int(vals[0]), int(v["closing_cash"]), svc.get_username_id(username)); refresh(); _refresh_dashboard()
                messagebox.showinfo("تم", f"تم إغلاق الوردية. النقد المتوقع من المدفوعات والمصروفات المسجلة: {expected}", parent=_root)
            _prompt_form("إغلاق الوردية", fields, submit)
        add_action("فتح وردية", open_shift); add_action("إغلاق الوردية المحددة", close_shift)
    elif resource == "expenses":
        add_action("مصروف جديد", lambda: _open_expense_form(refresh))
    elif resource == "journal_entries":
        add_action("قيد يدوي متوازن", lambda: _open_journal_form(refresh))
        def reverse_selected_journal():
            vals = _selected_row(tree)
            if not vals:
                messagebox.showwarning("تنبيه", "اختر قيدًا أولًا", parent=_root)
                return
            if str(vals[6]) != "POSTED":
                messagebox.showwarning("تنبيه", "اختر قيدًا مرحلًا وغير معكوس", parent=_root)
                return
            reason_win_fields = [{"name":"reason","label":"سبب العكس","required":True}]
            def submit(v):
                reversal_id = svc.reverse_manual_journal(int(vals[0]), svc.get_username_id(username), v["reason"])
                refresh(); _refresh_dashboard()
                messagebox.showinfo("تم", f"تم إنشاء قيد العكس رقم المعرف {reversal_id}", parent=_root)
            _prompt_form("عكس قيد يومية يدوي", reason_win_fields, submit,
                         note="يُنشأ قيد جديد بعكس المدين والدائن. لا يتم حذف أو تعديل بنود القيد الأصلي، ولا يمكن عكس القيود التشغيلية من هذه الشاشة.")
        add_action("عكس قيد يدوي", reverse_selected_journal)
    elif resource == "payroll_runs":
        add_action("مسودة رواتب", lambda: _open_payroll_form(refresh))
    elif resource == "roles":
        add_action("إدارة الصلاحيات", _open_role_permissions)


def open_resource_window(resource: str):
    cfg = svc.RESOURCE_CONFIG.get(resource)
    if not cfg:
        messagebox.showerror("خطأ", "هذه الشاشة غير مسجلة", parent=_root); return
    colors = _appearance_colors()
    win = ctk.CTkToplevel(_root)
    win.title(cfg["title"])
    win.geometry("1250x720")
    win.minsize(850, 520)
    win.configure(fg_color=colors["bg"])
    win.transient(_root)
    _style_treeview()

    header = ctk.CTkFrame(win, fg_color=colors["card"], corner_radius=12)
    header.pack(fill="x", padx=16, pady=(16, 8))
    ctk.CTkLabel(header, text=cfg["title"], font=("Segoe UI", 22, "bold"), text_color=colors["text"]).pack(side="right", padx=14, pady=10)

    toolbar = ctk.CTkFrame(win, fg_color="transparent")
    toolbar.pack(fill="x", padx=16, pady=4)
    search_var = tk.StringVar()
    search_entry = ctk.CTkEntry(toolbar, textvariable=search_var, placeholder_text="بحث...", width=280, height=34)
    search_entry.pack(side="right", padx=4)

    table_frame = ctk.CTkFrame(win, fg_color=colors["card"], corner_radius=10)
    table_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))
    tree_holder = tk.Frame(table_frame, bd=0, highlightthickness=0, bg=colors["card"])
    tree_holder.pack(fill="both", expand=True, padx=8, pady=8)
    columns = [f"c{i}" for i in range(len(cfg["columns"]))]
    tree = ttk.Treeview(tree_holder, columns=columns, show="headings", style="Admin.Treeview")
    vscroll = ttk.Scrollbar(tree_holder, orient="vertical", command=tree.yview)
    hscroll = ttk.Scrollbar(tree_holder, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vscroll.grid(row=0, column=1, sticky="ns")
    hscroll.grid(row=1, column=0, sticky="ew")
    tree_holder.rowconfigure(0, weight=1); tree_holder.columnconfigure(0, weight=1)
    for idx, heading in enumerate(cfg["columns"]):
        tree.heading(columns[idx], text=heading)
        tree.column(columns[idx], width=min(240, max(90, len(str(heading)) * 11)), anchor="center", stretch=True)

    def refresh():
        try:
            rows = svc.list_resource(resource, search_var.get())
        except Exception as exc:
            messagebox.showerror("خطأ في قراءة البيانات", str(exc), parent=win)
            return
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=["" if v is None else v for v in row])
        count_label.configure(text=f"عدد السجلات: {len(rows)}")

    count_label = ctk.CTkLabel(toolbar, text="", text_color=colors["subtext"])
    count_label.pack(side="left", padx=8)
    ctk.CTkButton(toolbar, text="تحديث", width=80, command=refresh, height=34).pack(side="left", padx=3)
    search_entry.bind("<Return>", lambda _e: refresh())

    if cfg.get("editable"):
        ctk.CTkButton(toolbar, text="إضافة", width=90, height=34, fg_color=colors["success"],
                      command=lambda: _open_entity_editor(resource, refresh_callback=refresh)).pack(side="left", padx=3)
        def edit_selected():
            vals = _selected_row(tree)
            if not vals:
                messagebox.showwarning("تنبيه", "اختر سجلًا للتعديل", parent=win); return
            _open_entity_editor(resource, _parse_record_id(resource, vals[0]), refresh_callback=refresh)
        ctk.CTkButton(toolbar, text="تعديل", width=90, height=34, command=edit_selected).pack(side="left", padx=3)
        if resource not in {"settings", "doc_sequences", "product_barcodes", "roles"}:
            def deactivate_selected():
                vals = _selected_row(tree)
                if not vals:
                    messagebox.showwarning("تنبيه", "اختر سجلًا أولًا", parent=win); return
                record_id = _parse_record_id(resource, vals[0])
                if not messagebox.askyesno("تأكيد", "هل تريد تعطيل هذا السجل؟ لن يتم حذفه من قاعدة البيانات.", parent=win): return
                try:
                    svc.deactivate_entity(resource, int(record_id), user_id=svc.get_username_id(username)); refresh(); _refresh_dashboard()
                except Exception as exc:
                    messagebox.showerror("تعذر التعطيل", str(exc), parent=win)
            ctk.CTkButton(toolbar, text="تعطيل", width=90, height=34, fg_color=colors["danger"], command=deactivate_selected).pack(side="left", padx=3)

    _resource_action_buttons(resource, toolbar, refresh, tree)
    tree.bind("<Double-1>", lambda _e: _open_entity_editor(resource, _parse_record_id(resource, _selected_row(tree)[0]), refresh) if cfg.get("editable") and _selected_row(tree) else None)
    refresh()
    return win


def open_add_product():
    return open_resource_window("products")


def open_add_to_storage():
    return _open_stock_adjustment(lambda: None)


def open_search_update_page():
    return open_resource_window("products")


def open_statistics_storage_page():
    return open_resource_window("stock_levels")


def open_products_shortage_page():
    return open_resource_window("low_stock_products")


def open_inventory_history_page():
    return open_resource_window("stock_movements")


def open_statistics_page():
    colors = _appearance_colors()
    win = ctk.CTkToplevel(_root)
    win.title("التقارير والتدقيق")
    win.geometry("520x560")
    win.configure(fg_color=colors["bg"])
    win.transient(_root); win.grab_set()
    ctk.CTkLabel(win, text="التقارير والتدقيق", font=("Segoe UI", 22, "bold"), text_color=colors["text"]).pack(pady=18)
    for label, resource in [("الأصناف منخفضة المخزون", "low_stock_products"), ("تقييم تقريبي للمخزون", "stock_valuation"),
                            ("أرصدة العملاء", "customer_balances"), ("أرصدة الموردين", "supplier_balances"),
                            ("القيود غير المتوازنة", "unbalanced_entries"), ("سجل التدقيق", "audit_log")]:
        ctk.CTkButton(win, text=label, height=42, command=lambda r=resource: open_resource_window(r),
                      fg_color=colors["accent"]).pack(fill="x", padx=36, pady=5)
    ctk.CTkButton(win, text="إغلاق", command=win.destroy, fg_color="#6b7280").pack(pady=18)


def open_sells_admin():
    return open_resource_window("sales")


def open_users_controll():
    return open_resource_window("users")


def open_admin(root):
    """Build the dashboard in the supplied Tk/CustomTkinter root."""
    global _root, _dashboard_refresh
    _root = root
    colors = _appearance_colors()
    for widget in root.winfo_children():
        widget.destroy()
    try:
        root.configure(fg_color=colors["bg"])
    except Exception:
        try: root.configure(bg=colors["bg"])
        except Exception: pass

    shell = ctk.CTkFrame(root, fg_color=colors["bg"], corner_radius=0)
    shell.pack(fill="both", expand=True)

    header = ctk.CTkFrame(shell, fg_color=colors["accent"], corner_radius=0, height=76)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="لوحة تحكم MyShop ERP", font=("Segoe UI", 26, "bold"), text_color="#ffffff").pack(side="right", padx=24, pady=18)
    ctk.CTkLabel(header, text=f"المستخدم: {username or 'غير معروف'}", font=("Segoe UI", 14), text_color="#ffffff").pack(side="left", padx=24)

    body = ctk.CTkFrame(shell, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=18, pady=16)
    nav = ctk.CTkScrollableFrame(body, width=300, fg_color=colors["card"], corner_radius=12)
    nav.pack(side="right", fill="y", padx=(12, 0))
    content = ctk.CTkScrollableFrame(body, fg_color="transparent", corner_radius=12)
    content.pack(side="left", fill="both", expand=True)

    ctk.CTkLabel(nav, text="الوحدات", font=("Segoe UI", 20, "bold"), text_color=colors["text"]).pack(fill="x", padx=12, pady=(12, 6))
    for group, resources in ADMIN_GROUPS:
        ctk.CTkLabel(nav, text=group, font=("Segoe UI", 13, "bold"), text_color=colors["subtext"], anchor="e").pack(fill="x", padx=12, pady=(12, 4))
        for label, resource in resources:
            ctk.CTkButton(nav, text=label, anchor="e", height=34, fg_color="transparent", text_color=colors["text"],
                          hover_color=colors["border"], command=lambda r=resource: open_resource_window(r)).pack(fill="x", padx=8, pady=2)

    ctk.CTkLabel(content, text="نظرة عامة", font=("Segoe UI", 25, "bold"), text_color=colors["text"]).pack(anchor="e", padx=6, pady=(2, 10))
    ctk.CTkLabel(content, text="اختر وحدة من القائمة للوصول إلى جداول النظام وإجراءاته. القيود والمخزون المرحل لا يُعدلان من جداول العرض مباشرة.",
                  font=("Segoe UI", 13), text_color=colors["subtext"], wraplength=900, justify="right").pack(anchor="e", fill="x", padx=6, pady=(0, 14))

    cards_frame = ctk.CTkFrame(content, fg_color="transparent")
    cards_frame.pack(fill="x", expand=False)
    for col in range(3): cards_frame.grid_columnconfigure(col, weight=1)
    stats_config = [
        ("products", "المنتجات النشطة", "products"), ("stock_units", "إجمالي وحدات المخزون", "stock_levels"),
        ("low_stock", "أصناف منخفضة المخزون", "low_stock_products"), ("customers", "العملاء", "partners"),
        ("suppliers", "الموردون", "partners"), ("sales_today", "مبيعات اليوم (وحدة صغرى)", "sales"),
        ("receivables", "صافي أرصدة العملاء", "customer_balances"), ("payables", "صافي أرصدة الموردين", "supplier_balances"),
        ("employees", "الموظفون النشطون", "employees"), ("unbalanced", "قيود تحتاج مراجعة", "unbalanced_entries"),
    ]
    stat_labels = {}
    for i, (key, label, resource) in enumerate(stats_config):
        card = ctk.CTkFrame(cards_frame, fg_color=colors["card"], corner_radius=12, border_width=1, border_color=colors["border"])
        card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(card, text=label, font=("Segoe UI", 12), text_color=colors["subtext"], wraplength=190).pack(padx=12, pady=(14, 4))
        value = ctk.CTkLabel(card, text="—", font=("Segoe UI", 23, "bold"), text_color=colors["text"])
        value.pack(padx=12, pady=(0, 6))
        ctk.CTkButton(card, text="فتح", height=28, fg_color=colors["accent"], command=lambda r=resource: open_resource_window(r)).pack(padx=12, pady=(0, 12))
        stat_labels[key] = value

    quick = ctk.CTkFrame(content, fg_color=colors["card"], corner_radius=12)
    quick.pack(fill="x", padx=6, pady=(14, 6))
    ctk.CTkLabel(quick, text="إجراءات سريعة", font=("Segoe UI", 18, "bold"), text_color=colors["text"]).pack(anchor="e", padx=14, pady=(12, 8))
    quick_buttons = [
        ("تسوية مخزون", lambda: _open_stock_adjustment(_refresh_dashboard)),
        ("تسجيل بيع", lambda: _open_sale_form(lambda: None)),
        ("فاتورة شراء", lambda: _open_purchase_invoice_form(lambda: None)),
        ("تسجيل دفعة", lambda: _open_payment_form(lambda: None)),
        ("تسجيل مصروف", lambda: _open_expense_form(lambda: None)),
        ("قيد يومية", lambda: _open_journal_form(lambda: None)),
    ]
    quick_row = ctk.CTkFrame(quick, fg_color="transparent")
    quick_row.pack(fill="x", padx=8, pady=(0, 12))
    for label, command in quick_buttons:
        ctk.CTkButton(quick_row, text=label, command=command, height=36, fg_color=colors["accent"]).pack(side="right", expand=True, fill="x", padx=4)

    footer = ctk.CTkFrame(shell, fg_color=colors["card"], height=54, corner_radius=0)
    footer.pack(fill="x", side="bottom")
    footer.pack_propagate(False)
    ctk.CTkButton(footer, text="خروج", width=100, fg_color=colors["danger"], command=root.destroy).pack(side="left", padx=12, pady=8)
    ctk.CTkButton(footer, text="تبديل المستخدم", width=140, fg_color="#6b7280", command=lambda: [shell.destroy(), go_login(root)]).pack(side="left", padx=6, pady=8)
    ctk.CTkLabel(footer, text="MyShop ERP — SQLite/SQLCipher", text_color=colors["subtext"]).pack(side="right", padx=18)

    def refresh_dashboard():
        try:
            stats = svc.get_dashboard_stats()
            for key, label in stat_labels.items():
                value = stats.get(key, 0)
                label.configure(text=f"{value:,}" if isinstance(value, (int, float)) else str(value))
        except Exception as exc:
            messagebox.showerror("تعذر تحميل الملخص", str(exc), parent=root)
    _dashboard_refresh = refresh_dashboard
    refresh_dashboard()
    return shell
