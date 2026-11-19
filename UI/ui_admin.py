"""Native PySide6 Arabic admin dashboard for the MyShop ERP schema.

This module intentionally has no dependency on UI.qt_compat.  Database and
business operations remain in Services.admin_service; this file only owns the
Qt presentation layer.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSettings, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
    QFileDialog
)

from UI.common import is_dark
from UI.router import go_login
from Services import admin_service as svc


username = ""
_root: QWidget | None = None
_dashboard_refresh: Callable[[], None] | None = None
_open_windows: list[QDialog] = []


def getUsername(username_from_login: str):
    global username
    username = username_from_login or ""


def _appearance_colors() -> dict[str, str]:
    dark = is_dark()
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
        "input": "#171d26" if dark else "#fbfcfd",
    }


def _optional_int(values: dict[str, Any], key: str) -> int | None:
    raw = values.get(key)
    if raw is None or str(raw).strip() == "":
        return None
    return int(raw)


def export_sales_excel(_checked: bool = False) -> bool:
    file_path, _ = QFileDialog.getSaveFileName(
        _root, "تصدير المبيعات", "sales.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not file_path:
        return False
    if not file_path.lower().endswith(".xlsx"):
        file_path += ".xlsx"
    try:
        exported_count = svc.export_sales_excel(file_path)
    except Exception as exc:
        _message("error", "فشل تصدير المبيعات", str(exc), _root)
        return False
    _message("info", "اكتمل التصدير", f"تم تصدير {exported_count:,} سجلًا.\n{file_path}", _root)
    return True


def export_storage_excel(_checked: bool = False) -> bool:
    file_path, _ = QFileDialog.getSaveFileName(
        _root, "تصدير أرصدة المخزون", "storage_balances.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not file_path:
        return False
    if not file_path.lower().endswith(".xlsx"):
        file_path += ".xlsx"
    try:
        exported_count = svc.export_storage_excel(file_path)
    except Exception as exc:
        _message("error", "فشل تصدير المخزون", str(exc), _root)
        return False
    _message("info", "اكتمل التصدير", f"تم تصدير {exported_count:,} سجلًا.\n{file_path}", _root)
    return True


def export_debts_excel(_checked: bool = False) -> bool:
    file_path, _ = QFileDialog.getSaveFileName(
        _root, "تصدير سجل حركة الديون", "debt_log.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not file_path:
        return False
    if not file_path.lower().endswith(".xlsx"):
        file_path += ".xlsx"
    try:
        exported_count = svc.export_debts_excel(file_path)
    except Exception as exc:
        _message("error", "فشل تصدير سجل الديون", str(exc), _root)
        return False
    _message("info", "اكتمل التصدير", f"تم تصدير {exported_count:,} سجلًا.\n{file_path}", _root)
    return True


def export_stock_movements_excel(_checked: bool = False) -> bool:
    file_path, _ = QFileDialog.getSaveFileName(
        _root, "تصدير حركات المخزون", "stock_movements.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not file_path:
        return False
    if not file_path.lower().endswith(".xlsx"):
        file_path += ".xlsx"
    try:
        exported_count = svc.export_stock_movements_excel(file_path)
    except Exception as exc:
        _message("error", "فشل تصدير حركات المخزون", str(exc), _root)
        return False
    _message("info", "اكتمل التصدير", f"تم تصدير {exported_count:,} سجلًا.\n{file_path}", _root)
    return True


def export_shifts_excel(_checked: bool = False) -> bool:
    file_path, _ = QFileDialog.getSaveFileName(
        _root, "تصدير ورديات الخزينة", "cash_shifts.xlsx", "Excel Workbook (*.xlsx)"
    )
    if not file_path:
        return False
    if not file_path.lower().endswith(".xlsx"):
        file_path += ".xlsx"
    try:
        exported_count = svc.export_shifts_excel(file_path)
    except Exception as exc:
        _message("error", "فشل تصدير الورديات", str(exc), _root)
        return False
    _message("info", "اكتمل التصدير", f"تم تصدير {exported_count:,} سجلًا.\n{file_path}", _root)
    return True


def open_excel_export_window(_checked: bool = False):
    """Open the export chooser; each button calls its own service function."""
    colors = _appearance_colors()
    win = QDialog(_root)
    win.setWindowTitle("تصدير بيانات Excel")
    win.resize(430, 430)
    win.setMinimumWidth(380)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setModal(True)
    win.setStyleSheet(f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}")

    layout = QVBoxLayout(win)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)
    layout.addWidget(_label("اختر الجدول الذي تريد تصديره", win, size=17, bold=True))
    layout.addWidget(_label(
        "سيتم تصدير جميع السجلات من الجدول المحدد إلى ملف Excel مستقل.",
        win, size=10, color=colors["subtext"], wrap=True,
    ))

    export_actions = [
        ("تصدير المبيعات", export_sales_excel),
        ("تصدير أرصدة المخزون", export_storage_excel),
        ("تصدير سجل حركة الديون", export_debts_excel),
        ("تصدير حركات المخزون", export_stock_movements_excel),
        ("تصدير ورديات الخزينة", export_shifts_excel),
    ]
    for label, callback in export_actions:
        layout.addWidget(_button(win, label, callback, height=40))

    layout.addStretch(1)
    layout.addWidget(_button(win, "إغلاق", win.accept, color="#6b7280", hover="#555e6b"))
    win.exec()
    return win



def _button(parent: QWidget, text: str, callback: Callable | None = None,
            color: str | None = None, hover: str | None = None,
            height: int = 36, width: int | None = None) -> QPushButton:
    colors = _appearance_colors()
    button = QPushButton(text, parent)
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(height)
    if width is not None:
        button.setFixedWidth(width)
    bg = color or colors["accent"]
    over = hover or colors["accent_hover"]
    button.setStyleSheet(
        "QPushButton {"
        f"background: {bg}; color: white; border: 0; border-radius: 7px;"
        "padding: 6px 12px; font-weight: 600;"
        "}"
        f"QPushButton:hover {{ background: {over}; }}"
        "QPushButton:disabled { background: #858b94; color: #e5e7eb; }"
    )
    if callback is not None:
        button.clicked.connect(callback)
    return button


def _label(text: str, parent: QWidget | None = None, *, size: int = 10,
           bold: bool = False, color: str | None = None,
           align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter,
           wrap: bool = False) -> QLabel:
    colors = _appearance_colors()
    result = QLabel(text, parent)
    result.setAlignment(align)
    result.setWordWrap(wrap)
    result.setFont(QFont("Segoe UI", size, QFont.Bold if bold else QFont.Normal))
    result.setStyleSheet(f"color: {color or colors['text']}; background: transparent;")
    return result


def _line_edit(parent: QWidget, value: str = "", placeholder: str = "") -> QLineEdit:
    colors = _appearance_colors()
    edit = QLineEdit(parent)
    edit.setText(value)
    edit.setPlaceholderText(placeholder)
    edit.setAlignment(Qt.AlignRight)
    edit.setMinimumHeight(34)
    edit.setStyleSheet(
        f"QLineEdit {{ background: {colors['input']}; color: {colors['text']}; "
        f"border: 1px solid {colors['border']}; border-radius: 6px; padding: 5px 8px; }}"
        f"QLineEdit:focus {{ border: 1px solid {colors['accent']}; }}"
    )
    return edit


def _style_combo(combo: QComboBox) -> QComboBox:
    """Apply the same accent theme used by the dashboard buttons."""
    colors = _appearance_colors()

    combo.setMinimumHeight(34)
    combo.setStyleSheet(
        f"""
        QComboBox {{
            background-color: {colors['accent']};
            color: white;
            border: 0;
            border-radius: 7px;
            padding: 6px 10px;
            font-weight: 600;
        }}

        QComboBox:hover {{
            background-color: {colors['accent_hover']};
        }}

        QComboBox::drop-down {{
            border: 0;
            width: 28px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {colors['accent']};
            color: white;
            border: 1px solid {colors['border']};
            outline: 0;
            selection-background-color: {colors['accent_hover']};
            selection-color: white;
        }}

        QComboBox QAbstractItemView::item {{
            padding: 7px 10px;
            min-height: 26px;
        }}

        QComboBox QAbstractItemView::item:hover {{
            background-color: {colors['accent_hover']};
            color: white;
        }}

        QComboBox QAbstractItemView::item:selected {{
            background-color: {colors['accent_hover']};
            color: white;
        }}
        """
    )
    return combo

def _message(kind: str, title: str, message: str, parent: QWidget | None = None) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(str(message))
    box.setIcon({
        "info": QMessageBox.Information,
        "warning": QMessageBox.Warning,
        "error": QMessageBox.Critical,
    }.get(kind, QMessageBox.Information))
    box.setLayoutDirection(Qt.RightToLeft)
    box.exec()


def _ask_yes_no(title: str, message: str, parent: QWidget | None = None) -> bool:
    answer = QMessageBox.question(
        parent, title, message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return answer == QMessageBox.Yes


def _install_page(root: QWidget, page: QWidget) -> None:
    """Install a page in either a QMainWindow or an ordinary QWidget host."""
    if isinstance(root, QMainWindow):
        if hasattr(root, "set_page"):
            root.set_page(page)
        else:
            root.setCentralWidget(page)
        return

    old_layout = root.layout()
    if old_layout is None:
        old_layout = QVBoxLayout(root)
        old_layout.setContentsMargins(0, 0, 0, 0)
    else:
        while old_layout.count():
            item = old_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
    old_layout.addWidget(page)


def _make_scroll_area(parent: QWidget, content: QWidget | None = None) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    area = QScrollArea(parent)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    body = content or QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(5)
    area.setWidget(body)
    return area, body, layout


# Each group exposes actual schema tables/views. Transactional records are
# read-only in the generic browser and changed through explicit workflows.
ADMIN_GROUPS = [
    ("الملخص", [
        ("المنتجات", "products"), ("الأقسام", "sections"), ("وحدات القياس", "units"),
        ("باركود المنتجات", "product_barcodes"), ("الضرائب", "tax_rates"),
    ]),
    ("المخزون", [
        ("أرصدة المخزون", "stock_levels"), ("الأصناف منخفضة المخزون", "low_stock_products"),
        ("حركة المخزون", "stock_movements"), ("تقييم تقريبي للمخزون", "stock_valuation"),
        ("المخازن", "warehouses"), ("التحويلات", "stock_transfers"),
        ("بنود التحويلات", "stock_transfer_items"), ("سجل حركة الديون", "debt_log"),
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


def _parse_record_id(resource: str, value: Any):
    if resource in {"settings", "doc_sequences"}:
        return str(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _field_default(field: dict):
    default = field.get("default", "")
    return date.today().isoformat() if default == "today" else default


class ColorField(QWidget):
    """Hex entry with a preview swatch and QColorDialog picker."""

    def __init__(self, parent: QWidget | None = None, initial: str = ""):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._entry = _line_edit(self, str(initial or ""), "#RRGGBB")
        self._entry.textChanged.connect(self._update_swatch)
        self._swatch = QLabel(self)
        self._swatch.setFixedSize(34, 34)
        self._swatch.setStyleSheet("border: 1px solid #8b929c; border-radius: 5px;")
        pick = _button(self, "اختيار", self._pick, height=34, width=70)
        clear = _button(self, "مسح", self.clear, color="#6b7280", hover="#555e6b", height=34, width=60)
        layout.addWidget(self._entry, 1)
        layout.addWidget(self._swatch)
        layout.addWidget(pick)
        layout.addWidget(clear)
        self._update_swatch()

    def get(self) -> str:
        return self._entry.text()

    def clear(self) -> None:
        self._entry.clear()

    def _valid(self) -> str | None:
        value = self._entry.text().strip()
        if value and not value.startswith("#"):
            value = "#" + value
        if len(value) == 7 and all(ch in "0123456789abcdefABCDEF" for ch in value[1:]):
            return value
        return None

    def _update_swatch(self, *_args) -> None:
        color = self._valid()
        self._swatch.setStyleSheet(
            f"background: {color}; border: 1px solid #8b929c; border-radius: 5px;"
            if color else "background: transparent; border: 1px dashed #8b929c; border-radius: 5px;"
        )

    def _pick(self) -> None:
        initial = QColor(self._valid()) if self._valid() else QColor("#ffffff")
        selected = QColorDialog.getColor(initial, self, "اختر لون المنتج")
        if selected.isValid():
            self._entry.setText(selected.name().upper())


def _make_choice_widget(parent: QWidget, field: dict, current: Any):
    """Return a native Qt editor and its value mode."""
    name = field["name"]
    if name == "color":
        return ColorField(parent, current or ""), "color"

    supplied_choices = field.get("choice_values")
    if supplied_choices:
        if all(isinstance(item, (tuple, list)) and len(item) == 2 for item in supplied_choices):
            choices = [(item[0], item[1]) for item in supplied_choices]
        else:
            choices = [(item, item) for item in supplied_choices]
    else:
        choices = svc.get_field_choices(name)

    if choices:
        combo = _style_combo(QComboBox(parent))
        combo.addItem("", "")
        for value, label in choices:
            combo.addItem(f"{value} — {label}", value)
        if current not in (None, ""):
            for index in range(combo.count()):
                if str(combo.itemData(index)) == str(current):
                    combo.setCurrentIndex(index)
                    break
        return combo, "combo"

    if name in _ENUM_CHOICES:
        combo = QComboBox(parent)
        combo.setMinimumHeight(34)
        for value in _ENUM_CHOICES[name]:
            combo.addItem(value, value)
        target = str(current if current not in (None, "") else field.get("default", _ENUM_CHOICES[name][0]))
        index = combo.findData(target)
        if index >= 0:
            combo.setCurrentIndex(index)
        return combo, "combo"

    edit = _line_edit(parent)
    if current not in (None, ""):
        edit.setText(str(current))
    elif _field_default(field) not in (None, ""):
        edit.setText(str(_field_default(field)))
    if field.get("secret"):
        edit.setEchoMode(QLineEdit.Password)
    return edit, "line"


def _widget_value(widget: QWidget, mode: str):
    if mode == "color":
        return widget.get()  # type: ignore[attr-defined]
    if mode == "combo":
        value = widget.currentData()  # type: ignore[attr-defined]
        return "" if value is None else value
    return widget.text().strip()  # type: ignore[attr-defined]


def _prompt_form(title: str, fields: list[dict], on_submit: Callable[[dict], Any],
                 record: dict | None = None, parent: QWidget | None = None,
                 note: str | None = None) -> QDialog:
    parent = parent or _root
    colors = _appearance_colors()
    win = QDialog(parent)
    win.setWindowTitle(title)
    win.resize(650, 760)
    win.setMinimumSize(520, 420)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setModal(True)
    win.setStyleSheet(f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}")
    root_layout = QVBoxLayout(win)
    root_layout.setContentsMargins(18, 14, 18, 14)
    root_layout.setSpacing(8)
    heading = _label(title, win, size=20, bold=True)
    root_layout.addWidget(heading)
    if note:
        note_label = _label(note, win, size=10, color=colors["subtext"], wrap=True)
        root_layout.addWidget(note_label)

    scroll = QScrollArea(win)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    body = QWidget()
    body.setStyleSheet(f"background: {colors['card']}; border-radius: 9px;")
    form = QFormLayout(body)
    form.setContentsMargins(14, 12, 14, 12)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(9)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setFormAlignment(Qt.AlignTop)

    widgets: dict[str, QWidget] = {}
    modes: dict[str, str] = {}
    for field in fields:
        current = (record or {}).get(field["name"], _field_default(field))
        widget, mode = _make_choice_widget(body, field, current)
        label = _label(field["label"], body, size=10)
        form.addRow(label, widget)
        widgets[field["name"]] = widget
        modes[field["name"]] = mode
    scroll.setWidget(body)
    root_layout.addWidget(scroll, 1)

    footer = QHBoxLayout()
    footer.addStretch(1)

    def submit() -> None:
        values = {
            name: _widget_value(widget, modes[name])
            for name, widget in widgets.items()
        }

        missing = [
            field["label"]
            for field in fields
            if field.get("required")
            and (
                values.get(field["name"]) is None
                or str(values[field["name"]]).strip() == ""
            )
        ]

        if missing:
            _message(
                "warning",
                "بيانات مطلوبة",
                "يرجى إدخال البيانات التالية:\n" + "\n".join(missing),
                win,
            )
            return

        try:
            result = on_submit(values)
        except Exception as exc:
            _message("error", "تعذر الحفظ", str(exc), win)
            return

        if result is False:
            return

        win.accept()

    save_button = _button(win, "حفظ", submit, color=colors["success"], hover="#176c4b", width=100)
    cancel_button = _button(win, "إلغاء", win.reject, color="#6b7280", hover="#555e6b", width=100)
    footer.addWidget(save_button)
    footer.addWidget(cancel_button)
    root_layout.addLayout(footer)
    win.exec()
    return win


def _refresh_dashboard() -> None:
    if _dashboard_refresh:
        try:
            _dashboard_refresh()
        except Exception:
            pass


def _notify_action(success_message: str, action: Callable[[], Any],
                   refresh_resource=None, refresh_callback: Callable | None = None) -> bool:
    try:
        action()
    except Exception as exc:
        _message("error", "خطأ", str(exc), _root)
        return False
    _message("info", "تم", success_message, _root)
    _refresh_dashboard()
    if refresh_callback:
        refresh_callback()
    return True


def _open_entity_editor(resource: str, record_id=None, refresh_callback: Callable | None = None):
    fields = svc.FIELD_DEFS[resource]
    record = None
    if record_id is not None:
        record = svc.get_resource_record(resource, record_id)
        if not record:
            _message("error", "خطأ", "لم يتم العثور على السجل", _root)
            return
    title = ("إضافة " if record_id is None else "تعديل ") + svc.RESOURCE_CONFIG[resource]["title"]
    note = None
    if resource == "products":
        note = "الكميات لا تُعدّل من بطاقة المنتج؛ استخدم تسوية المخزون أو التحويل حتى يظل دفتر حركة المخزون هو المصدر الصحيح. الأسعار والمبالغ تُخزن بوحدة العملة الصغرى وفق المخطط. لون المنتج اختياري ويظهر على زر المنتج في صفحة الكاشير."
    elif resource == "users":
        note = "لا يتم عرض كلمة المرور المحفوظة. صيغة كلمات المرور الجديدة هنا PBKDF2-SHA256؛ تأكد أن خدمة تسجيل الدخول تستخدم verify_admin_password من Services.admin_service."
    elif resource == "warehouses":
        note = "يمكن تعيين مخزن افتراضي واحد فقط. لا يمكن تعطيل المخزن الافتراضي قبل تعيين بديل."
    elif resource == "settings":
        note = "تغيير المفاتيح المستخدمة في الحسابات يؤثر على ترحيل القيود. لا تغيّرها إلا إذا كنت تعرف أثرها."

    def save(values: dict) -> None:
        svc.save_entity(resource, values, record_id=record_id, user_id=svc.get_username_id(username))
        if refresh_callback:
            refresh_callback()
        _refresh_dashboard()
        _message("info", "تم", "تم حفظ البيانات بنجاح", _root)

    _prompt_form(title, fields, save, record=record, note=note)


class ResourceTableModel(QAbstractTableModel):
    """Read-only model for admin resources.

    Rows retain database column order even when the user visually rearranges
    columns in QTableView. This keeps action handlers (IDs/status fields) stable.
    """

    def __init__(self, columns: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._columns = [str(column) for column in columns]
        self._rows: list[tuple[Any, ...]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        try:
            value = self._rows[index.row()][index.column()]
        except IndexError:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.UserRole:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._columns):
                return self._columns[section]
            if orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_rows(self, rows: list[tuple[Any, ...]]):
        normalized = []
        column_count = len(self._columns)
        for row in rows:
            values = tuple(row[:column_count])
            if len(values) < column_count:
                values += (None,) * (column_count - len(values))
            normalized.append(values)

        self.beginResetModel()
        self._rows = normalized
        self.endResetModel()

    def record_at(self, row: int) -> list[Any] | None:
        if row < 0 or row >= len(self._rows):
            return None
        return list(self._rows[row])

    @staticmethod
    def _sort_key(value: Any):
        if value is None:
            return (3, "")
        if isinstance(value, bool):
            return (0, int(value))

        # Numeric database values should sort numerically, not lexicographically.
        try:
            from decimal import Decimal, InvalidOperation
            numeric = Decimal(str(value).replace(",", ""))
            if numeric.is_finite():
                return (0, numeric)
        except (InvalidOperation, ValueError, TypeError):
            pass

        if isinstance(value, (int, float)):
            return (0, value)
        return (1, str(value).casefold())

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        if not 0 <= column < len(self._columns):
            return
        reverse = order == Qt.SortOrder.DescendingOrder
        self.beginResetModel()
        self._rows.sort(key=lambda row: self._sort_key(row[column]), reverse=reverse)
        self.endResetModel()


def _selected_row(table: QTableView) -> list[Any] | None:
    """Return selected record values in original database order.

    Header drag-and-drop changes only visual positions, not logical model
    columns, so business actions continue to read the correct ID/status fields.
    """
    index = table.currentIndex()
    if not index.isValid() and table.selectionModel() is not None:
        selected_rows = table.selectionModel().selectedRows()
        if selected_rows:
            index = selected_rows[0]
    if not index.isValid():
        return None

    model = table.model()
    while hasattr(model, "mapToSource") and hasattr(model, "sourceModel"):
        index = model.mapToSource(index)
        model = model.sourceModel()

    if isinstance(model, ResourceTableModel):
        return model.record_at(index.row())

    # Defensive fallback for any future compatible model.
    if model is None:
        return None
    return [model.index(index.row(), column).data(Qt.ItemDataRole.UserRole)
            if model.index(index.row(), column).data(Qt.ItemDataRole.UserRole) is not None
            else model.index(index.row(), column).data(Qt.ItemDataRole.DisplayRole)
            for column in range(model.columnCount())]


def _open_audit_log_details(
    table: QTableView,
    parent: QWidget,
    columns: list[str],
):
    """Show audit/debt details, formatting JSON columns when present."""
    values = _selected_row(table)

    if not values:
        _message("warning", "تنبيه", "اختر سجلًا أولًا لعرض تفاصيله.", parent)
        return

    json_columns = {
        index
        for index, heading in enumerate(columns)
        if "JSON" in str(heading).upper()
    }

    is_debt_log = bool(json_columns)

    details = {}

    for index, heading in enumerate(columns):
        value = values[index] if index < len(values) else ""

        if index in json_columns and value:
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                pass

        details[str(heading)] = value

    title = (
        "تفاصيل سجل حركة الديون"
        if is_debt_log
        else "تفاصيل سجل التدقيق"
    )

    colors = _appearance_colors()

    win = QDialog(parent)
    win.setWindowTitle(title)
    win.resize(950, 700)
    win.setMinimumSize(650, 450)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setStyleSheet(
        f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}"
    )

    layout = QVBoxLayout(win)
    layout.addWidget(_label(title, win, size=20, bold=True))

    text_box = QPlainTextEdit(win)
    text_box.setFont(QFont("Consolas", 11))
    text_box.setPlainText(
        json.dumps(details, ensure_ascii=False, indent=2, default=str)
    )
    text_box.setReadOnly(True)

    layout.addWidget(text_box, 1)

    close_button = _button(
        win,
        "إغلاق",
        win.accept,
        color="#6b7280",
        hover="#555e6b",
        width=120,
    )

    layout.addWidget(close_button, 0, Qt.AlignHCenter)
    win.exec()


def _open_stock_adjustment(refresh: Callable[[], None]):
    fields = [
        {"name": "product_id", "label": "المنتج ID", "type": "int", "required": True},
        {"name": "warehouse_id", "label": "المخزن ID", "type": "int", "required": True},
        {"name": "movement_type", "label": "نوع الحركة", "required": True,
         "choice_values": _ENUM_CHOICES["movement_type"]},
        {"name": "quantity_change", "label": "تغير الكمية (+ إضافة / - سحب)", "type": "float", "required": True},
        {"name": "unit_cost", "label": "التكلفة بوحدة العملة الصغرى (اختياري)", "type": "int?"},
        {"name": "note", "label": "ملاحظة"},
    ]
    fields[0]["choice_values"] = svc.get_field_choices("product_id")
    fields[1]["choice_values"] = svc.get_field_choices("warehouse_id")

    def submit(values):
        product_id = int(values["product_id"])
        warehouse_id = int(values["warehouse_id"])
        qty = float(values["quantity_change"])
        unit_cost = int(values["unit_cost"]) if str(values.get("unit_cost", "")).strip() else None
        svc.add_stock_adjustment(product_id, warehouse_id, qty, str(values["movement_type"]),
                                 unit_cost, svc.get_username_id(username), values.get("note", ""))
        refresh()
        _refresh_dashboard()
        _message("info", "تم", "تم تسجيل حركة المخزون بنجاح", _root)

    _prompt_form("تسوية المخزون", fields, submit,
                 note="لا تغيّر الكمية مباشرة في جدول المنتجات. ستُضاف حركة جديدة إلى دفتر المخزون.")


def _open_transfer(refresh: Callable[[], None]):
    warehouses = [(x[0], x[1]) for x in svc.get_field_choices("warehouse_id")]
    products = [(x[0], x[1]) for x in svc.get_field_choices("product_id")]
    fields = [
        {"name": "from_warehouse_id", "label": "من المخزن ID", "type": "int", "required": True, "choice_values": warehouses},
        {"name": "to_warehouse_id", "label": "إلى المخزن ID", "type": "int", "required": True, "choice_values": warehouses},
        {"name": "product_id", "label": "المنتج ID", "type": "int", "required": True, "choice_values": products},
        {"name": "quantity", "label": "الكمية", "type": "float", "required": True},
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        transfer_id = svc.create_stock_transfer(
            int(values["from_warehouse_id"]), int(values["to_warehouse_id"]),
            [{"product_id": int(values["product_id"]), "quantity": float(values["quantity"])}],
            svc.get_username_id(username), values.get("note", ""),
        )
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم تسجيل التحويل وإضافة حركتي الصرف والإضافة. رقم السجل: {transfer_id}", _root)

    _prompt_form("تحويل بين المخازن", fields, submit,
                 note="يتم تسجيل التحويل وحركتي المخزون داخل معاملة واحدة. هذه الشاشة تنفذ تحويلًا لصنف واحد في كل مرة.")


def _open_sale_form(refresh: Callable[[], None]):
    fields = [
        {
            "name": "customer_id",
            "label": "العميل ID (فارغ للبيع النقدي)",
            "type": "int?",
            "choice_values": svc.get_field_choices("customer_id"),
        },
        {
            "name": "warehouse_id",
            "label": "المخزن ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("warehouse_id"),
        },
        {
            "name": "product_id",
            "label": "المنتج ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("product_id"),
        },
        {
            "name": "quantity",
            "label": "الكمية",
            "type": "float",
            "required": True,
        },
        {
            "name": "unit_price",
            "label": "سعر الوحدة بوحدة العملة الصغرى",
            "type": "int",
            "required": True,
        },
        {
            "name": "discount",
            "label": "خصم البند بوحدة العملة الصغرى",
            "type": "int",
            "default": "0",
        },
        {
            "name": "tax_rate_bp",
            "label": "نسبة الضريبة بالنقاط الأساسية (اتركها فارغة لاستخدام ضريبة المنتج)",
            "type": "int?",
        },
        {
            "name": "shift_id",
            "label": "الوردية المفتوحة ID (اختياري، لتسوية النقدية)",
            "type": "int?",
            "choice_values": svc.get_field_choices("shift_id"),
        },
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        current_user_id = svc.get_username_id(username)
        if current_user_id is None:
            raise ValueError("لا يمكن تحديد المستخدم الحالي من اسم الدخول")

        sale_id = svc.create_sale(
            customer_id=_optional_int(values, "customer_id"),
            warehouse_id=int(values["warehouse_id"]),
            product_id=int(values["product_id"]),
            quantity=float(values["quantity"]),
            unit_price=int(values["unit_price"]),
            discount=int(values.get("discount") or 0),
            tax_rate_bp=_optional_int(values, "tax_rate_bp"),
            cashier_id=current_user_id,
            shift_id=_optional_int(values, "shift_id"),
            note=values.get("note", ""),
            post=True,
        )

        refresh()
        _refresh_dashboard()
        _message(
            "info",
            "تم",
            f"تم تسجيل البيع وترحيل القيد. معرف البيع: {sale_id}",
            _root,
        )

    _prompt_form(
        "تسجيل عملية بيع",
        fields,
        submit,
        note=(
            "هذه النسخة تسجل بندًا واحدًا. البيع بعميل مسجل يُرحّل إلى حساب العملاء، "
            "والبيع النقدي بدون عميل يُرحّل إلى حساب النقدية. "
            "اختر الوردية المفتوحة عند الرغبة في إدراج البيع النقدي ضمن تسوية الخزينة. "
            "المبالغ بوحدة العملة الصغرى."
        ),
    )


def _open_purchase_order_form(refresh: Callable[[], None]):
    fields = [
        {"name": "supplier_id", "label": "المورد ID", "type": "int", "required": True, "choice_values": svc.get_field_choices("supplier_id")},
        {"name": "product_id", "label": "المنتج ID", "type": "int", "required": True, "choice_values": svc.get_field_choices("product_id")},
        {"name": "quantity", "label": "الكمية", "type": "float", "required": True},
        {"name": "unit_cost", "label": "تكلفة الوحدة بوحدة العملة الصغرى", "type": "int", "required": True},
        {"name": "expected_date", "label": "تاريخ التوقع YYYY-MM-DD"},
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        order_id = svc.create_purchase_order(
            int(values["supplier_id"]), int(values["product_id"]), float(values["quantity"]),
            int(values["unit_cost"]), svc.get_username_id(username),
            values.get("expected_date") or None, values.get("note", ""),
        )
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم إنشاء أمر الشراء كمسودة. المعرف: {order_id}", _root)

    _prompt_form("إنشاء أمر شراء", fields, submit,
                 note="أمر الشراء لا يزيد المخزون؛ يتم الاستلام عبر فاتورة الشراء المرحلة.")


def _open_sale_return_form(refresh: Callable[[], None]):
    fields = [
        {
            "name": "original_sale_id",
            "label": "فاتورة البيع الأصلية ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("original_sale_id"),
        },
        {
            "name": "product_id",
            "label": "المنتج ID الموجود بالفاتورة",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("product_id"),
        },
        {
            "name": "quantity",
            "label": "كمية المرتجع",
            "type": "float",
            "required": True,
        },
        {
            "name": "shift_id",
            "label": "الوردية المفتوحة ID (للمرتجع النقدي)",
            "type": "int?",
            "choice_values": svc.get_field_choices("shift_id"),
        },
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        current_user_id = svc.get_username_id(username)

        if current_user_id is None:
            raise ValueError("لا يمكن تحديد المستخدم الحالي من اسم الدخول")

        return_id = svc.create_sale_return(
            original_sale_id=int(values["original_sale_id"]),
            product_id=int(values["product_id"]),
            quantity=float(values["quantity"]),
            cashier_id=current_user_id,
            shift_id=_optional_int(values, "shift_id"),
            note=values.get("note", ""),
        )

        refresh()
        _refresh_dashboard()
        _message(
            "info",
            "تم",
            f"تم ترحيل مرتجع البيع. المعرف: {return_id}",
            _root,
        )

    _prompt_form(
        "مرتجع بيع",
        fields,
        submit,
        note=(
            "اختر فاتورة بيع مرحلة والمنتج المرتبط بها. "
            "يمنع النظام إرجاع كمية تتجاوز الكمية المباعة بعد المرتجعات السابقة. "
            "عند رد عملية بيع نقدية، اختر الوردية المناسبة حتى يظهر المرتجع "
            "في تسوية الخزينة."
        ),
    )


def _open_purchase_invoice_form(refresh: Callable[[], None]):
    fields = [
        {
            "name": "supplier_id",
            "label": "المورد ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("supplier_id"),
        },
        {
            "name": "warehouse_id",
            "label": "المخزن ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("warehouse_id"),
        },
        {
            "name": "product_id",
            "label": "المنتج ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("product_id"),
        },
        {
            "name": "quantity",
            "label": "الكمية",
            "type": "float",
            "required": True,
        },
        {
            "name": "unit_cost",
            "label": "تكلفة الوحدة بوحدة العملة الصغرى",
            "type": "int",
            "required": True,
        },
        {
            "name": "tax_rate_bp",
            "label": "نسبة الضريبة بالنقاط الأساسية (اتركها فارغة لاستخدام ضريبة المنتج)",
            "type": "int?",
        },
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        product_id = int(values["product_id"])

        entered_tax_rate = _optional_int(values, "tax_rate_bp")

        # An explicitly supplied value (including 0) overrides product tax.
        # An empty field uses the active tax rate configured on the product.
        effective_tax_rate = (
            entered_tax_rate
            if entered_tax_rate is not None
            else svc.get_product_tax_rate_bp(product_id)
        )

        if effective_tax_rate > 0:
            ok = _ask_yes_no(
                "تنبيه محاسبي",
                (
                    "دليل الحسابات الحالي لا يحتوي على حساب ضريبة مدخلات "
                    "قابلة للاسترداد. ستُضاف الضريبة إلى تكلفة المخزون في القيد.\n\n"
                    f"نسبة الضريبة: {effective_tax_rate / 100:.2f}%\n\n"
                    "هل تريد المتابعة؟"
                ),
                _root,
            )

            if not ok:
                return False

        invoice_id = svc.create_purchase_invoice(
            supplier_id=int(values["supplier_id"]),
            warehouse_id=int(values["warehouse_id"]),
            product_id=product_id,
            quantity=float(values["quantity"]),
            unit_cost=int(values["unit_cost"]),
            tax_rate_bp=effective_tax_rate,
            user_id=svc.get_username_id(username),
            note=values.get("note", ""),
            post=True,
        )

        refresh()
        _refresh_dashboard()

        _message(
            "info",
            "تم",
            f"تم ترحيل فاتورة الشراء وزيادة المخزون. المعرف: {invoice_id}",
            _root,
        )

    _prompt_form(
        "تسجيل فاتورة شراء",
        fields,
        submit,
        note=(
            "النسخة الحالية تدعم بندًا واحدًا فقط لكل عملية. "
            "ترحيل الفاتورة يزيد المخزون ويُنشئ قيدًا متوازنًا. "
            "إذا كانت ضريبة المدخلات قابلة للاسترداد، أضف حساب ضريبة مدخلات "
            "قبل استخدام هذا المسار."
        ),
    )


def _open_purchase_return_form(refresh: Callable[[], None]):
    fields = [
        {"name": "original_invoice_id", "label": "فاتورة الشراء الأصلية ID", "type": "int", "required": True, "choice_values": svc.get_field_choices("original_invoice_id")},
        {"name": "product_id", "label": "المنتج ID الموجود بالفاتورة", "type": "int", "required": True, "choice_values": svc.get_field_choices("product_id")},
        {"name": "quantity", "label": "كمية المرتجع", "type": "float", "required": True},
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        return_id = svc.create_purchase_return(
            int(values["original_invoice_id"]), int(values["product_id"]), float(values["quantity"]),
            svc.get_username_id(username), values.get("note", ""),
        )
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم ترحيل مرتجع الشراء. المعرف: {return_id}", _root)

    _prompt_form("مرتجع شراء", fields, submit,
                 note="يتحقق النظام من الكمية التي تم شراؤها سابقًا، ويخفض المخزون وينشئ قيدًا متوازنًا. ضريبة الشراء تُعامل ضمن تكلفة المخزون وفق مخطط الحسابات الحالي.")


def _open_payment_form(refresh: Callable[[], None]):
    fields = [
        {
            "name": "direction",
            "label": "الاتجاه",
            "required": True,
            "choice_values": [
                ("IN", "تحصيل من عميل"),
                ("OUT", "سداد لمورد"),
            ],
        },
        {
            "name": "partner_id",
            "label": "الشريك ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("partner_id"),
        },
        {
            "name": "method_id",
            "label": "طريقة الدفع ID",
            "type": "int",
            "required": True,
            "choice_values": svc.get_field_choices("method_id"),
        },
        {
            "name": "amount",
            "label": "المبلغ بوحدة العملة الصغرى",
            "type": "int",
            "required": True,
        },
        {
            "name": "shift_id",
            "label": "الوردية المفتوحة ID (اختياري)",
            "type": "int?",
            "choice_values": svc.get_field_choices("shift_id"),
        },
        {
            "name": "document_type",
            "label": "نوع المستند المراد التوزيع عليه (اختياري)",
            "choice_values": [
                ("SALE", "SALE"),
                ("PURCHASE_INVOICE", "PURCHASE_INVOICE"),
            ],
        },
        {
            "name": "document_id",
            "label": "معرف المستند (اتركه فارغًا للدفع غير الموزع)",
            "type": "int?",
        },
        {
            "name": "allocated_amount",
            "label": "المبلغ الموزع (اختياري)",
            "type": "int?",
        },
        {"name": "reference", "label": "مرجع التحويل/الإيصال"},
        {"name": "note", "label": "ملاحظة"},
    ]

    def submit(values):
        direction = str(values["direction"]).strip()
        partner_id = _optional_int(values, "partner_id")

        if partner_id is None:
            raise ValueError("يجب اختيار العميل أو المورد")

        document_type = str(values.get("document_type") or "").strip()
        document_id = _optional_int(values, "document_id")
        allocated_amount = _optional_int(values, "allocated_amount")

        allocations = []

        if document_id is not None:
            if not document_type:
                raise ValueError("اختر نوع المستند المراد التوزيع عليه")

            if allocated_amount is None:
                raise ValueError("أدخل مبلغ التوزيع عند تحديد مستند")

            if allocated_amount <= 0:
                raise ValueError("مبلغ التوزيع يجب أن يكون أكبر من صفر")

            expected_type = (
                "SALE" if direction == "IN" else "PURCHASE_INVOICE"
            )

            if document_type != expected_type:
                raise ValueError(
                    "نوع المستند لا يتوافق مع اتجاه الدفع. "
                    "التحصيل من العميل يكون على فواتير البيع، "
                    "والسداد للمورد يكون على فواتير الشراء."
                )

            allocations.append({
                "document_type": document_type,
                "document_id": document_id,
                "amount": allocated_amount,
            })

        elif document_type or allocated_amount is not None:
            raise ValueError(
                "أدخل معرف المستند أو اترك بيانات التوزيع فارغة"
            )

        payment_id = svc.record_payment(
            direction=direction,
            partner_id=partner_id,
            method_id=int(values["method_id"]),
            amount=int(values["amount"]),
            user_id=svc.get_username_id(username),
            allocations=allocations,
            shift_id=_optional_int(values, "shift_id"),
            reference=values.get("reference", ""),
            note=values.get("note", ""),
        )

        refresh()
        _refresh_dashboard()

        _message(
            "info",
            "تم",
            f"تم تسجيل الدفع وإنشاء القيد المحاسبي. المعرف: {payment_id}",
            _root,
        )

    _prompt_form(
        "تسجيل دفعة أو تحصيل",
        fields,
        submit,
        note=(
            "يجب ربط كل دفعة بعميل أو مورد. "
            "يمكن توزيع الدفع على مستند واحد في هذه الشاشة. "
            "أي مبلغ غير موزع يظل رصيدًا على حساب الشريك وفق منطق أرصدة النظام."
        ),
    )


def _open_expense_form(refresh: Callable[[], None]):
    fields = [
        {"name": "expense_date", "label": "تاريخ المصروف YYYY-MM-DD", "required": True, "default": date.today().isoformat()},
        {"name": "account_id", "label": "حساب المصروف ID", "type": "int", "required": True, "choice_values": svc.get_field_choices("account_id")},
        {"name": "method_id", "label": "طريقة الدفع ID", "type": "int", "required": True, "choice_values": svc.get_field_choices("method_id")},
        {"name": "amount", "label": "المبلغ بوحدة العملة الصغرى", "type": "int", "required": True},
        {"name": "partner_id", "label": "الشريك ID (اختياري)", "type": "int?", "choice_values": svc.get_field_choices("partner_id")},
        {"name": "shift_id", "label": "الوردية المفتوحة ID (اختياري)", "type": "int?", "choice_values": svc.get_field_choices("shift_id")},
        {"name": "description", "label": "الوصف"},
    ]

    def submit(values):
        expense_id = svc.record_expense(
            values["expense_date"], int(values["account_id"]), int(values["method_id"]),
            int(values["amount"]), svc.get_username_id(username), values.get("description", ""),
            int(values["partner_id"]) if values.get("partner_id") else None,
            int(values["shift_id"]) if values.get("shift_id") else None,
        )
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم تسجيل المصروف وإنشاء القيد. المعرف: {expense_id}", _root)

    _prompt_form("تسجيل مصروف", fields, submit,
                 note="اختر حسابًا من نوع EXPENSE وطريقة دفع مرتبطة بحساب أستاذ.")


def _open_journal_form(refresh: Callable[[], None]):
    accounts = [(x[0], x[1]) for x in svc.get_field_choices("account_id")]
    fields = [
        {"name": "entry_date", "label": "تاريخ القيد YYYY-MM-DD", "required": True, "default": date.today().isoformat()},
        {"name": "description", "label": "وصف القيد", "required": True},
        {"name": "debit_account", "label": "الحساب المدين ID", "type": "int", "required": True, "choice_values": accounts},
        {"name": "credit_account", "label": "الحساب الدائن ID", "type": "int", "required": True, "choice_values": accounts},
        {"name": "amount", "label": "المبلغ بوحدة العملة الصغرى", "type": "int", "required": True},
    ]

    def submit(values):
        debit_id = int(values["debit_account"])
        credit_id = int(values["credit_account"])
        if debit_id == credit_id:
            raise ValueError("اختر حسابين مختلفين")
        amount = int(values["amount"])
        if amount <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
        description = values["description"]
        entry_id = svc.create_manual_journal(
            values["entry_date"], description,
            [
                {"account_id": debit_id, "debit": amount, "credit": 0, "description": description},
                {"account_id": credit_id, "debit": 0, "credit": amount, "description": description},
            ], svc.get_username_id(username),
        )
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم إنشاء القيد المتوازن وترحيله. المعرف: {entry_id}", _root)

    _prompt_form("إنشاء قيد يومية متوازن", fields, submit,
                 note="هذا النموذج ينشئ قيدًا من سطر مدين وسطر دائن بالقيمة نفسها. القيود المرحلة غير قابلة للتعديل أو الحذف.")


def _open_payroll_form(refresh: Callable[[], None]):
    fields = [
        {"name": "period_start", "label": "بداية الفترة YYYY-MM-DD", "required": True, "default": date.today().replace(day=1).isoformat()},
        {"name": "period_end", "label": "نهاية الفترة YYYY-MM-DD", "required": True, "default": date.today().isoformat()},
    ]

    def submit(values):
        run_id = svc.create_payroll_draft(values["period_start"], values["period_end"], svc.get_username_id(username))
        refresh()
        _refresh_dashboard()
        _message("info", "تم", f"تم إنشاء مسودة رواتب تشمل الموظفين النشطين. المعرف: {run_id}", _root)

    _prompt_form("إنشاء مسودة مسير رواتب", fields, submit,
                 note="تنشأ قسائم أولية على أساس الأجر الأساسي فقط. لم يتم تفعيل ترحيل الرواتب أو الدفع آليًا لأن ذلك يتطلب سياسة خصومات/حضور وحسابات مقابلة محددة.")


def _open_role_permissions():
    colors = _appearance_colors()
    roles = svc.get_field_choices("role_id")
    if not roles:
        _message("error", "خطأ", "لا توجد أدوار", _root)
        return

    win = QDialog(_root)
    win.setWindowTitle("إدارة صلاحيات الأدوار")
    win.resize(600, 720)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setStyleSheet(f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}")
    layout = QVBoxLayout(win)
    layout.addWidget(_label("إدارة صلاحيات الدور", win, size=20, bold=True))
    role_combo = _style_combo(QComboBox(win))
    for role_id, name in roles:
        role_combo.addItem(f"{role_id} — {name}", role_id)
    layout.addWidget(role_combo)

    scroll = QScrollArea(win)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    check_body = QWidget()
    check_body.setStyleSheet(f"background: {colors['card']};")
    check_layout = QVBoxLayout(check_body)
    check_layout.setAlignment(Qt.AlignTop)
    scroll.setWidget(check_body)
    layout.addWidget(scroll, 1)
    state: dict[str, Any] = {"checks": [], "permission_ids": [], "role_id": None}

    def load_role(_index: int = 0):
        while check_layout.count():
            item = check_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        state["checks"].clear()
        state["permission_ids"].clear()
        role_id = role_combo.currentData()
        if role_id is None:
            return
        all_permissions, assigned, _role = svc.get_role_permissions(int(role_id))
        state["role_id"] = int(role_id)
        for permission_id, code, description in all_permissions:
            checkbox = QCheckBox(f"{code} — {description}", check_body)
            checkbox.setChecked(permission_id in assigned)
            checkbox.setLayoutDirection(Qt.RightToLeft)
            check_layout.addWidget(checkbox)
            state["checks"].append(checkbox)
            state["permission_ids"].append(permission_id)

    def save():
        if state["role_id"] is None:
            return
        selected = [pid for pid, checkbox in zip(state["permission_ids"], state["checks"]) if checkbox.isChecked()]
        try:
            svc.set_role_permissions(state["role_id"], selected, svc.get_username_id(username))
        except Exception as exc:
            _message("error", "خطأ", str(exc), win)
            return
        _message("info", "تم", "تم تحديث صلاحيات الدور", win)
        win.accept()

    role_combo.currentIndexChanged.connect(load_role)
    load_role()
    layout.addWidget(_button(win, "حفظ الصلاحيات", save, color=colors["success"], hover="#176c4b"))
    win.exec()


def _resource_action_buttons(resource: str, toolbar: QHBoxLayout,
                             refresh: Callable[[], None], table: QTableView):
    colors = _appearance_colors()

    def add_action(label: str, func: Callable):
        parent = toolbar.parentWidget() or _root

        toolbar.addWidget(
            _button(
                parent,
                label,
                func,
                color=colors["accent"],
                hover=colors["accent_hover"],
                height=34,
            )
        )

    if resource in {"debt_log", "audit_log"}:
        add_action("عرض تفاصيل السجل", lambda: _open_audit_log_details(table, table.window(), svc.RESOURCE_CONFIG[resource]["columns"]))
    elif resource == "stock_levels":
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
            fields = [
                {"name": "opening_cash", "label": "رصيد بداية الوردية بوحدة العملة الصغرى", "type": "int", "default": "0", "required": True},
                {"name": "note", "label": "ملاحظة"},
            ]

            def submit(values):
                svc.open_cash_shift(svc.get_username_id(username), int(values["opening_cash"]), values.get("note", ""))
                refresh()
                _refresh_dashboard()
                _message("info", "تم", "تم فتح الوردية", _root)

            _prompt_form("فتح وردية خزينة", fields, submit)

        def close_shift():
            values = _selected_row(table)
            if not values:
                _message("warning", "تنبيه", "اختر وردية أولًا", _root)
                return
            if len(values) <= 7 or str(values[7]) != "OPEN":
                _message("warning", "تنبيه", "الوردية المحددة ليست مفتوحة", _root)
                return
            fields = [{"name": "closing_cash", "label": "النقد الفعلي عند الإغلاق بوحدة العملة الصغرى", "type": "int", "required": True}]

            def submit(form_values):
                expected = svc.close_cash_shift(int(values[0]), int(form_values["closing_cash"]), svc.get_username_id(username))
                refresh()
                _refresh_dashboard()
                _message("info", "تم", f"تم إغلاق الوردية. النقد المتوقع من المدفوعات والمصروفات المسجلة: {expected}", _root)

            _prompt_form("إغلاق الوردية", fields, submit)

        add_action("فتح وردية", open_shift)
        add_action("إغلاق الوردية المحددة", close_shift)
    elif resource == "expenses":
        add_action("مصروف جديد", lambda: _open_expense_form(refresh))
    elif resource == "journal_entries":
        add_action("قيد يدوي متوازن", lambda: _open_journal_form(refresh))

        def reverse_selected_journal():
            values = _selected_row(table)
            if not values:
                _message("warning", "تنبيه", "اختر قيدًا أولًا", _root)
                return
            if len(values) <= 6 or str(values[6]) != "POSTED":
                _message("warning", "تنبيه", "اختر قيدًا مرحلًا وغير معكوس", _root)
                return
            fields = [{"name": "reason", "label": "سبب العكس", "required": True}]

            def submit(form_values):
                reversal_id = svc.reverse_manual_journal(int(values[0]), svc.get_username_id(username), form_values["reason"])
                refresh()
                _refresh_dashboard()
                _message("info", "تم", f"تم إنشاء قيد العكس رقم المعرف {reversal_id}", _root)

            _prompt_form("عكس قيد يومية يدوي", fields, submit,
                         note="يُنشأ قيد جديد بعكس المدين والدائن. لا يتم حذف أو تعديل بنود القيد الأصلي، ولا يمكن عكس القيود التشغيلية من هذه الشاشة.")

        add_action("عكس قيد يدوي", reverse_selected_journal)
    elif resource == "payroll_runs":
        add_action("مسودة رواتب", lambda: _open_payroll_form(refresh))
    elif resource == "roles":
        add_action("إدارة الصلاحيات", _open_role_permissions)


def open_resource_window(resource: str):
    cfg = svc.RESOURCE_CONFIG.get(resource)
    if not cfg:
        _message("error", "خطأ", "هذه الشاشة غير مسجلة", _root)
        return

    colors = _appearance_colors()
    win = QDialog(_root)
    win.setWindowTitle(cfg["title"])
    win.resize(1250, 720)
    win.setMinimumSize(850, 520)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setAttribute(Qt.WA_DeleteOnClose, True)
    win.setStyleSheet(f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}")
    _open_windows.append(win)
    win.destroyed.connect(lambda *_: _open_windows.remove(win) if win in _open_windows else None)

    root_layout = QVBoxLayout(win)
    header = QFrame(win)
    header.setStyleSheet(f"background: {colors['card']}; border-radius: 10px;")
    header_layout = QHBoxLayout(header)
    header_layout.addWidget(_label(cfg["title"], header, size=20, bold=True))
    root_layout.addWidget(header)

    toolbar_widget = QWidget(win)
    toolbar = QHBoxLayout(toolbar_widget)
    toolbar.setContentsMargins(0, 4, 0, 4)
    search_entry = _line_edit(toolbar_widget, placeholder="بحث...")
    search_entry.setFixedWidth(280)
    toolbar.addWidget(search_entry)
    count_label = _label("", toolbar_widget, color=colors["subtext"])
    toolbar.addWidget(count_label)
    toolbar.addWidget(_button(toolbar_widget, "تحديث", height=34, width=80))
    refresh_button = toolbar.itemAt(toolbar.count() - 1).widget()
    root_layout.addWidget(toolbar_widget)

    table_model = ResourceTableModel(cfg["columns"], win)
    table = QTableView(win)
    table.setModel(table_model)
    table.setLayoutDirection(Qt.RightToLeft)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setShowGrid(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(30)
    header_view = table.horizontalHeader()
    header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header_view.setSectionsMovable(True)
    header_view.setSectionsClickable(True)
    header_view.setHighlightSections(False)
    header_view.setStretchLastSection(False)
    header_view.setMinimumSectionSize(65)
    header_view.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    # Sorting is activated by an explicit header click so the service's
    # default ordering (for example newest sales first) is preserved initially.
    table.setSortingEnabled(False)
    header_view.setSortIndicatorShown(True)
    table.setStyleSheet(
        f"QTableView {{ background: {colors['card']}; color: {colors['text']}; "
        f"alternate-background-color: {colors['bg']}; gridline-color: {colors['border']}; "
        f"border: 0; selection-background-color: {colors['accent']}; selection-color: white; }}"
        f"QHeaderView::section {{ background: {colors['bg']}; color: {colors['text']}; "
        "padding: 7px; border: 0; font-weight: 600; }}"
        f"QTableCornerButton::section {{ background: {colors['bg']}; border: 0; }}"
    )
    for index, heading in enumerate(cfg["columns"]):
        table.setColumnWidth(index, min(260, max(90, len(str(heading)) * 11)))
    root_layout.addWidget(table, 1)

    # Keep each resource's column order and widths between application runs.
    header_settings = QSettings("MyShop", "MyShopERP")
    header_state_key = f"admin/resource_tables/{resource}/header_state"
    saved_header_state = header_settings.value(header_state_key)
    if saved_header_state is not None:
        header_view.restoreState(saved_header_state)

    def save_header_state(*_args):
        header_settings.setValue(header_state_key, header_view.saveState())

    header_view.sectionMoved.connect(save_header_state)
    header_view.sectionResized.connect(save_header_state)

    sort_state: dict[str, Any] = {"column": None, "order": Qt.SortOrder.AscendingOrder}

    def sort_from_header(logical_index: int):
        if sort_state["column"] == logical_index:
            sort_state["order"] = (
                Qt.SortOrder.DescendingOrder
                if sort_state["order"] == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            sort_state["column"] = logical_index
            sort_state["order"] = Qt.SortOrder.AscendingOrder

        header_view.setSortIndicator(logical_index, sort_state["order"])
        table_model.sort(logical_index, sort_state["order"])

    header_view.sectionClicked.connect(sort_from_header)

    def refresh():
        try:
            rows = svc.list_resource(resource, search_entry.text())
        except Exception as exc:
            _message("error", "خطأ في قراءة البيانات", str(exc), win)
            return
        table_model.set_rows(rows)
        if sort_state["column"] is not None:
            table_model.sort(int(sort_state["column"]), sort_state["order"])
        count_label.setText(f"عدد السجلات: {len(rows)}")

    refresh_button.clicked.connect(refresh)
    search_entry.returnPressed.connect(refresh)

    if cfg.get("editable"):
        add_button = _button(toolbar_widget, "إضافة", color=colors["success"], hover="#176c4b", width=90, height=34)
        toolbar.addWidget(add_button)
        add_button.clicked.connect(lambda: _open_entity_editor(resource, refresh_callback=refresh))

        def edit_selected():
            values = _selected_row(table)
            if not values:
                _message("warning", "تنبيه", "اختر سجلًا للتعديل", win)
                return
            _open_entity_editor(resource, _parse_record_id(resource, values[0]), refresh_callback=refresh)

        edit_button = _button(toolbar_widget, "تعديل", width=90, height=34)
        toolbar.addWidget(edit_button)
        edit_button.clicked.connect(edit_selected)

        if resource not in {"settings", "doc_sequences", "product_barcodes", "roles"}:
            def deactivate_selected():
                values = _selected_row(table)
                if not values:
                    _message("warning", "تنبيه", "اختر سجلًا أولًا", win)
                    return
                record_id = _parse_record_id(resource, values[0])
                if not _ask_yes_no("تأكيد", "هل تريد تعطيل هذا السجل؟ لن يتم حذفه من قاعدة البيانات.", win):
                    return
                try:
                    svc.deactivate_entity(resource, int(record_id), user_id=svc.get_username_id(username))
                    refresh()
                    _refresh_dashboard()
                except Exception as exc:
                    _message("error", "تعذر التعطيل", str(exc), win)

            deactivate_button = _button(toolbar_widget, "تعطيل", color=colors["danger"], hover="#a93226", width=90, height=34)
            toolbar.addWidget(deactivate_button)
            deactivate_button.clicked.connect(deactivate_selected)

    _resource_action_buttons(resource, toolbar, refresh, table)

    def handle_double_click(_index: QModelIndex):
        if resource in {"debt_log", "audit_log"}:
            _open_audit_log_details(table, win, cfg["columns"])
            return
        if cfg.get("editable"):
            values = _selected_row(table)
            if values:
                _open_entity_editor(resource, _parse_record_id(resource, values[0]), refresh_callback=refresh)

    table.doubleClicked.connect(handle_double_click)
    refresh()
    win.show()
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


def open_debt_log_page():
    """Open the full debt activity window for the admin."""
    return open_resource_window("debt_log")


def open_statistics_page():
    colors = _appearance_colors()
    win = QDialog(_root)
    win.setWindowTitle("التقارير والتدقيق")
    win.resize(520, 560)
    win.setLayoutDirection(Qt.RightToLeft)
    win.setStyleSheet(f"QDialog {{ background: {colors['bg']}; color: {colors['text']}; }}")
    layout = QVBoxLayout(win)
    layout.addWidget(_label("التقارير والتدقيق", win, size=20, bold=True))
    reports = [
        ("الأصناف منخفضة المخزون", "low_stock_products"),
        ("تقييم تقريبي للمخزون", "stock_valuation"),
        ("أرصدة العملاء", "customer_balances"),
        ("أرصدة الموردين", "supplier_balances"),
        ("القيود غير المتوازنة", "unbalanced_entries"),
        ("سجل التدقيق", "audit_log"),
    ]
    for label, resource in reports:
        layout.addWidget(_button(win, label, lambda _checked=False, r=resource: open_resource_window(r), height=42))
    layout.addWidget(_button(win, "إغلاق", win.accept, color="#6b7280", hover="#555e6b"))
    win.exec()


def open_sells_admin():
    return open_resource_window("sales")


def open_users_controll():
    return open_resource_window("users")


def open_admin(root: QWidget):
    """Build and mount the native PySide6 admin dashboard."""
    global _root, _dashboard_refresh
    _root = root
    colors = _appearance_colors()

    shell = QWidget()
    shell.setLayoutDirection(Qt.RightToLeft)
    shell.setStyleSheet(f"background: {colors['bg']}; color: {colors['text']};")
    shell_layout = QVBoxLayout(shell)
    shell_layout.setContentsMargins(0, 0, 0, 0)
    shell_layout.setSpacing(0)
    _install_page(root, shell)

    header = QFrame(shell)
    header.setFixedHeight(76)
    header.setStyleSheet(f"background: {colors['accent']};")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(24, 8, 24, 8)
    header_layout.addWidget(_label("لوحة تحكم MyShop ERP", header, size=23, bold=True, color="#ffffff"))
    header_layout.addStretch(1)
    header_layout.addWidget(_label(f"المستخدم: {username or 'غير معروف'}", header, size=12, color="#ffffff"))
    shell_layout.addWidget(header)

    body = QWidget(shell)
    body_layout = QHBoxLayout(body)
    body_layout.setContentsMargins(18, 16, 18, 16)
    body_layout.setSpacing(12)
    shell_layout.addWidget(body, 1)

    nav_area = QScrollArea(body)
    nav_area.setWidgetResizable(True)
    nav_area.setFixedWidth(300)
    nav_area.setFrameShape(QFrame.NoFrame)
    nav_widget = QWidget()
    nav_widget.setStyleSheet(f"background: {colors['card']}; border-radius: 10px;")
    nav_layout = QVBoxLayout(nav_widget)
    nav_layout.setContentsMargins(12, 12, 12, 12)
    nav_layout.setAlignment(Qt.AlignTop)
    nav_layout.addWidget(_label("الوحدات", nav_widget, size=18, bold=True))
    for group, resources in ADMIN_GROUPS:
        nav_layout.addWidget(_label(group, nav_widget, size=11, bold=True, color=colors["subtext"]))
        for label, resource in resources:
            button = QPushButton(label, nav_widget)
            button.setMinimumHeight(33)
            button.setCursor(Qt.PointingHandCursor)
            button.setLayoutDirection(Qt.RightToLeft)
            button.setStyleSheet(
                f"QPushButton {{ text-align: left; color: {colors['text']}; background: transparent; border: 0; padding: 5px 8px; }}"
                f"QPushButton:hover {{ background: {colors['border']}; border-radius: 5px; }}"
            )
            button.clicked.connect(lambda _checked=False, r=resource: open_resource_window(r))
            nav_layout.addWidget(button)
    nav_layout.addStretch(1)
    nav_area.setWidget(nav_widget)
    body_layout.addWidget(nav_area)

    content_area = QScrollArea(body)
    content_area.setWidgetResizable(True)
    content_area.setFrameShape(QFrame.NoFrame)
    content = QWidget()
    content.setStyleSheet("background: transparent;")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(6, 2, 6, 8)
    content_layout.setSpacing(10)
    content_layout.addWidget(_label("نظرة عامة", content, size=23, bold=True))
    content_layout.addWidget(_label(
        "اختر وحدة من القائمة للوصول إلى جداول النظام وإجراءاته. القيود والمخزون المرحل لا يُعدلان من جداول العرض مباشرة.",
        content, size=10, color=colors["subtext"], wrap=True,
    ))

    cards_frame = QWidget(content)
    cards_grid = QGridLayout(cards_frame)
    cards_grid.setContentsMargins(0, 0, 0, 0)
    cards_grid.setHorizontalSpacing(10)
    cards_grid.setVerticalSpacing(10)
    stats_config = [
        ("products", "المنتجات النشطة", "products"),
        ("stock_units", "إجمالي وحدات المخزون", "stock_levels"),
        ("low_stock", "أصناف منخفضة المخزون", "low_stock_products"),
        ("customers", "العملاء", "partners"),
        ("suppliers", "الموردون", "partners"),
        ("sales_today", "مبيعات اليوم (وحدة صغرى)", "sales"),
        ("receivables", "صافي أرصدة العملاء", "customer_balances"),
        ("payables", "صافي أرصدة الموردين", "supplier_balances"),
        ("employees", "الموظفون النشطون", "employees"),
        ("unbalanced", "قيود تحتاج مراجعة", "unbalanced_entries"),
    ]
    stat_labels: dict[str, QLabel] = {}
    for index, (key, title, resource) in enumerate(stats_config):
        card = QFrame(cards_frame)
        card.setStyleSheet(f"background: {colors['card']};  border-radius: 10px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.addWidget(_label(title, card, size=10, color=colors["subtext"], wrap=True))
        value_label = _label("—", card, size=21, bold=True, align=Qt.AlignHCenter | Qt.AlignVCenter)
        card_layout.addWidget(value_label)
        card_layout.addWidget(_button(card, "فتح", lambda _checked=False, r=resource: open_resource_window(r), height=28))
        stat_labels[key] = value_label
        cards_grid.addWidget(card, index // 3, 2 - (index % 3))
    for col in range(3):
        cards_grid.setColumnStretch(col, 1)
    content_layout.addWidget(cards_frame)

    quick = QFrame(content)
    quick.setStyleSheet(f"background: {colors['card']}; border-radius: 10px;")

    quick_layout = QVBoxLayout(quick)
    quick_layout.setContentsMargins(12, 10, 12, 12)
    quick_layout.setSpacing(10)

    quick_layout.addWidget(
        _label("إجراءات سريعة", quick, size=16, bold=True)
    )

    quick_row_widget = QWidget(quick)
    quick_row = QGridLayout(quick_row_widget)
    quick_row.setContentsMargins(0, 0, 0, 0)
    quick_row.setHorizontalSpacing(8)
    quick_row.setVerticalSpacing(8)

    quick_actions = [
        ("تسوية مخزون", lambda: _open_stock_adjustment(_refresh_dashboard)),
        ("تسجيل بيع", lambda: _open_sale_form(lambda: None)),
        ("فاتورة شراء", lambda: _open_purchase_invoice_form(lambda: None)),
        ("تسجيل دفعة", lambda: _open_payment_form(lambda: None)),
        ("تسجيل مصروف", lambda: _open_expense_form(lambda: None)),
        ("قيد يومية", lambda: _open_journal_form(lambda: None)),
        ("تصدير Excel", open_excel_export_window),
    ]

    for index, (label, command) in enumerate(quick_actions):
        quick_row.addWidget(
            _button(quick_row_widget, label, command, height=36),
            index // 4,
            index % 4,
        )

    for column in range(4):
        quick_row.setColumnStretch(column, 1)

    quick_layout.addWidget(quick_row_widget)
    content_layout.addWidget(quick)

    content_area.setWidget(content)
    body_layout.addWidget(content_area, 1)

    footer = QFrame(shell)
    footer.setFixedHeight(54)
    footer.setStyleSheet(f"background: {colors['card']};")
    footer_layout = QHBoxLayout(footer)
    footer_layout.setContentsMargins(12, 6, 12, 6)
    footer_layout.addWidget(_button(footer, "خروج", root.close, color=colors["danger"], hover="#a93226", width=100))
    footer_layout.addWidget(_button(footer, "تبديل المستخدم", lambda: go_login(root), color="#6b7280", hover="#555e6b", width=140))
    footer_layout.addStretch(1)
    footer_layout.addWidget(_label("MyShop ERP — MySQL 8", footer, color=colors["subtext"]))
    shell_layout.addWidget(footer)

    def refresh_dashboard():
        try:
            stats = svc.get_dashboard_stats()
            for key, label in stat_labels.items():
                value = stats.get(key, 0)
                label.setText(f"{value:,}" if isinstance(value, (int, float)) else str(value))
        except Exception as exc:
            _message("error", "تعذر تحميل الملخص", str(exc), root)

    _dashboard_refresh = refresh_dashboard
    refresh_dashboard()
    return shell
