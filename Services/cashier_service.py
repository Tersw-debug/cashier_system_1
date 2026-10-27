"""Cashier operations for MyShop ERP (migrations 1-6).

All amounts crossing the database boundary are integer minor currency units.
A sale/return and its stock/accounting records are written in one DB transaction.
Excel exports are generated only after a sale transaction has committed.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from Database.Schema import db


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASHIER_REPORTS_ROOT = PROJECT_ROOT / "Cashier_Reports"


def _money_round(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _setting(c, key: str, default: str | None = None) -> str | None:
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def get_currency_decimals() -> int:
    row = db.fetch_one("SELECT value FROM settings WHERE key='currency_decimals'")
    try:
        decimals = int(row[0]) if row and row[0] is not None else 2
    except (TypeError, ValueError):
        decimals = 2
    return max(0, min(4, decimals))


def money_to_minor(value: str | int | float | Decimal, decimals: int | None = None) -> int:
    decimals = get_currency_decimals() if decimals is None else max(0, min(4, int(decimals)))
    try:
        amount = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError, ValueError):
        raise ValueError("أدخل مبلغًا رقميًا صحيحًا") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("المبلغ يجب أن يكون رقمًا غير سالب")
    return _money_round(amount * (Decimal(10) ** decimals))


def minor_to_money(value: int | float | Decimal, decimals: int | None = None) -> str:
    decimals = get_currency_decimals() if decimals is None else max(0, min(4, int(decimals)))
    amount = Decimal(str(value)) / (Decimal(10) ** decimals)
    return f"{amount:.{decimals}f}"


def _next_number(c, sequence_name: str) -> str:
    row = c.execute(
        "SELECT prefix,next_number,padding FROM doc_sequences WHERE name=?",
        (sequence_name,),
    ).fetchone()
    if not row:
        raise ValueError(f"تسلسل الترقيم غير موجود: {sequence_name}")
    prefix, number, padding = row
    c.execute(
        "UPDATE doc_sequences SET next_number=? WHERE name=?",
        (int(number) + 1, sequence_name),
    )
    return f"{prefix}{int(number):0{int(padding)}d}"


def _configured_account_id(c, key: str) -> int:
    code = _setting(c, key)
    if not code:
        raise ValueError(f"إعداد الحساب غير موجود: {key}")
    row = c.execute(
        "SELECT id FROM accounts WHERE code=? AND is_active=1", (str(code),)
    ).fetchone()
    if not row:
        raise ValueError(f"الحساب {code} غير موجود أو غير نشط")
    return int(row[0])


def _audit(
    c,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int,
    new_values: dict[str, Any] | None = None,
    note: str | None = None,
) -> None:
    c.execute(
        """INSERT INTO audit_log(user_id,action,entity,entity_id,new_values,note)
           VALUES(?,?,?,?,?,?)""",
        (
            user_id,
            action,
            entity,
            entity_id,
            json.dumps(new_values, ensure_ascii=False, default=str)
            if new_values is not None else None,
            note,
        ),
    )


def _post_journal(
    c,
    description: str,
    source_type: str,
    source_id: int,
    user_id: int | None,
    lines: list[dict[str, Any]],
) -> int:
    """Create and post a balanced journal entry inside the caller's transaction."""
    if len(lines) < 2:
        raise ValueError("القيد المحاسبي يجب أن يحتوي على بندين على الأقل")

    normalized_lines: list[dict[str, Any]] = []
    for line in lines:
        debit = int(line.get("debit", 0) or 0)
        credit = int(line.get("credit", 0) or 0)
        if debit < 0 or credit < 0 or (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise ValueError("كل بند قيد يجب أن يكون مدينًا أو دائنًا فقط وبقيمة موجبة")
        normalized = dict(line)
        normalized["debit"] = debit
        normalized["credit"] = credit
        normalized_lines.append(normalized)

    debits = sum(line["debit"] for line in normalized_lines)
    credits = sum(line["credit"] for line in normalized_lines)
    if debits <= 0 or debits != credits:
        raise ValueError(f"القيد غير متوازن: المدين {debits}، الدائن {credits}")

    number = _next_number(c, "JOURNAL")
    c.execute(
        """INSERT INTO journal_entries
           (number,entry_date,description,source_type,source_id,status,user_id)
           VALUES(?,?,?,?,?,'DRAFT',?)""",
        (number, date.today().isoformat(), description, source_type, source_id, user_id),
    )
    entry_id = int(c.lastrowid)
    for line in normalized_lines:
        c.execute(
            """INSERT INTO journal_lines
               (entry_id,account_id,partner_id,debit,credit,description)
               VALUES(?,?,?,?,?,?)""",
            (
                entry_id,
                int(line["account_id"]),
                line.get("partner_id"),
                line["debit"],
                line["credit"],
                line.get("description"),
            ),
        )
    c.execute("UPDATE journal_entries SET status='POSTED' WHERE id=?", (entry_id,))
    return entry_id


def get_cashier_context(user_id: int) -> dict[str, Any]:
    """Return active warehouses/customers/payment methods and the user's open shift."""
    warehouses = db.fetch_all(
        """SELECT id,name,is_default FROM warehouses
           WHERE is_active=1 ORDER BY is_default DESC,name"""
    )
    customers = db.fetch_all(
        """SELECT id,name,COALESCE(phone,'') FROM partners
           WHERE is_customer=1 AND is_active=1 ORDER BY name"""
    )
    methods = db.fetch_all(
        """SELECT pm.id,pm.name,pm.kind
           FROM payment_methods pm
           JOIN accounts a ON a.id=pm.account_id AND a.is_active=1
           WHERE pm.is_active=1 ORDER BY pm.name,pm.id"""
    )
    shift = db.fetch_one(
        """SELECT id,opening_cash,opened_at FROM cash_shifts
           WHERE user_id=? AND status='OPEN' ORDER BY id DESC LIMIT 1""",
        (user_id,),
    )
    last_shift = db.fetch_one(
        """SELECT id,opening_cash,opened_at FROM cash_shifts
           WHERE user_id=? ORDER BY id DESC LIMIT 1""",
        (user_id,),
    )
    return {
        "warehouses": warehouses,
        "customers": customers,
        "payment_methods": methods,
        "open_shift": shift,
        "last_shift": last_shift,
        "currency_decimals": get_currency_decimals(),
    }


def get_cashier_products(query: str = "", warehouse_id: int | None = None) -> list[tuple]:
    """Search active products by name, SKU, or barcode.

    Row layout: id, name, sku, barcode, sell_price_minor, stock_qty,
    min_quantity, track_stock, cost_price_minor, tax_rate_bp, section_name.
    """
    query = (query or "").strip()
    params: list[Any] = []
    if warehouse_id is None:
        stock_expr = (
            "COALESCE((SELECT SUM(sl.quantity) FROM stock_levels sl "
            "WHERE sl.product_id=p.id),0)"
        )
    else:
        stock_expr = (
            "COALESCE((SELECT sl.quantity FROM stock_levels sl "
            "WHERE sl.product_id=p.id AND sl.warehouse_id=?),0)"
        )
        params.append(int(warehouse_id))

    sql = f"""SELECT p.id,p.name,COALESCE(p.sku,''),
                COALESCE((SELECT pb.barcode FROM product_barcodes pb
                          WHERE pb.product_id=p.id
                          ORDER BY pb.is_primary DESC,pb.id LIMIT 1),''),
                p.sell_price,{stock_expr},p.min_quantity,p.track_stock,p.cost_price,
                COALESCE((SELECT tr.rate_bp FROM tax_rates tr
                          WHERE tr.id=p.tax_rate_id AND tr.is_active=1),0),
                COALESCE(s.name,''),p.color
             FROM products p LEFT JOIN sections s ON s.id=p.section_id
             WHERE p.is_active=1"""
    if query:
        sql += """ AND (p.name LIKE ? OR p.sku=? OR EXISTS (
                    SELECT 1 FROM product_barcodes pb
                    WHERE pb.product_id=p.id AND pb.barcode=?))"""
        params.extend((f"%{query}%", query, query))
        sql += """ ORDER BY CASE WHEN p.sku=? THEN 0
                    WHEN EXISTS (SELECT 1 FROM product_barcodes pb
                                 WHERE pb.product_id=p.id AND pb.barcode=?)
                    THEN 0 ELSE 1 END,p.name LIMIT 100"""
        params.extend((query, query))
    else:
        sql += " ORDER BY p.name LIMIT 500"
    return db.fetch_all(sql, tuple(params))


def get_cashier_product_groups(warehouse_id: int | None = None):
    rows = get_cashier_products("", warehouse_id)
    sections: dict[str, list[tuple]] = {}
    ungrouped: list[tuple] = []
    for row in rows:
        section_name = (row[10] or "").strip()
        if section_name:
            sections.setdefault(section_name, []).append(row)
        else:
            ungrouped.append(row)
    return sorted(sections.items(), key=lambda item: item[0].casefold()), ungrouped


def get_customer_by_name_phone(name: str, phone: str | None = None) -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    if phone and phone.strip():
        row = db.fetch_one(
            """SELECT id FROM partners
               WHERE is_customer=1 AND name=? COLLATE NOCASE AND phone=? LIMIT 1""",
            (name, phone.strip()),
        )
    else:
        row = db.fetch_one(
            """SELECT id FROM partners
               WHERE is_customer=1 AND name=? COLLATE NOCASE LIMIT 1""",
            (name,),
        )
    return int(row[0]) if row else None


def get_username_id(username: str) -> int | None:
    row = db.fetch_one(
        "SELECT id FROM users WHERE username=? COLLATE NOCASE AND is_active=1",
        (str(username).strip(),),
    )
    return int(row[0]) if row else None


def get_open_shift(user_id: int):
    return db.fetch_one(
        """SELECT id,opening_cash,opened_at FROM cash_shifts
           WHERE user_id=? AND status='OPEN' ORDER BY id DESC LIMIT 1""",
        (user_id,),
    )


def _session_date_from_value(opened_at: Any) -> str:
    """Convert the database timestamp to a portable YYYY-MM-DD directory name."""
    if opened_at:
        text = str(opened_at).strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(text[:10]).isoformat()
            except ValueError:
                pass
    return date.today().isoformat()


def get_cashier_session_folder(shift_id: int, create: bool = True) -> str:
    """Return the folder for a shift, grouped by the date the shift started."""
    shift = db.fetch_one("SELECT opened_at FROM cash_shifts WHERE id=?", (int(shift_id),))
    if not shift:
        raise ValueError("الوردية غير موجودة")
    folder = CASHIER_REPORTS_ROOT / _session_date_from_value(shift[0])
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def open_cashier_shift(user_id: int, opening_cash_minor: int = 0) -> int:
    opening_cash_minor = int(opening_cash_minor)
    if opening_cash_minor < 0:
        raise ValueError("رصيد بداية الوردية لا يمكن أن يكون سالبًا")
    # Verify that the required date folder can be created before opening the shift.
    # The DB's opened_at field uses local time, matching the local date here.
    (CASHIER_REPORTS_ROOT / date.today().isoformat()).mkdir(parents=True, exist_ok=True)
    with db.transaction() as c:
        if c.execute(
            "SELECT 1 FROM cash_shifts WHERE user_id=? AND status='OPEN' LIMIT 1",
            (user_id,),
        ).fetchone():
            raise ValueError("لديك وردية مفتوحة بالفعل")
        c.execute(
            """INSERT INTO cash_shifts(user_id,opening_cash,note,status)
               VALUES(?,?,?,'OPEN')""",
            (user_id, opening_cash_minor, "بدأت من صفحة الكاشير"),
        )
        shift_id = int(c.lastrowid)
        _audit(
            c,
            user_id,
            "OPEN_SHIFT",
            "cash_shifts",
            shift_id,
            {"opening_cash": opening_cash_minor, "status": "OPEN"},
        )
    # The folder is already prepared; resolve it from the persisted timestamp too,
    # in case the shift crossed a local date boundary while it was being opened.
    get_cashier_session_folder(shift_id, create=True)
    return shift_id


def close_cashier_shift(shift_id: int, closing_cash_minor: int, user_id: int) -> int:
    closing_cash_minor = int(closing_cash_minor)
    if closing_cash_minor < 0:
        raise ValueError("النقد الفعلي لا يمكن أن يكون سالبًا")
    with db.transaction() as c:
        shift = c.execute(
            "SELECT opening_cash,status FROM cash_shifts WHERE id=? AND user_id=?",
            (shift_id, user_id),
        ).fetchone()
        if not shift or shift[1] != "OPEN":
            raise ValueError("الوردية غير موجودة أو مغلقة")
        cash_in = c.execute(
            """SELECT COALESCE(SUM(py.amount),0) FROM payments py
               JOIN payment_methods pm ON pm.id=py.method_id
               WHERE py.shift_id=? AND py.direction='IN' AND pm.kind='CASH'""",
            (shift_id,),
        ).fetchone()[0]
        cash_out = c.execute(
            """SELECT COALESCE(SUM(py.amount),0) FROM payments py
               JOIN payment_methods pm ON pm.id=py.method_id
               WHERE py.shift_id=? AND py.direction='OUT' AND pm.kind='CASH'""",
            (shift_id,),
        ).fetchone()[0]
        cash_expenses = c.execute(
            """SELECT COALESCE(SUM(e.amount),0) FROM expenses e
               JOIN payment_methods pm ON pm.id=e.method_id
               WHERE e.shift_id=? AND pm.kind='CASH'""",
            (shift_id,),
        ).fetchone()[0]
        cash_returns = c.execute(
            """SELECT COALESCE(SUM(r.total),0)
               FROM sales r JOIN sales original ON original.id=r.original_sale_id
               WHERE r.shift_id=? AND r.status='POSTED' AND r.sale_type='RETURN'
                 AND r.customer_id IS NULL
                 AND EXISTS (
                   SELECT 1 FROM payment_allocations a
                   JOIN payments py ON py.id=a.payment_id
                   JOIN payment_methods pm ON pm.id=py.method_id
                   WHERE a.document_type='SALE' AND a.document_id=original.id
                     AND py.direction='IN' AND pm.kind='CASH'
                 )""",
            (shift_id,),
        ).fetchone()[0]
        expected = (
            int(shift[0]) + int(cash_in or 0) - int(cash_out or 0)
            - int(cash_expenses or 0) - int(cash_returns or 0)
        )
        c.execute(
            """UPDATE cash_shifts SET closed_at=datetime('now','localtime'),
               closing_cash=?,expected_cash=?,status='CLOSED' WHERE id=?""",
            (closing_cash_minor, expected, shift_id),
        )
        _audit(
            c,
            user_id,
            "CLOSE_SHIFT",
            "cash_shifts",
            shift_id,
            {"status": "CLOSED", "closing_cash": closing_cash_minor, "expected_cash": expected},
        )
        return expected


def create_cashier_sale(
    items: list[dict[str, Any]],
    cashier_id: int,
    warehouse_id: int,
    payment_method_id: int,
    amount_paid_minor: int,
    customer_id: int | None = None,
    new_customer_name: str | None = None,
    new_customer_phone: str | None = None,
    shift_id: int | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Post sale lines, stock movements, payment/allocation, and journals atomically."""
    if not items:
        raise ValueError("السلة فارغة")
    if shift_id is None:
        raise ValueError("ابدأ وردية الكاشير قبل إتمام البيع حتى يمكن تسوية النقدية")
    try:
        amount_paid_minor = int(amount_paid_minor)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("المبلغ المدفوع غير صحيح") from None
    if amount_paid_minor < 0:
        raise ValueError("المبلغ المدفوع لا يمكن أن يكون سالبًا")

    quantities: dict[int, Decimal] = {}
    for item in items:
        try:
            pid = int(item["product_id"])
            quantity = Decimal(str(item["quantity"]))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise ValueError("بيانات المنتجات أو الكميات غير صحيحة") from None
        if pid <= 0 or not quantity.is_finite() or quantity <= 0:
            raise ValueError("كل كمية يجب أن تكون رقمًا موجبًا")
        quantities[pid] = quantities.get(pid, Decimal("0")) + quantity

    with db.transaction() as c:
        warehouse = c.execute("SELECT is_active FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
        if not warehouse or not warehouse[0]:
            raise ValueError("اختر مخزنًا نشطًا")
        cashier = c.execute("SELECT is_active FROM users WHERE id=?", (cashier_id,)).fetchone()
        if not cashier or not cashier[0]:
            raise ValueError("حساب الكاشير غير موجود أو غير نشط")
        method = c.execute(
            """SELECT pm.account_id,pm.kind,pm.is_active
               FROM payment_methods pm
               JOIN accounts a ON a.id=pm.account_id AND a.is_active=1
               WHERE pm.id=?""",
            (payment_method_id,),
        ).fetchone()
        if not method or not method[2] or not method[0]:
            raise ValueError("طريقة الدفع غير نشطة أو غير مرتبطة بحساب أستاذ نشط")
        shift = c.execute("SELECT user_id,status FROM cash_shifts WHERE id=?", (shift_id,)).fetchone()
        if not shift or int(shift[0]) != int(cashier_id) or shift[1] != "OPEN":
            raise ValueError("الوردية المحددة ليست مفتوحة لهذا الكاشير")

        if new_customer_name and new_customer_name.strip():
            new_customer_name = new_customer_name.strip()
            new_customer_phone = (new_customer_phone or "").strip() or None
            if customer_id is not None:
                raise ValueError("اختر عميلًا موجودًا أو أدخل عميلًا جديدًا، وليس الاثنين معًا")
            existing = c.execute(
                """SELECT id FROM partners
                   WHERE is_customer=1 AND name=? COLLATE NOCASE
                     AND COALESCE(phone,'')=COALESCE(?,'') LIMIT 1""",
                (new_customer_name, new_customer_phone),
            ).fetchone()
            if existing:
                customer_id = int(existing[0])
            else:
                c.execute(
                    "INSERT INTO partners(name,phone,is_customer,is_supplier) VALUES(?,?,1,0)",
                    (new_customer_name, new_customer_phone),
                )
                customer_id = int(c.lastrowid)
                _audit(
                    c, cashier_id, "CREATE", "partners", customer_id,
                    {"name": new_customer_name, "phone": new_customer_phone, "is_customer": True},
                    "إنشاء عميل من صفحة الكاشير",
                )

        if customer_id is not None:
            customer = c.execute(
                "SELECT is_customer,is_active FROM partners WHERE id=?", (customer_id,)
            ).fetchone()
            if not customer or not customer[0] or not customer[1]:
                raise ValueError("العميل غير موجود أو غير نشط")

        allow_negative = _setting(c, "allow_negative_stock", "0") == "1"
        line_rows: list[dict[str, Any]] = []
        subtotal = tax_total = cogs_total = 0

        for pid, quantity in quantities.items():
            product = c.execute(
                """SELECT p.name,p.sell_price,p.cost_price,p.track_stock,p.is_active,p.tax_rate_id,
                          COALESCE((SELECT tr.rate_bp FROM tax_rates tr
                                    WHERE tr.id=p.tax_rate_id AND tr.is_active=1),0)
                   FROM products p WHERE p.id=?""",
                (pid,),
            ).fetchone()
            if not product or not product[4]:
                raise ValueError(f"المنتج رقم {pid} غير موجود أو غير نشط")
            name, unit_price, unit_cost, track_stock, _active, _tax_rate_id, tax_rate_bp = product
            if unit_price is None or int(unit_price) < 0:
                raise ValueError(f"سعر البيع غير صحيح للمنتج {name}")
            if unit_cost is None or int(unit_cost) < 0:
                raise ValueError(f"تكلفة المنتج غير صحيحة للمنتج {name}")
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError(f"كمية غير صالحة للمنتج {name}")
            if track_stock:
                stock_row = c.execute(
                    "SELECT quantity FROM stock_levels WHERE product_id=? AND warehouse_id=?",
                    (pid, warehouse_id),
                ).fetchone()
                available = Decimal(str(stock_row[0])) if stock_row else Decimal("0")
                if quantity > available and not allow_negative:
                    raise ValueError(f"المخزون غير كافٍ للمنتج {name}: المتاح {available}")

            base = _money_round(quantity * Decimal(int(unit_price)))
            tax = _money_round(Decimal(base) * Decimal(int(tax_rate_bp or 0)) / Decimal(10000))
            line_total = base + tax
            cogs = _money_round(quantity * Decimal(int(unit_cost))) if track_stock else 0
            subtotal += base
            tax_total += tax
            cogs_total += cogs
            line_rows.append({
                "product_id": pid, "name": name, "quantity": float(quantity),
                "unit_price": int(unit_price), "unit_cost": int(unit_cost),
                "tax_rate_bp": int(tax_rate_bp or 0), "tax_amount": tax,
                "line_total": line_total, "base": base, "cogs": cogs,
                "track_stock": bool(track_stock),
            })

        total = subtotal + tax_total
        if total <= 0:
            raise ValueError("لا يمكن إتمام فاتورة بقيمة صفر")
        if amount_paid_minor > total:
            raise ValueError("المبلغ المدفوع لا يمكن أن يتجاوز إجمالي الفاتورة")
        if customer_id is None and amount_paid_minor != total:
            raise ValueError("البيع النقدي المباشر يجب دفعه بالكامل؛ اختر عميلًا لتسجيل المديونية")

        sale_number = _next_number(c, "SALE")
        c.execute(
            """INSERT INTO sales
               (number,sale_type,customer_id,warehouse_id,cashier_id,shift_id,status,
                subtotal,tax_total,discount,total,note)
               VALUES(?,'SALE',?,?,?,?, 'POSTED',?,?,0,?,?)""",
            (sale_number, customer_id, warehouse_id, cashier_id, shift_id,
             subtotal, tax_total, total, note or None),
        )
        sale_id = int(c.lastrowid)

        for line in line_rows:
            c.execute(
                """INSERT INTO sale_items
                   (sale_id,product_id,product_name,quantity,unit_price,unit_cost,
                    line_discount,tax_rate_bp,tax_amount,line_total)
                   VALUES(?,?,?,?,?,?,0,?,?,?)""",
                (sale_id, line["product_id"], line["name"], line["quantity"],
                 line["unit_price"], line["unit_cost"], line["tax_rate_bp"],
                 line["tax_amount"], line["line_total"]),
            )
            if line["track_stock"]:
                c.execute(
                    """INSERT INTO stock_movements
                       (product_id,warehouse_id,movement_type,quantity_change,unit_cost,
                        reference_type,reference_id,user_id,note)
                       VALUES(?,?,'SALE',?,?,?,?,?,?)""",
                    (line["product_id"], warehouse_id, -line["quantity"], line["unit_cost"],
                     "SALE", sale_id, cashier_id, note or None),
                )

        ar_id = _configured_account_id(c, "account.receivable")
        sales_account_id = _configured_account_id(c, "account.sales")
        tax_account_id = _configured_account_id(c, "account.tax_payable")
        inventory_account_id = _configured_account_id(c, "account.inventory")
        cogs_account_id = _configured_account_id(c, "account.cogs")
        sale_lines: list[dict[str, Any]] = [
            {"account_id": ar_id, "debit": total, "credit": 0, "partner_id": customer_id},
            {"account_id": sales_account_id, "debit": 0, "credit": subtotal, "partner_id": customer_id},
        ]
        if tax_total:
            sale_lines.append({"account_id": tax_account_id, "debit": 0, "credit": tax_total,
                               "partner_id": customer_id})
        if cogs_total:
            sale_lines.extend([
                {"account_id": cogs_account_id, "debit": cogs_total, "credit": 0, "partner_id": customer_id},
                {"account_id": inventory_account_id, "debit": 0, "credit": cogs_total, "partner_id": customer_id},
            ])
        _post_journal(c, f"فاتورة بيع {sale_number}", "SALE", sale_id, cashier_id, sale_lines)

        payment_id = None
        if amount_paid_minor > 0:
            payment_number = _next_number(c, "PAYMENT")
            c.execute(
                """INSERT INTO payments(number,direction,partner_id,method_id,shift_id,amount,note,user_id)
                   VALUES(?,'IN',?,?,?,?,?,?)""",
                (payment_number, customer_id, payment_method_id, shift_id, amount_paid_minor,
                 f"تحصيل فاتورة {sale_number}", cashier_id),
            )
            payment_id = int(c.lastrowid)
            c.execute(
                """INSERT INTO payment_allocations(payment_id,document_type,document_id,amount)
                   VALUES(?,'SALE',?,?)""",
                (payment_id, sale_id, amount_paid_minor),
            )
            _post_journal(
                c, f"تحصيل {payment_number} للفاتورة {sale_number}", "PAYMENT", payment_id, cashier_id,
                [
                    {"account_id": int(method[0]), "debit": amount_paid_minor, "credit": 0, "partner_id": customer_id},
                    {"account_id": ar_id, "debit": 0, "credit": amount_paid_minor, "partner_id": customer_id},
                ],
            )
            _audit(c, cashier_id, "CREATE", "payments", payment_id,
                   {"number": payment_number, "direction": "IN", "sale_id": sale_id,
                    "amount": amount_paid_minor, "method_id": payment_method_id})

        _audit(c, cashier_id, "POST", "sales", sale_id,
               {"number": sale_number, "customer_id": customer_id, "warehouse_id": warehouse_id,
                "subtotal": subtotal, "tax_total": tax_total, "total": total,
                "amount_paid": amount_paid_minor, "payment_id": payment_id})
        return {
            "sale_id": sale_id, "number": sale_number, "subtotal": subtotal,
            "tax_total": tax_total, "total": total, "amount_paid": amount_paid_minor,
            "remaining": total - amount_paid_minor, "payment_id": payment_id,
            "item_count": len(line_rows), "customer_id": customer_id,
        }


def get_returnable_sales_items(sale_identifier: str | int) -> tuple[int, str, list[tuple]]:
    """Return (sale_id, sale_number, remaining item rows) for a posted sale."""
    identifier = str(sale_identifier).strip()
    if not identifier:
        raise ValueError("أدخل رقم الفاتورة أو معرفها")
    numeric_id = int(identifier) if identifier.isdigit() else -1
    row = db.fetch_one(
        """SELECT id,number,status,sale_type FROM sales
           WHERE id=? OR number=? ORDER BY id DESC LIMIT 1""",
        (numeric_id, identifier),
    )
    if not row or row[2] != "POSTED" or row[3] != "SALE":
        raise ValueError("فاتورة البيع الأصلية غير موجودة أو غير مرحلة")
    sale_id, sale_number = int(row[0]), row[1]
    items = db.fetch_all(
        """SELECT si.product_id,si.product_name,SUM(si.quantity) AS sold_qty,
                  MIN(si.unit_price),MIN(si.unit_cost)
           FROM sale_items si WHERE si.sale_id=?
           GROUP BY si.product_id,si.product_name ORDER BY si.product_name""",
        (sale_id,),
    )
    result = []
    for item in items:
        pid, name, sold_qty, unit_price, unit_cost = item
        returned_row = db.fetch_one(
            """SELECT COALESCE(SUM(ri.quantity),0)
               FROM sales r JOIN sale_items ri ON ri.sale_id=r.id
               WHERE r.original_sale_id=? AND r.sale_type='RETURN'
                 AND r.status='POSTED' AND ri.product_id=?""",
            (sale_id, pid),
        )
        remaining = float(sold_qty) - float(returned_row[0] if returned_row else 0)
        if remaining > 1e-9:
            result.append((int(pid), name, remaining, int(unit_price), int(unit_cost)))
    return sale_id, sale_number, result


def create_cashier_return(
    original_sale_id: int,
    product_id: int,
    quantity: float,
    cashier_id: int,
    shift_id: int | None = None,
    note: str = "",
) -> int:
    """Post a return without altering the original sale."""
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("كمية المرتجع غير صحيحة") from None
    if not qty.is_finite() or qty <= 0:
        raise ValueError("كمية المرتجع يجب أن تكون موجبة")
    if shift_id is None:
        raise ValueError("ابدأ وردية الكاشير قبل تسجيل المرتجع")

    with db.transaction() as c:
        shift = c.execute("SELECT user_id,status FROM cash_shifts WHERE id=?", (shift_id,)).fetchone()
        if not shift or int(shift[0]) != int(cashier_id) or shift[1] != "OPEN":
            raise ValueError("الوردية المحددة ليست مفتوحة لهذا الكاشير")
        original = c.execute(
            """SELECT number,customer_id,warehouse_id,status,sale_type
               FROM sales WHERE id=?""",
            (int(original_sale_id),),
        ).fetchone()
        if not original or original[3] != "POSTED" or original[4] != "SALE":
            raise ValueError("فاتورة البيع الأصلية غير موجودة أو غير مرحلة")
        line = c.execute(
            """SELECT product_name,SUM(quantity),MIN(unit_price),MIN(unit_cost),
                      SUM(line_discount),MAX(tax_rate_bp)
               FROM sale_items WHERE sale_id=? AND product_id=?
               GROUP BY product_id,product_name""",
            (int(original_sale_id), int(product_id)),
        ).fetchone()
        if not line:
            raise ValueError("المنتج غير موجود ضمن فاتورة البيع الأصلية")
        product_name, sold_qty_raw, unit_price, unit_cost, total_discount, tax_rate_bp = line
        sold_qty = Decimal(str(sold_qty_raw))
        returned_row = c.execute(
            """SELECT COALESCE(SUM(ri.quantity),0)
               FROM sales r JOIN sale_items ri ON ri.sale_id=r.id
               WHERE r.original_sale_id=? AND r.sale_type='RETURN'
                 AND r.status='POSTED' AND ri.product_id=?""",
            (int(original_sale_id), int(product_id)),
        ).fetchone()
        remaining = sold_qty - Decimal(str(returned_row[0] or 0))
        if qty > remaining:
            raise ValueError(f"الكمية المتبقية للمرتجع {max(remaining, Decimal('0')):g} فقط")

        base = _money_round(qty * Decimal(int(unit_price)))
        discount = min(base, _money_round(Decimal(int(total_discount or 0)) * qty / sold_qty)) if sold_qty else 0
        tax_bp = int(tax_rate_bp or 0)
        tax_amount = _money_round(Decimal(base - discount) * Decimal(tax_bp) / Decimal(10000))
        total = base - discount + tax_amount
        if total <= 0:
            raise ValueError("لا يمكن إنشاء مرتجع بقيمة صفر")

        number = _next_number(c, "SALE_RETURN")
        c.execute(
            """INSERT INTO sales
               (number,sale_type,original_sale_id,customer_id,warehouse_id,cashier_id,shift_id,
                status,subtotal,tax_total,discount,total,note)
               VALUES(?,'RETURN',?,?,?,?,?,'POSTED',?,?,?,?,?)""",
            (number, int(original_sale_id), original[1], original[2], cashier_id, shift_id,
             base, tax_amount, discount, total, note or f"مرتجع من {original[0]}"),
        )
        return_id = int(c.lastrowid)
        c.execute(
            """INSERT INTO sale_items
               (sale_id,product_id,product_name,quantity,unit_price,unit_cost,line_discount,
                tax_rate_bp,tax_amount,line_total)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (return_id, int(product_id), product_name, float(qty), int(unit_price),
             int(unit_cost), discount, tax_bp, tax_amount, total),
        )
        product = c.execute("SELECT track_stock FROM products WHERE id=?", (int(product_id),)).fetchone()
        track_stock = bool(product and product[0])
        if track_stock:
            c.execute(
                """INSERT INTO stock_movements
                   (product_id,warehouse_id,movement_type,quantity_change,unit_cost,
                    reference_type,reference_id,user_id,note)
                   VALUES(?,?,'SALE_RETURN',?,?,?,?,?,?)""",
                (int(product_id), int(original[2]), float(qty), int(unit_cost),
                 "SALE_RETURN", return_id, cashier_id, note or None),
            )

        returns_account = _configured_account_id(c, "account.sales_returns")
        tax_account = _configured_account_id(c, "account.tax_payable")
        ar_account = _configured_account_id(c, "account.receivable")
        lines: list[dict[str, Any]] = [{
            "account_id": returns_account, "debit": base - discount, "credit": 0,
            "partner_id": original[1],
        }]
        if tax_amount:
            lines.append({"account_id": tax_account, "debit": tax_amount, "credit": 0,
                          "partner_id": original[1]})
        if original[1] is not None:
            counter_account = ar_account
        else:
            payment_method = c.execute(
                """SELECT pm.account_id FROM payment_allocations a
                   JOIN payments py ON py.id=a.payment_id
                   JOIN payment_methods pm ON pm.id=py.method_id
                   JOIN accounts ac ON ac.id=pm.account_id AND ac.is_active=1
                   WHERE a.document_type='SALE' AND a.document_id=? AND py.direction='IN'
                   ORDER BY py.id LIMIT 1""",
                (int(original_sale_id),),
            ).fetchone()
            counter_account = int(payment_method[0]) if payment_method and payment_method[0] else _configured_account_id(c, "account.cash")
        lines.append({"account_id": counter_account, "debit": 0, "credit": total, "partner_id": original[1]})
        if track_stock:
            cogs_reversal = _money_round(qty * Decimal(int(unit_cost)))
            if cogs_reversal:
                inv_account = _configured_account_id(c, "account.inventory")
                cogs_account = _configured_account_id(c, "account.cogs")
                lines.extend([
                    {"account_id": inv_account, "debit": cogs_reversal, "credit": 0, "partner_id": original[1]},
                    {"account_id": cogs_account, "debit": 0, "credit": cogs_reversal, "partner_id": original[1]},
                ])
        _post_journal(c, f"مرتجع بيع {number}", "SALE_RETURN", return_id, cashier_id, lines)
        _audit(c, cashier_id, "POST_RETURN", "sales", return_id,
               {"number": number, "original_sale_id": int(original_sale_id),
                "product_id": int(product_id), "quantity": float(qty), "total": total})
        return return_id


def export_cashier_sale_to_excel(sale_id: int, shift_id: int | None = None) -> str:
    """Append/update a sale in the single workbook for its session date.

    File: Cashier_Reports/YYYY-MM-DD/Sales_Register.xlsx
    Worksheet: سجل المبيعات

    There is one row per sale. The first column contains the operation/invoice
    number that the cashier can enter in the return dialog to find the sale.
    Product details are wrapped in one cell so invoice totals are not duplicated
    across multiple product rows. This function runs after the sale transaction
    commits; the ERP database remains the source of truth.
    """
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("تصدير Excel يحتاج تثبيت المكتبة: pip install openpyxl") from exc

    sale = db.fetch_one(
        """SELECT id,number,sale_type,customer_id,warehouse_id,cashier_id,shift_id,status,
                  subtotal,tax_total,discount,total,note
           FROM sales WHERE id=?""",
        (int(sale_id),),
    )
    if not sale:
        raise ValueError("لم يتم العثور على الفاتورة المطلوبة لتصديرها")
    if sale[7] != "POSTED" or sale[2] != "SALE":
        raise ValueError("تصدير Excel متاح لفواتير البيع المرحلة فقط")

    sale_shift_id = int(sale[6]) if sale[6] is not None else None
    if sale_shift_id is None:
        raise ValueError("لا توجد وردية مرتبطة بالفاتورة")
    if shift_id is not None and int(shift_id) != sale_shift_id:
        raise ValueError("رقم الوردية لا يطابق الوردية المسجلة على الفاتورة")
    folder = Path(get_cashier_session_folder(sale_shift_id, create=True))
    output_path = folder / "Sales_Register.xlsx"

    labels = db.fetch_one(
        """SELECT COALESCE(p.name,'عميل نقدي'),COALESCE(p.phone,''),
                  COALESCE(w.name,''),COALESCE(u.username,'')
           FROM sales s
           LEFT JOIN partners p ON p.id=s.customer_id
           LEFT JOIN warehouses w ON w.id=s.warehouse_id
           LEFT JOIN users u ON u.id=s.cashier_id
           WHERE s.id=?""",
        (int(sale_id),),
    )
    customer_name, customer_phone, warehouse_name, cashier_name = labels or (
        "عميل نقدي", "", "", ""
    )
    shift_row = db.fetch_one(
        "SELECT opened_at FROM cash_shifts WHERE id=?", (sale_shift_id,)
    )
    session_started = str(shift_row[0]) if shift_row and shift_row[0] else date.today().isoformat()

    items = db.fetch_all(
        """SELECT si.product_id,si.product_name,si.quantity,si.unit_price,
                  si.line_discount,si.tax_rate_bp,si.tax_amount,si.line_total,
                  COALESCE(p.sku,''),
                  COALESCE((SELECT pb.barcode FROM product_barcodes pb
                            WHERE pb.product_id=si.product_id
                            ORDER BY pb.is_primary DESC,pb.id LIMIT 1),'')
           FROM sale_items si
           LEFT JOIN products p ON p.id=si.product_id
           WHERE si.sale_id=? ORDER BY si.id""",
        (int(sale_id),),
    )
    payments = db.fetch_all(
        """SELECT py.number,pm.name,py.amount,a.amount,py.direction
           FROM payment_allocations a
           JOIN payments py ON py.id=a.payment_id
           JOIN payment_methods pm ON pm.id=py.method_id
           WHERE a.document_type='SALE' AND a.document_id=?
           ORDER BY py.id""",
        (int(sale_id),),
    )

    decimals = get_currency_decimals()
    factor = Decimal(10) ** decimals
    money_format = "#,##0" + ("." + ("0" * decimals) if decimals else "")

    def major(minor: Any) -> float:
        return float(Decimal(int(minor or 0)) / factor)

    def qty_text(value: Any) -> str:
        quantity = Decimal(str(value or 0))
        return format(quantity.normalize(), "f")

    def safe_text(value: Any) -> str:
        """Avoid interpreting user-controlled text as an Excel formula."""
        result = "" if value is None else str(value)
        if result.startswith(("=", "+", "-", "@")):
            return "'" + result
        return result

    item_lines = []
    for item in items:
        pid, name, qty, unit_price, discount, tax_bp, tax_amount, line_total, sku, barcode = item
        identifiers = [f"ID {pid}"]
        if sku:
            identifiers.append(f"SKU {sku}")
        if barcode:
            identifiers.append(f"باركود {barcode}")
        item_lines.append(
            f"{safe_text(name)} ({' | '.join(identifiers)}) — "
            f"الكمية: {qty_text(qty)}؛ سعر الوحدة: {major(unit_price):.{decimals}f}؛ "
            f"الخصم: {major(discount):.{decimals}f}؛ "
            f"الضريبة: {major(tax_amount):.{decimals}f}؛ "
            f"إجمالي السطر: {major(line_total):.{decimals}f}"
        )
    item_details = "\n".join(item_lines) if item_lines else "لا توجد تفاصيل أصناف"

    incoming_paid = sum(
        int(payment[3] or 0) for payment in payments if str(payment[4]).upper() == "IN"
    )
    payment_details = "\n".join(
        f"{payment[0]} — {payment[1]}: {major(payment[3]):.{decimals}f}"
        for payment in payments
    ) or "—"
    remaining = max(0, int(sale[11] or 0) - incoming_paid)

    headers = [
        "رقم العملية / الفاتورة (للمرتجع)",
        "تاريخ بدء الوردية",
        "رقم الوردية",
        "الكاشير",
        "العميل",
        "هاتف العميل",
        "المخزن",
        "تفاصيل الأصناف المباعة",
        "عدد بنود الأصناف",
        "الإجمالي قبل الضريبة",
        "الخصم",
        "الضريبة",
        "إجمالي الفاتورة",
        "المدفوع",
        "المتبقي",
        "الإيصالات وطرق الدفع",
        "ملاحظات",
    ]
    row_values = [
        safe_text(sale[1]),
        session_started,
        sale_shift_id,
        safe_text(cashier_name),
        safe_text(customer_name),
        safe_text(customer_phone),
        safe_text(warehouse_name),
        item_details,
        len(items),
        major(sale[8]),
        major(sale[10]),
        major(sale[9]),
        major(sale[11]),
        major(incoming_paid),
        major(remaining),
        payment_details,
        safe_text(sale[12] or "—"),
    ]

    if output_path.exists():
        try:
            wb = load_workbook(output_path)
        except Exception as exc:
            raise RuntimeError(
                "تعذر فتح سجل المبيعات الحالي. أغلق ملف Excel إن كان مفتوحًا ثم أعد المحاولة."
            ) from exc
        if "سجل المبيعات" in wb.sheetnames:
            ws = wb["سجل المبيعات"]
        else:
            # Migrate a workbook made by an earlier version rather than silently
            # creating a second worksheet in the same daily report.
            ws = wb.active
            ws.title = "سجل المبيعات"
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "سجل المبيعات"

    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A4"

    navy = "17365D"
    blue = "D9EAF7"
    pale = "F3F6FA"
    white = "FFFFFF"
    dark = "263238"
    thin_gray = Side(style="thin", color="D7DEE8")
    border = Border(bottom=thin_gray)
    title_font = Font(name="Arial", size=16, bold=True, color=white)
    header_font = Font(name="Arial", size=10, bold=True, color=white)
    body_font = Font(name="Arial", size=10, color=dark)

    if ws.max_row < 3 or ws.cell(row=3, column=1).value != headers[0]:
        # Initialize/reinitialize the layout only when it is not already the
        # cumulative register format. Existing register data is never overwritten.
        if ws.max_row == 1 and ws.cell(1, 1).value is None:
            pass
        elif ws.max_row > 1 or ws.cell(1, 1).value is not None:
            # Leave an unrelated legacy sheet untouched and create the intended
            # register only if it does not exist.
            if "سجل المبيعات" in wb.sheetnames and ws.title != "سجل المبيعات":
                ws = wb.create_sheet("سجل المبيعات")
            else:
                ws.delete_rows(1, ws.max_row)
        ws.sheet_view.rightToLeft = True
        ws.merge_cells("A1:Q1")
        ws["A1"] = "سجل عمليات البيع — MyShop ERP"
        ws["A1"].fill = PatternFill("solid", fgColor=navy)
        ws["A1"].font = title_font
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30
        ws.merge_cells("A2:Q2")
        ws["A2"] = (
            "لإرجاع منتج: انسخ رقم العملية من العمود الأول وأدخله في نافذة مرتجع بيع. "
            "يُسجل كل بيع في صف واحد وتظهر تفاصيل الأصناف داخل عمودها."
        )
        ws["A2"].font = Font(name="Arial", size=10, italic=True, color=dark)
        ws["A2"].alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
        ws.row_dimensions[2].height = 30
        for col_index, label in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col_index, value=label)
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[3].height = 36

    # Idempotency: exporting the same committed sale again updates its row rather
    # than duplicating a transaction in the register.
    target_row = None
    for row_index in range(4, ws.max_row + 1):
        if str(ws.cell(row=row_index, column=1).value or "") == str(sale[1]):
            target_row = row_index
            break
    if target_row is None:
        target_row = max(4, ws.max_row + 1)

    for col_index, value in enumerate(row_values, start=1):
        cell = ws.cell(row=target_row, column=col_index, value=value)
        cell.font = body_font
        cell.alignment = Alignment(
            horizontal="right" if col_index in (4, 5, 6, 8, 16, 17) else "center",
            vertical="top",
            wrap_text=True,
        )
        cell.border = border
        if target_row % 2 == 0:
            cell.fill = PatternFill("solid", fgColor=pale)
        if col_index in (10, 11, 12, 13, 14, 15):
            cell.number_format = money_format
        if col_index in (1, 3, 9, 10, 11, 12, 13, 14, 15):
            cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)

    wrapped_lines = max(1, len(item_lines), len(payment_details.splitlines()))
    ws.row_dimensions[target_row].height = min(180, max(34, wrapped_lines * 28))

    widths = [27, 22, 12, 18, 24, 17, 22, 68, 15, 19, 15, 15, 19, 17, 17, 38, 32]
    for col_index, width in enumerate(widths, start=1):
        letter = get_column_letter(col_index)
        ws.column_dimensions[letter].width = width

    last_data_row = max(3, ws.max_row)
    ws.auto_filter.ref = f"A3:Q{last_data_row}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.outlinePr.summaryBelow = True

    # Atomic replacement protects the register from being left half-written if
    # the application exits during save. Excel should be closed while new sales
    # are appended on Windows.
    fd, temp_name = tempfile.mkstemp(prefix=".sales_register_", suffix=".xlsx", dir=str(folder))
    os.close(fd)
    try:
        wb.save(temp_name)
        os.replace(temp_name, output_path)
    except PermissionError as exc:
        raise RuntimeError(
            "تعذر تحديث سجل المبيعات. أغلق Sales_Register.xlsx في Excel ثم أعد تصدير العملية."
        ) from exc
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass
    return str(output_path)
