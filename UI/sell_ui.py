"""Native PySide6 Arabic point-of-sale UI for the MyShop ERP schema.

All database operations are delegated to Services.cashier_service.  This
module uses PySide6 widgets, layouts, signals, dialogs, and item models
directly, without importing UI.qt_compat.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
import subprocess
import sys
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QScrollArea,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from Domain.debt import _DebtTableModel
from Domain.cart import _CartTableModel, _line_totals, _qty_text
from UI.common import is_dark
from Services.cashier_service import (
    add_customer_debt,
    close_cashier_shift,
    create_cashier_return,
    create_cashier_sale,
    export_cashier_sale_to_excel,
    get_cashier_session_folder,
    get_cashier_context,
    get_cashier_product_groups,
    get_cashier_products,
    search_cashier_products,
    get_debt_customers,
    get_open_shift,
    get_returnable_sales_items,
    get_username_id,
    minor_to_money,
    money_to_minor,
    open_cashier_shift,
    pay_customer_debt,
    remove_customer_debt,
    update_customer_debt,
)


WALK_IN_LABEL = "عميل نقدي"


def _valid_hex(color: Any) -> str | None:
    value = (color or "").strip()
    if len(value) == 7 and value[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in value[1:]):
        return value
    return None


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def _shade(color: str, factor: float) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(value * factor))) for value in _rgb(color))


def _text_on(color: str) -> str:
    red, green, blue = _rgb(color)
    return "#000000" if (0.299 * red + 0.587 * green + 0.114 * blue) > 150 else "#ffffff"


def _quantity(value: Any) -> Decimal:
    try:
        quantity = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        raise ValueError("أدخل كمية رقمية صحيحة") from None
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    return quantity





def _ui_palette(dark: bool) -> dict[str, str]:
    """Return the high-contrast color palette used by the cashier UI."""
    if dark:
        return {
            "background": "#0B1220", "surface": "#111B2E", "surface_alt": "#18263B",
            "input": "#0F1A2B", "border": "#2A3B55", "text": "#E8EEF7", "muted": "#A7B4C7",
            "primary": "#3478F6", "primary_hover": "#2864D8", "success": "#15966A",
            "success_hover": "#107A56", "danger": "#D94B5B", "danger_hover": "#BD3948",
            "warning": "#B7791F", "warning_hover": "#965F16", "info": "#326FC2",
            "info_hover": "#275A9E", "neutral": "#526176", "neutral_hover": "#405066",
            "selection": "#285AA8",
        }
    return {
        "background": "#F2F5F9", "surface": "#FFFFFF", "surface_alt": "#F7F9FC",
        "input": "#FBFCFE", "border": "#DCE4EE", "text": "#172033", "muted": "#66758A",
        "primary": "#2563EB", "primary_hover": "#1D4ED8", "success": "#13865B",
        "success_hover": "#0F704B", "danger": "#C83B4A", "danger_hover": "#AD2F3D",
        "warning": "#B7791F", "warning_hover": "#965F16", "info": "#2868B2",
        "info_hover": "#20558F", "neutral": "#64748B", "neutral_hover": "#526176",
        "selection": "#DCEBFF",
    }








def _configure_table_view(view: QTableView, palette: dict[str, str],
                          widths: tuple[int, ...]) -> None:
    """Configure a JavaFX-like table: draggable columns and user-resizable widths."""
    view.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setAlternatingRowColors(True)
    view.setShowGrid(True)
    view.setWordWrap(False)
    view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(36)

    header = view.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setSectionsMovable(True)
    header.setSectionsClickable(True)
    header.setHighlightSections(False)
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(55)
    header.setToolTip("اسحب عنوان العمود لتغيير ترتيبه، واسحب الحد الفاصل لتغيير عرضه.")

    for column, width in enumerate(widths):
        view.setColumnWidth(column, width)

    view.setStyleSheet(
        f"QTableView {{ background: {palette['surface']}; color: {palette['text']}; "
        f"gridline-color: {palette['border']}; border: 0; "
        f"selection-background-color: {palette['selection']}; }}"
        f"QTableView::item {{ padding: 5px; }}"
        f"QHeaderView::section {{ background: {palette['surface_alt']}; "
        f"color: {palette['text']}; padding: 8px; border: 0; "
        f"border-bottom: 1px solid {palette['border']}; font-weight: 600; }}"
    )

def _make_button(parent: QWidget, label: str, command: Callable | None = None,
                 kind: str = "neutral", palette: dict[str, str] | None = None,
                 width: int | None = None, height: int = 36,
                 font_size: int = 10) -> QPushButton:
    palette = palette or _ui_palette(is_dark())
    color_map = {
        "primary": (palette["primary"], palette["primary_hover"]),
        "success": (palette["success"], palette["success_hover"]),
        "danger": (palette["danger"], palette["danger_hover"]),
        "warning": (palette["warning"], palette["warning_hover"]),
        "info": (palette["info"], palette["info_hover"]),
        "neutral": (palette["neutral"], palette["neutral_hover"]),
    }
    foreground, hover = color_map.get(kind, color_map["neutral"])
    button = QPushButton(label, parent)
    button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(height)
    if width is not None:
        button.setFixedWidth(width)
    button.setFont(QFont("Segoe UI", font_size, QFont.Bold))
    button.setStyleSheet(
        "QPushButton {"
        f"background: {foreground}; color: #FFFFFF; border: 0; border-radius: 8px;"
        "padding: 5px 10px;"
        "}"
        f"QPushButton:hover {{ background: {hover}; }}"
        "QPushButton:disabled { background: #858b94; color: #e5e7eb; }"
    )
    if command is not None:
        button.clicked.connect(lambda _checked=False: command())
    return button


def _make_label(parent: QWidget, text: str, palette: dict[str, str],
                *, size: int = 10, bold: bool = False,
                color: str | None = None, wrap: bool = False,
                align: Qt.AlignmentFlag = Qt.AlignRight | Qt.AlignVCenter) -> QLabel:
    label = QLabel(text, parent)
    label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    # Let the label fill its layout cell so right alignment is visible.
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    label.setAlignment(align)
    label.setWordWrap(wrap)
    label.setFont(QFont("Segoe UI", size, QFont.Bold if bold else QFont.Normal))
    label.setStyleSheet(f"color: {color or palette['text']}; background: transparent;")
    return label


def _style_line_edit(edit: QLineEdit, palette: dict[str, str], *, height: int = 38,
                     align: Qt.AlignmentFlag = Qt.AlignLeft) -> QLineEdit:
    edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    edit.setMinimumHeight(height)
    edit.setAlignment(align)
    edit.setFont(QFont("Segoe UI", 10))
    edit.setStyleSheet(
        f"QLineEdit {{ background: {palette['input']}; color: {palette['text']}; "
        f"border: 1px solid {palette['border']}; border-radius: 8px; padding: 6px 9px; }}"
        f"QLineEdit:focus {{ border: 1px solid {palette['primary']}; }}"
    )
    return edit


def _style_combo(combo: QComboBox, palette: dict[str, str], height: int = 38) -> QComboBox:
    combo.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    combo.setMinimumHeight(height)
    combo.view().setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    combo.setStyleSheet(
        f"QComboBox {{ background: {palette['input']}; color: {palette['text']}; "
        f"border: 1px solid {palette['border']}; border-radius: 8px; padding: 5px 8px; }}"
        f"QComboBox QAbstractItemView {{ background: {palette['surface']}; color: {palette['text']}; "
        f"selection-background-color: {palette['selection']}; }}"
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
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(str(message))
    box.setIcon(QMessageBox.Question)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    return box.exec() == QMessageBox.Yes


def _clear_layout(layout: QVBoxLayout | QHBoxLayout | QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _clear_widget_contents(widget: QWidget) -> QVBoxLayout:
    layout = widget.layout()
    if layout is None:
        layout = QVBoxLayout(widget)
    else:
        _clear_layout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return layout  # type: ignore[return-value]


def _install_page(parent: QWidget, page: QWidget) -> None:
    if isinstance(parent, QMainWindow):
        if hasattr(parent, "set_page"):
            parent.set_page(page)
        else:
            parent.setCentralWidget(page)
        return
    layout = parent.layout()
    if layout is None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
    else:
        _clear_layout(layout)
    layout.addWidget(page)


def _new_dialog(parent: QWidget, title: str, palette: dict[str, str],
                size: tuple[int, int] | None = None) -> QDialog:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLayoutDirection(Qt.RightToLeft)
    dialog.setStyleSheet(f"QDialog {{ background: {palette['surface']}; color: {palette['text']}; }}")
    if size:
        dialog.resize(*size)
    dialog.setModal(True)
    return dialog


class _ColorSwatch(QLabel):
    """Small reusable product-color preview used only in quick product buttons."""

    def __init__(self, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {color};")


def build_sell_ui(parent: QWidget, username: str):
    """Mount the cashier screen into a QWidget or the supplied PySide6 main window."""
    if isinstance(parent, QMainWindow):
        page = QWidget()
        _install_page(parent, page)
    else:
        page = parent
        _clear_widget_contents(page)

    top = parent.window()
    try:
        cashier_id = get_username_id(str(username))
    except Exception as exc:
        _message("error", "تعذر فتح الكاشير", f"تعذر الوصول إلى حساب الكاشير:\n{type(exc).__name__}: {exc}", top)
        return False

    if cashier_id is None:
        _message("error", "خطأ تسجيل الدخول", f"لم يتم العثور على حساب مستخدم نشط باسم: {username}", top)
        return False

    dark = is_dark()
    palette = _ui_palette(dark)
    try:
        context = get_cashier_context(cashier_id)
    except Exception as exc:
        _message("error", "خطأ قاعدة البيانات", f"تعذر تحميل بيانات الكاشير:\n{type(exc).__name__}: {exc}", top)
        return False

    warehouses = context.get("warehouses", [])
    methods = context.get("payment_methods", [])
    if not warehouses:
        _message("error", "لا يوجد مخزن", "أضف مخزنًا نشطًا من صفحة الإدارة قبل البيع.", top)
        return False
    if not methods:
        _message("error", "لا توجد طرق دفع", "أضف طريقة دفع نشطة مرتبطة بحساب أستاذ نشط.", top)
        return False

    warehouse_labels = {f"{int(row[0])} — {row[1]}": int(row[0]) for row in warehouses}
    default_warehouse = next((row for row in warehouses if row[2]), warehouses[0])
    method_labels: dict[str, int] = {}
    for row in methods:
        label = f"{row[1]} ({row[2]})"
        if label in method_labels:
            label = f"{label} (#{int(row[0])})"
        method_labels[label] = int(row[0])

    customers = list(context.get("customers", []))
    customer_labels: dict[str, int | None] = {WALK_IN_LABEL: None}
    for customer_id, customer_name, phone in customers:
        label = f"{customer_name} — {phone}" if phone else str(customer_name)
        if label in customer_labels:
            label = f"{label} (#{customer_id})"
        customer_labels[label] = int(customer_id)

    initial_shift = context.get("open_shift")
    last_shift = context.get("last_shift")
    remembered_shift = initial_shift or last_shift
    current_shift: dict[str, Any] = {
        "row": initial_shift,
        "last_id": int(remembered_shift[0]) if remembered_shift else None,
    }
    cart: dict[int, dict[str, Any]] = {}

    # ---------------- page and header ----------------
    page.setLayoutDirection(Qt.RightToLeft)
    page.setStyleSheet(f"background: {palette['background']}; color: {palette['text']};")
    root_layout = page.layout()
    if root_layout is None:
        root_layout = QVBoxLayout(page)
    root_layout.setContentsMargins(14, 14, 14, 14)
    root_layout.setSpacing(12)

    main = QWidget(page)
    main.setLayoutDirection(Qt.RightToLeft)
    main_layout = QVBoxLayout(main)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(12)
    root_layout.addWidget(main)

    toolbar = QFrame(main)
    toolbar.setStyleSheet(f"background: {palette['surface']}; border-radius: 14px;")
    toolbar_layout = QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(18, 10, 18, 10)
    toolbar_layout.setSpacing(9)

    title_block = QWidget(toolbar)
    title_layout = QVBoxLayout(title_block)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(1)
    title_layout.addWidget(_make_label(title_block, "نقطة البيع", palette, size=19, bold=True))
    title_layout.addWidget(_make_label(title_block, "إدارة المبيعات والفواتير", palette, size=9, color=palette["muted"]))
    toolbar_layout.addWidget(title_block)
    toolbar_layout.addWidget(_make_label(toolbar, "المخزن", palette, size=10, bold=True))

    warehouse_menu = _style_combo(QComboBox(toolbar), palette, 36)
    for row in warehouses:
        warehouse_menu.addItem(f"{int(row[0])} — {row[1]}", int(row[0]))
    default_index = warehouse_menu.findData(int(default_warehouse[0]))
    if default_index >= 0:
        warehouse_menu.setCurrentIndex(default_index)
    warehouse_menu.setMinimumWidth(190)
    toolbar_layout.addWidget(warehouse_menu)
    toolbar_layout.addStretch(1)

    shift_status_frame = QFrame(toolbar)
    shift_status_frame.setStyleSheet(f"background: {palette['surface_alt']}; border-radius: 9px;")
    shift_status_layout = QHBoxLayout(shift_status_frame)
    shift_status_layout.setContentsMargins(10, 7, 10, 7)
    shift_text_label = _make_label(shift_status_frame, "جاري تحميل حالة الوردية...", palette, size=9, bold=True, color=palette["muted"])
    shift_status_layout.addWidget(shift_text_label)
    toolbar_layout.addWidget(shift_status_frame)
    shift_button = _make_button(toolbar, "بدء الوردية", kind="success", palette=palette, width=128, height=38)
    toolbar_layout.addWidget(shift_button)
    main_layout.addWidget(toolbar)

    # ---------------- three-column work area ----------------
    content = QWidget(main)
    content.setLayoutDirection(Qt.RightToLeft)
    content_layout = QHBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(8)
    main_layout.addWidget(content, 1)

    # Checkout panel is the right-most panel in the RTL layout.
    controls = QFrame(content)
    controls.setObjectName("checkoutPanel")
    controls.setFixedWidth(250)
    controls.setStyleSheet(f"""
        QFrame#checkoutPanel {{
            background-color: {palette['surface']};
            border: none;
            border-radius: 18px;
        }}
    """)
    controls_layout = QVBoxLayout(controls)
    controls_layout.setContentsMargins(0, 0, 0, 0)
    controls_scroll = QScrollArea(controls)
    controls_scroll.setWidgetResizable(True)
    controls_scroll.setFrameShape(QFrame.NoFrame)
    controls_scroll.setStyleSheet("""
        QScrollArea {
            background: transparent;
            border: none;
        }
    """)

    controls_scroll.viewport().setStyleSheet("""
        background: transparent;
    """)
    controls_body = QWidget()
    controls_body.setStyleSheet("background: transparent;")
    controls_body.setLayoutDirection(Qt.RightToLeft)
    controls_body_layout = QVBoxLayout(controls_body)
    controls_body_layout.setContentsMargins(8, 8, 8, 8)
    controls_body_layout.setSpacing(5)
    controls_scroll.setWidget(controls_body)
    controls_layout.addWidget(controls_scroll)
    content_layout.addWidget(controls)

    center = QFrame(content)
    center.setStyleSheet(f"background: {palette['surface']}; border-radius: 14px;")
    center_layout = QVBoxLayout(center)
    center_layout.setContentsMargins(12, 12, 12, 12)
    center_layout.setSpacing(7)
    content_layout.addWidget(center, 1)

    quick = QFrame(content)
    quick.setFixedWidth(270)
    quick.setStyleSheet(f"background: {palette['surface']}; border-radius: 14px;")
    quick_layout = QVBoxLayout(quick)
    quick_layout.setContentsMargins(10, 12, 10, 8)
    quick_layout.setSpacing(4)
    quick_layout.addWidget(_make_label(quick, "الأصناف السريعة", palette,align=Qt.AlignmentFlag.AlignLeft , size=14, bold=True))
    quick_layout.addWidget(_make_label(quick, "اختر الصنف لإضافته إلى السلة", palette, align=Qt.AlignmentFlag.AlignLeft, size=9, color=palette["muted"]))
    separator = QFrame(quick)
    separator.setFixedHeight(1)
    separator.setStyleSheet(f"background: {palette['border']};")
    quick_layout.addWidget(separator)
    quick_scroll = QScrollArea(quick)
    quick_scroll.setWidgetResizable(True)
    quick_scroll.setFrameShape(QFrame.NoFrame)
    quick_content = QWidget()
    quick_content.setLayoutDirection(Qt.RightToLeft)
    quick_content_layout = QVBoxLayout(quick_content)
    quick_content_layout.setContentsMargins(2, 2, 2, 2)
    quick_content_layout.setSpacing(4)
    quick_content_layout.setAlignment(Qt.AlignTop)
    quick_scroll.setWidget(quick_content)
    quick_layout.addWidget(quick_scroll, 1)
    content_layout.addWidget(quick)

    # ---------------- center/cart panel ----------------
    center_header = QWidget(center)
    center_header_layout = QHBoxLayout(center_header)
    center_header_layout.setContentsMargins(3, 0, 3, 0)
    center_header_layout.addWidget(_make_label(center_header, "سلة المشتريات", palette, size=15, bold=True))
    center_header_layout.addStretch(1)
    center_header_layout.addWidget(_make_label(center_header, "أضف المنتجات وراجع الكميات قبل إتمام البيع", palette, size=9, color=palette["muted"]))
    center_layout.addWidget(center_header)

    search_frame = QWidget(center)
    search_layout = QHBoxLayout(search_frame)
    search_layout.setContentsMargins(0, 0, 0, 0)
    search_entry = _style_line_edit(QLineEdit(search_frame), palette, height=42)
    search_entry.setPlaceholderText("امسح الباركود أو ابحث باسم المنتج / SKU")
    search_entry.setFont(QFont("Segoe UI", 11))
    search_layout.addWidget(search_entry, 1)
    add_button = _make_button(search_frame, "بحث عن صنف", kind="primary", palette=palette, width=112, height=42)
    search_layout.addWidget(add_button)
    center_layout.addWidget(search_frame)

    tree = QTableView(center)
    cart_model = _CartTableModel(cart, tree)
    tree.setModel(cart_model)
    _configure_table_view(tree, palette, (190, 105, 95, 75, 105, 75))
    center_layout.addWidget(tree, 1)

    cart_actions = QWidget(center)
    cart_actions_layout = QHBoxLayout(cart_actions)
    cart_actions_layout.setContentsMargins(0, 0, 0, 0)
    cart_actions_layout.addWidget(_make_button(cart_actions, "زيادة الكمية +", kind="neutral", palette=palette, width=118, height=34))
    increase_button = cart_actions_layout.itemAt(cart_actions_layout.count() - 1).widget()
    cart_actions_layout.addWidget(_make_button(cart_actions, "تقليل الكمية −", kind="neutral", palette=palette, width=118, height=34))
    decrease_button = cart_actions_layout.itemAt(cart_actions_layout.count() - 1).widget()
    cart_actions_layout.addStretch(1)
    remove_button = _make_button(cart_actions, "حذف الصنف", kind="danger", palette=palette, width=100, height=34)
    clear_button = _make_button(cart_actions, "تفريغ السلة", kind="neutral", palette=palette, width=100, height=34)
    cart_actions_layout.addWidget(remove_button)
    cart_actions_layout.addWidget(clear_button)
    center_layout.addWidget(cart_actions)

    # ---------------- checkout controls ----------------
    controls_body_layout.addWidget(_make_label(controls_body, "إتمام البيع", palette, align=Qt.AlignmentFlag.AlignLeft ,size=16, bold=True))
    controls_body_layout.addWidget(_make_label(controls_body, "العميل", palette, align=Qt.AlignmentFlag.AlignLeft ,size=10, bold=True))
    customer_menu = _style_combo(QComboBox(controls_body), palette)

    def rebuild_customer_combo(select_label: str = WALK_IN_LABEL):
        customer_menu.clear()
        customer_menu.addItem(WALK_IN_LABEL, None)
        for customer_id, customer_name, phone in customers:
            label = f"{customer_name} — {phone}" if phone else str(customer_name)
            if label in [customer_menu.itemText(i) for i in range(customer_menu.count())]:
                label = f"{label} (#{customer_id})"
            customer_menu.addItem(label, int(customer_id))
        target = customer_menu.findText(select_label)
        customer_menu.setCurrentIndex(target if target >= 0 else 0)

    rebuild_customer_combo()
    controls_body_layout.addWidget(customer_menu)

    customer_mode_row = QWidget(controls_body)
    customer_mode_layout = QHBoxLayout(customer_mode_row)
    customer_mode_layout.setContentsMargins(0, 2, 0, 2)
    new_customer_check = QCheckBox("تسجيل عميل جديد", customer_mode_row)
    new_customer_check.setLayoutDirection(Qt.RightToLeft)
    new_customer_check.setFont(QFont("Segoe UI", 10, QFont.Bold))
    new_customer_check.setStyleSheet(f"color: {palette['text']};")
    customer_mode_layout.addWidget(new_customer_check)
    customer_mode_layout.addStretch(1)
    controls_body_layout.addWidget(customer_mode_row)

    new_customer_frame = QFrame(controls_body)
    new_customer_frame.setStyleSheet(f"background: {palette['surface_alt']}; border-radius: 10px;")
    new_customer_layout = QVBoxLayout(new_customer_frame)
    new_customer_layout.setContentsMargins(11, 9, 11, 9)
    new_customer_layout.setSpacing(4)
    new_customer_layout.addWidget(_make_label(new_customer_frame, "اسم العميل *", palette, align=Qt.AlignmentFlag.AlignLeft , size=10, bold=True))
    new_customer_name = _style_line_edit(QLineEdit(new_customer_frame), palette, height=37)
    new_customer_name.setPlaceholderText("اكتب اسم العميل")
    new_customer_layout.addWidget(new_customer_name)
    new_customer_layout.addWidget(_make_label(new_customer_frame, "رقم الهاتف (اختياري)", palette, align=Qt.AlignmentFlag.AlignLeft , size=10, bold=True))
    new_customer_phone = _style_line_edit(QLineEdit(new_customer_frame), palette, height=37)
    new_customer_phone.setPlaceholderText("اكتب رقم الهاتف")
    new_customer_layout.addWidget(new_customer_phone)
    controls_body_layout.addWidget(new_customer_frame)
    new_customer_frame.hide()

    payment_label = _make_label(controls_body, "طريقة الدفع", palette, align=Qt.AlignmentFlag.AlignLeft ,size=10, bold=True)
    controls_body_layout.addWidget(payment_label)
    payment_menu = _style_combo(QComboBox(controls_body), palette)
    for method_label, method_id in method_labels.items():
        payment_menu.addItem(method_label, method_id)
    controls_body_layout.addWidget(payment_menu)

    controls_body_layout.addWidget(_make_label(controls_body, "المبلغ المدفوع", palette, align=Qt.AlignmentFlag.AlignLeft ,size=10, bold=True))
    paid_entry = _style_line_edit(QLineEdit(controls_body), palette, height=38, align=Qt.AlignCenter)
    paid_entry.setText("0")
    paid_entry.setFont(QFont("Segoe UI", 12, QFont.Bold))
    controls_body_layout.addWidget(paid_entry)
    controls_body_layout.addWidget(_make_label(controls_body, "بالوحدة النقدية الرئيسية؛ المبالغ تحفظ كوحدات صغرى.", palette, size=9, color=palette["muted"], wrap=True))

    summary_card = QFrame(controls_body)
    summary_card.setStyleSheet(f"background: {palette['surface_alt']}; border-radius: 11px;")
    summary_layout = QVBoxLayout(summary_card)
    summary_layout.setContentsMargins(13, 10, 13, 10)
    summary_layout.addWidget(_make_label(summary_card, "إجمالي الفاتورة", palette, align=Qt.AlignmentFlag.AlignLeft ,size=10, bold=True, color=palette["muted"]))
    total_label = _make_label(summary_card, minor_to_money(0), palette, size=23, bold=True,
                              color="#48D6A0" if dark else palette["success"])
    summary_layout.addWidget(total_label)
    controls_body_layout.addWidget(summary_card)

    # ---------------- cashier behavior ----------------
    def is_credit_customer() -> bool:
        return new_customer_check.isChecked() or customer_menu.currentData() is not None

    def current_warehouse_id() -> int:
        value = warehouse_menu.currentData()
        if value is None:
            raise ValueError("اختر مخزنًا صحيحًا")
        return int(value)

    def current_total_minor() -> int:
        total = 0
        for entry in cart.values():
            _base, _tax, line_total = _line_totals(entry["product"], entry["quantity"])
            total += line_total
        return total

    def check_stock(product: tuple, wanted_qty: Decimal) -> None:
        """Raise ValueError when a stock-tracked product lacks the requested quantity."""
        try:
            tracked = bool(product[7])
            available = Decimal(str(product[5]))
        except (IndexError, InvalidOperation, TypeError):
            return
        if tracked and wanted_qty > available:
            raise ValueError(
                f"الكمية المطلوبة ({_qty_text(wanted_qty)}) أكبر من "
                f"المتاح في المخزن ({_qty_text(available)}) للصنف: {product[1]}"
            )

    def refresh_customer_mode(reset_payment: bool = False):
        if new_customer_check.isChecked():
            customer_menu.setEnabled(False)
            new_customer_frame.show()
        else:
            customer_menu.setEnabled(True)
            new_customer_frame.hide()
        if not is_credit_customer():
            paid_entry.setText(minor_to_money(current_total_minor()))
        elif reset_payment or not paid_entry.text().strip():
            paid_entry.setText(minor_to_money(0))

    def repaint_cart():
        selected_pid = selected_product_id()
        cart_model.refresh()
        total = current_total_minor()
        total_label.setText(minor_to_money(total))
        if not is_credit_customer():
            paid_entry.setText(minor_to_money(total))
        elif not paid_entry.text().strip():
            paid_entry.setText(minor_to_money(0))
        if selected_pid is not None:
            row_index = cart_model.row_for_product(selected_pid)
            if row_index >= 0:
                index = cart_model.index(row_index, 0)
                tree.setCurrentIndex(index)
                tree.selectRow(row_index)

    def selected_product_id() -> int | None:
        index = tree.currentIndex()
        if not index.isValid():
            return None
        product_id = cart_model.product_id_at(index.row())
        return product_id if product_id in cart else None

    def ask_product_quantity(product: tuple, on_confirm: Callable | None = None):
        dialog = _new_dialog(top, "تحديد الكمية", palette, (360, 220))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(_make_label(dialog, f"المنتج: {product[1]}", palette, size=13, bold=True, wrap=True))
        layout.addWidget(_make_label(dialog, "أدخل الكمية المطلوبة:", palette, size=12))
        quantity_entry = _style_line_edit(QLineEdit(dialog), palette, height=38, align=Qt.AlignCenter)
        quantity_entry.setText("1")
        layout.addWidget(quantity_entry)
        buttons = QHBoxLayout()
        add_to_cart_button = _make_button(dialog, "إضافة للسلة", kind="primary", palette=palette)
        cancel_button = _make_button(dialog, "إلغاء", kind="neutral", palette=palette)
        buttons.addWidget(add_to_cart_button)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        def confirm_quantity():
            try:
                quantity = _quantity(quantity_entry.text())
            except ValueError as exc:
                _message("error", "كمية غير صحيحة", str(exc), dialog)
                quantity_entry.setFocus()
                return
            dialog.accept()
            if on_confirm is not None:
                on_confirm(product, _qty_text(quantity))
            else:
                add_product_to_cart(product, _qty_text(quantity))

        add_to_cart_button.clicked.connect(confirm_quantity)
        cancel_button.clicked.connect(dialog.reject)
        quantity_entry.returnPressed.connect(confirm_quantity)
        dialog.exec()

    def add_product_to_cart(product: tuple, raw_qty: Any = "1"):
        try:
            quantity = _quantity(raw_qty)
            product_id = int(product[0])
            existing = cart[product_id]["quantity"] if product_id in cart else Decimal(0)
            check_stock(product, existing + quantity)
        except ValueError as exc:
            _message("error", "تعذر الإضافة", str(exc), top)
            return
        if product_id in cart:
            cart[product_id]["quantity"] += quantity
            cart[product_id]["product"] = product
        else:
            cart[product_id] = {"product": product, "quantity": quantity}
        repaint_cart()
        search_entry.clear()
        search_entry.setFocus()

    def show_product_search_dialog(primary: tuple | None, related: list[tuple]):
        """Show the closest product (when one exists) and its name-related products."""
        total_results = len(related) + (1 if primary is not None else 0)
        picker = _new_dialog(top, "نتائج البحث عن صنف", palette, (640, 500))
        layout = QVBoxLayout(picker)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        if primary is not None:
            heading_text = "تم العثور على أقرب صنف مطابق"
        else:
            heading_text = f"أصناف ذات صلة بالبحث ({total_results})"
        layout.addWidget(_make_label(picker, heading_text, palette, size=15, bold=True))

        scroll = QScrollArea(picker)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QWidget()
        body.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(2, 2, 2, 2)
        body_layout.setSpacing(7)
        body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        def add_product_option(product: tuple, *, closest: bool = False) -> None:
            product_name = str(product[1] or "بدون اسم")
            code = str(product[3] or product[2] or "—")
            stock = float(product[5] or 0) if len(product) > 5 else 0.0
            label = (
                f"{product_name}   |   {code}   |   "
                f"{minor_to_money(product[4])}   |   المخزون: {stock:g}"
            )
            button = _make_button(
                body,
                label,
                kind="success" if closest else "neutral",
                palette=palette,
                height=48,
                font_size=10,
            )
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(
                button.styleSheet()
                + " QPushButton { text-align: right; padding-right: 12px; }"
            )
            button.clicked.connect(
                lambda _checked=False, selected=product: select_from_picker(selected)
            )
            body_layout.addWidget(button)

        def select_from_picker(product: tuple) -> None:
            picker.accept()
            ask_product_quantity(product)

        if primary is not None:
            body_layout.addWidget(_make_label(body, "الصنف الأقرب", palette, size=11, bold=True))
            add_product_option(primary, closest=True)

        if related:
            related_heading = "أصناف مشابهة في الاسم" if primary is not None else "الأصناف ذات الصلة"
            body_layout.addWidget(_make_label(body, related_heading, palette, size=11, bold=True))
            for product in related:
                add_product_option(product)
        elif primary is not None:
            body_layout.addWidget(
                _make_label(body, "لا توجد أصناف أخرى بأسماء مشابهة.", palette, size=9, color=palette["muted"])
            )

        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        cancel_button = _make_button(picker, "إغلاق", kind="neutral", palette=palette, width=100)
        cancel_button.clicked.connect(picker.reject)
        layout.addWidget(cancel_button, 0, Qt.AlignmentFlag.AlignLeft)
        picker.exec()

    def search_and_add():
        value = search_entry.text().strip()
        if not value:
            return
        try:
            primary, related = search_cashier_products(value, current_warehouse_id())
        except Exception as exc:
            _message("error", "خطأ في البحث", str(exc), top)
            return

        if primary is None and not related:
            _message("warning", "غير موجود", "لم يتم العثور على صنف مطابق أو أصناف قريبة من الاسم المدخل.", top)
            return

        show_product_search_dialog(primary, related)

    def change_selected_qty(delta: int):
        product_id = selected_product_id()
        if product_id is None:
            return
        new_quantity = cart[product_id]["quantity"] + Decimal(delta)
        if new_quantity <= 0:
            cart.pop(product_id, None)
        else:
            if delta > 0:
                try:
                    check_stock(cart[product_id]["product"], new_quantity)
                except ValueError as exc:
                    _message("error", "تعذر زيادة الكمية", str(exc), top)
                    return
            cart[product_id]["quantity"] = new_quantity
        repaint_cart()

    def remove_selected():
        product_id = selected_product_id()
        if product_id is not None:
            cart.pop(product_id, None)
            repaint_cart()

    def clear_cart():
        cart.clear()
        repaint_cart()

    def customer_id_from_form():
        if new_customer_check.isChecked():
            name = new_customer_name.text().strip()
            if not name:
                raise ValueError("أدخل اسم العميل الجديد")
            return None, name, new_customer_phone.text().strip() or None
        selected_id = customer_menu.currentData()
        if customer_menu.currentIndex() < 0:
            raise ValueError("اختر عميلًا صحيحًا")
        return (int(selected_id) if selected_id is not None else None), None, None

    def refresh_customers():
        nonlocal customers, customer_labels
        try:
            fresh = get_cashier_context(cashier_id)
            customers = list(fresh["customers"])
            old_label = customer_menu.currentText()
            customer_labels = {WALK_IN_LABEL: None}
            for customer_id, customer_name, phone in customers:
                label = f"{customer_name} — {phone}" if phone else str(customer_name)
                if label in customer_labels:
                    label = f"{label} (#{customer_id})"
                customer_labels[label] = int(customer_id)
            rebuild_customer_combo(old_label)
            refresh_customer_mode()
        except Exception as exc:
            _message("error", "خطأ", str(exc), top)

    quick_access_state = {"warehouse_id": None, "built": False}

    def build_quick_access(force: bool = False):
        warehouse_id = current_warehouse_id()
        if (not force and quick_access_state["built"] and quick_access_state["warehouse_id"] == warehouse_id):
            return
        _clear_layout(quick_content_layout)
        try:
            groups, ungrouped = get_cashier_product_groups(warehouse_id)
            groups = list(groups)
        except Exception as exc:
            message = _make_label(quick_content, f"تعذر تحميل الأصناف:\n{exc}", palette, size=9, color=palette["danger"], wrap=True)
            quick_content_layout.addWidget(message)
            quick_access_state["built"] = False
            return
        if ungrouped:
            groups.append(("بدون قسم", ungrouped))

        paper_labels = {"normal": "عادي", "glossy": "لامع", "sticker": "استيكر", "double glossy": "لامع مزدوج"}
        color_labels = {"colorful": "ألوان", "black and white": "أبيض/أسود"}

        def compact_product_label(product):
            full_name = str(product[1] or "")
            path = str(product[12] or "") if len(product) > 12 else ""
            parts = [part.strip() for part in path.split(" / ") if part.strip()]
            details = full_name.split("|", 1)[1].strip() if "|" in full_name else full_name
            if len(parts) >= 2:
                details = details.replace(f" {parts[1]}", "", 1)
            if len(parts) >= 3:
                details = details.replace(f" - {parts[2]}", "", 1)
            if len(parts) >= 4:
                details = details.removesuffix(f" - {parts[3]}")
            paper = " ".join(details.strip(" -").split())
            paper_label = paper_labels.get(paper.casefold(), paper or "منتج")
            mode = parts[3].casefold() if len(parts) >= 4 else ""
            mode_label = color_labels.get(mode, mode)
            return f"{paper_label} · {mode_label}" if mode_label else paper_label

        for section_name, products in groups:
            group_frame = QWidget(quick_content)
            group_layout = QVBoxLayout(group_frame)
            group_layout.setContentsMargins(1, 3, 1, 2)
            group_layout.setSpacing(3)
            group_layout.addWidget(_make_label(group_frame, section_name, palette, size=10, bold=True))
            products_frame = QWidget(group_frame)
            products_grid = QGridLayout(products_frame)
            products_grid.setContentsMargins(0, 0, 0, 0)
            products_grid.setHorizontalSpacing(4)
            products_grid.setVerticalSpacing(4)
            products_grid.setColumnStretch(0, 1)
            products_grid.setColumnStretch(1, 1)
            for index, product in enumerate(products):
                button_text = f"{compact_product_label(product)}\n{minor_to_money(product[4])}"
                color = _valid_hex(product[11]) if len(product) > 11 else None
                foreground = color or "#1f3b4d"
                hover = _shade(color, 0.85) if color else "#2c526a"
                button = QPushButton(button_text, products_frame)
                button.setCursor(Qt.PointingHandCursor)
                button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                button.setMinimumWidth(0)
                button.setFixedHeight(46)
                # Ignore text-based size hints so both grid columns receive equal widths.
                button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                button.setFont(QFont("Segoe UI", 9))
                button.setStyleSheet(
                    f"QPushButton {{ background: {foreground}; color: {_text_on(foreground)}; "
                    f"border: 0; border-radius: 7px; padding: 4px; text-align: center; }}"
                    f"QPushButton:hover {{ background: {hover}; }}"
                )
                button.clicked.connect(lambda _checked=False, p=product: ask_product_quantity(p))
                products_grid.addWidget(button, index // 2, index % 2)
            group_layout.addWidget(products_frame)
            quick_content_layout.addWidget(group_frame)

        if not groups:
            quick_content_layout.addWidget(_make_label(quick_content, "لا توجد منتجات نشطة", palette, size=9, color=palette["muted"]))
        quick_content_layout.addStretch(1)
        quick_access_state["warehouse_id"] = warehouse_id
        quick_access_state["built"] = True

    # Connect the signal exactly once. Updating a Python callback avoids calling
    # clicked.disconnect() without a receiver, which produces PySide warnings.
    shift_action: dict[str, Callable | None] = {"callback": None}
    shift_button.clicked.connect(
        lambda _checked=False: (
            shift_action["callback"]()
            if callable(shift_action["callback"])
            else None
        )
    )

    def set_shift_button(text: str, kind: str, callback: Callable):
        color_keys = {
            "success": (palette["success"], palette["success_hover"]),
            "danger": (palette["danger"], palette["danger_hover"]),
        }
        foreground, hover = color_keys[kind]
        shift_action["callback"] = callback
        shift_button.setText(text)
        shift_button.setStyleSheet(
            f"QPushButton {{ background: {foreground}; color: #fff; border: 0; border-radius: 8px; padding: 5px 10px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )

    def refresh_shift_ui() -> bool:
        try:
            row = get_open_shift(cashier_id)
        except Exception as exc:
            current_shift["row"] = None
            shift_text_label.setText("تعذر تحميل حالة الوردية")
            shift_button.setEnabled(False)
            _message("error", "خطأ قاعدة البيانات", f"تعذر تحميل حالة الوردية:\n{exc}", top)
            return False
        current_shift["row"] = row
        shift_button.setEnabled(True)
        if row:
            current_shift["last_id"] = int(row[0])
            shift_text_label.setText(f"الوردية #{row[0]} مفتوحة منذ {row[2]}")
            set_shift_button("إغلاق الوردية", "danger", ask_close_shift)
        else:
            shift_text_label.setText("لا توجد وردية مفتوحة")
            set_shift_button("بدء الوردية", "success", ask_open_shift)
        return True

    def confirm_sale():
        if not cart:
            _message("warning", "السلة فارغة", "أضف صنفًا واحدًا على الأقل.", top)
            return
        shift_row = current_shift["row"]
        if not shift_row:
            _message("warning", "لا توجد وردية مفتوحة", "ابدأ وردية الكاشير قبل إتمام البيع.", top)
            return
        try:
            selected_customer, new_name, new_phone = customer_id_from_form()
            total_minor = current_total_minor()
            paid_minor = money_to_minor(paid_entry.text() or "0")
            if paid_minor > total_minor:
                raise ValueError("المبلغ المدفوع أكبر من إجمالي الفاتورة")
            if selected_customer is None and not new_name and paid_minor != total_minor:
                raise ValueError("يجب دفع فاتورة العميل النقدي بالكامل")
            method_id = payment_menu.currentData()
            if method_id is None:
                raise ValueError("اختر طريقة دفع")

            sale = create_cashier_sale(
                items=[{"product_id": product_id, "quantity": str(entry["quantity"])} for product_id, entry in cart.items()],
                cashier_id=cashier_id,
                warehouse_id=current_warehouse_id(),
                payment_method_id=int(method_id),
                amount_paid_minor=paid_minor,
                customer_id=selected_customer,
                new_customer_name=new_name,
                new_customer_phone=new_phone,
                shift_id=int(shift_row[0]),
            )
        except Exception as exc:
            _message("error", "تعذر إتمام البيع", str(exc), top)
            return

        export_path = None
        export_error = None
        try:
            export_path = export_cashier_sale_to_excel(int(sale["sale_id"]), shift_id=int(shift_row[0]))
        except Exception as exc:
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
        _message("info", "تم البيع", message, top)
        cart.clear()
        paid_entry.setText(minor_to_money(0))
        new_customer_check.setChecked(False)
        new_customer_name.clear()
        new_customer_phone.clear()
        customer_menu.setCurrentIndex(0)
        refresh_customer_mode()
        refresh_customers()
        repaint_cart()
        build_quick_access(force=True)
        search_entry.setFocus()

    def amount_dialog(title: str, prompt: str, callback: Callable[[int], Any], default: str = "0"):
        dialog = _new_dialog(top, title, palette, (360, 190))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(_make_label(dialog, prompt, palette, size=12, bold=True, wrap=True))
        amount_entry = _style_line_edit(QLineEdit(dialog), palette, height=36, align=Qt.AlignCenter)
        amount_entry.setText(default)
        layout.addWidget(amount_entry)
        confirm_button = _make_button(dialog, "تأكيد", kind="primary", palette=palette)
        layout.addWidget(confirm_button, 0, Qt.AlignHCenter)

        def submit():
            try:
                amount = money_to_minor(amount_entry.text())
                callback(amount)
                dialog.accept()
            except Exception as exc:
                _message("error", "خطأ", str(exc), dialog)

        confirm_button.clicked.connect(submit)
        amount_entry.returnPressed.connect(submit)
        dialog.exec()

    def ask_open_shift():
        def open_it(amount: int):
            try:
                shift_id = open_cashier_shift(cashier_id, amount)
                current_shift["last_id"] = int(shift_id)
                refresh_shift_ui()
                _message("info", "الوردية", "بدأت الوردية بنجاح وتم تجهيز مجلد تقاريرها.", top)
            except Exception as exc:
                refresh_shift_ui()
                _message("error", "تعذر بدء الوردية", f"{type(exc).__name__}: {exc}", top)
        amount_dialog("بدء الوردية", "رصيد النقدية عند بداية الوردية", open_it)

    def ask_close_shift():
        row = current_shift["row"]
        if not row:
            refresh_shift_ui()
            return

        def close_it(amount: int):
            expected = close_cashier_shift(int(row[0]), amount, cashier_id)
            refresh_shift_ui()
            _message(
                "info", "إغلاق الوردية",
                f"تم إغلاق الوردية.\n"
                f"النقدية المتوقعة: {minor_to_money(expected)}\n"
                f"النقدية الفعلية: {minor_to_money(amount)}\n"
                f"الفرق: {minor_to_money(amount - expected)}",
                top,
            )
        amount_dialog("إغلاق الوردية", "أدخل النقدية الفعلية في الدرج", close_it)

    def open_return_dialog():
        dialog = _new_dialog(top, "مرتجع بيع", palette, (520, 390))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(6)
        layout.addWidget(_make_label(dialog, "رقم العملية/الفاتورة (من سجل المبيعات) أو معرف البيع", palette, size=11))
        sale_ref_entry = _style_line_edit(QLineEdit(dialog), palette)
        layout.addWidget(sale_ref_entry)
        layout.addWidget(_make_label(dialog, "المنتج القابل للإرجاع", palette, size=11))
        item_menu = _style_combo(QComboBox(dialog), palette)
        layout.addWidget(item_menu)
        layout.addWidget(_make_label(dialog, "الكمية المراد إرجاعها", palette, size=11))
        return_quantity_entry = _style_line_edit(QLineEdit(dialog), palette)
        return_quantity_entry.setText("1")
        layout.addWidget(return_quantity_entry)
        resolved: dict[str, Any] = {"sale_id": None, "items": [], "labels": {}, "identifier": None}

        def load_return_items(show_message: bool = True):
            identifier = sale_ref_entry.text().strip()
            if not identifier:
                _message("error", "تعذر تحميل الفاتورة", "أدخل رقم الفاتورة أو معرفها.", dialog)
                return False
            try:
                sale_id, sale_number, rows = get_returnable_sales_items(identifier)
                if not rows:
                    raise ValueError("لا توجد كميات متبقية قابلة للإرجاع لهذه الفاتورة")
                labels = {}
                item_menu.clear()
                for row in rows:
                    product_id, name, remaining, _price, _cost = row
                    label = f"{name} — متبقي {remaining:g} (ID {product_id})"
                    labels[label] = row
                    item_menu.addItem(label, row)
                resolved.update({"sale_id": int(sale_id), "items": rows, "labels": labels, "identifier": identifier})
                if show_message:
                    _message("info", "الفاتورة", f"الفاتورة {sale_number} جاهزة للمرتجع.", dialog)
                return True
            except Exception as exc:
                resolved.update({"sale_id": None, "items": [], "labels": {}, "identifier": None})
                item_menu.clear()
                _message("error", "تعذر تحميل الفاتورة", str(exc), dialog)
                return False

        def submit_return():
            try:
                identifier = sale_ref_entry.text().strip()
                if resolved["sale_id"] is None or resolved["identifier"] != identifier:
                    if not load_return_items(show_message=False):
                        return
                row = item_menu.currentData()
                if not row:
                    raise ValueError("اختر منتجًا صالحًا")
                quantity = _quantity(return_quantity_entry.text())
                if quantity > Decimal(str(row[2])):
                    raise ValueError(f"الكمية المتبقية هي {row[2]:g} فقط")
                shift = current_shift["row"]
                if not shift:
                    raise ValueError("ابدأ وردية الكاشير قبل تسجيل المرتجع")
                return_id = create_cashier_return(
                    int(resolved["sale_id"]), int(row[0]), float(quantity), cashier_id,
                    int(shift[0]), "مرتجع من صفحة الكاشير",
                )
                dialog.accept()
                build_quick_access(force=True)
                _message("info", "تم المرتجع", f"تم إنشاء المرتجع بنجاح. معرف المرتجع: {return_id}", top)
            except Exception as exc:
                _message("error", "تعذر تنفيذ المرتجع", str(exc), dialog)

        buttons = QHBoxLayout()
        load_button = _make_button(dialog, "تحميل الفاتورة", kind="primary", palette=palette)
        submit_button = _make_button(dialog, "تسجيل المرتجع", kind="danger", palette=palette)
        buttons.addWidget(load_button)
        buttons.addStretch(1)
        buttons.addWidget(submit_button)
        layout.addLayout(buttons)
        load_button.clicked.connect(load_return_items)
        submit_button.clicked.connect(submit_return)
        dialog.exec()

    def open_session_reports():
        shift_row = current_shift.get("row")
        shift_id = int(shift_row[0]) if shift_row else current_shift.get("last_id")
        if not shift_id:
            _message("info", "تقارير الوردية", "ابدأ وردية أولًا لإنشاء مجلد التقارير.", top)
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
            _message("error", "تعذر فتح مجلد التقارير", f"تعذر فتح المجلد الخاص بالوردية:\n{type(exc).__name__}: {exc}", top)

    def on_warehouse_change(_index: int = -1):
        try:
            fresh_products = {
                int(product[0]): product
                for product in get_cashier_products("", current_warehouse_id())
            }
            for product_id, entry in cart.items():
                if product_id in fresh_products:
                    entry["product"] = fresh_products[product_id]
            build_quick_access()
            repaint_cart()
        except Exception as exc:
            _message("error", "خطأ", str(exc), top)

    # ---------------- customer debt management ----------------
    debt_window: dict[str, QDialog | None] = {"win": None}

    def show_debt_customers():
        old = debt_window["win"]
        if old is not None:
            try:
                if old.isVisible():
                    old.raise_()
                    old.activateWindow()
                    return
            except RuntimeError:
                pass
        debt_window["win"] = None

        win = QDialog(page)
        debt_window["win"] = win
        win.setWindowTitle("العملاء المدينون")
        win.resize(900, 590)
        win.setLayoutDirection(Qt.RightToLeft)
        win.setStyleSheet(f"QDialog {{ background: {palette['surface']}; color: {palette['text']}; }}")
        win.setAttribute(Qt.WA_DeleteOnClose, True)
        layout = QVBoxLayout(win)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        header = QFrame(win)
        header.setStyleSheet(f"background: {palette['surface_alt']}; border-radius: 12px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.addWidget(_make_label(header, "العملاء المدينون", palette, size=18, bold=True))
        header_layout.addStretch(1)
        pay_button = _make_button(header, "تسديد الدين", kind="success", palette=palette, width=105)
        update_button = _make_button(header, "تعديل الدين", kind="neutral", palette=palette, width=105)
        remove_button = _make_button(header, "حذف الدين", kind="danger", palette=palette, width=105)
        add_debt_button = _make_button(header, "إضافة دين", kind="warning", palette=palette, width=105)
        header_layout.addWidget(pay_button)
        header_layout.addWidget(update_button)
        header_layout.addWidget(remove_button)
        header_layout.addWidget(add_debt_button)
        layout.addWidget(header)

        search_bar = QWidget(win)
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_debt_entry = _style_line_edit(QLineEdit(search_bar), palette, height=36)
        search_debt_entry.setPlaceholderText("ابحث باسم العميل أو رقم الهاتف")
        search_layout.addWidget(search_debt_entry, 1)
        debt_refresh_button = _make_button(search_bar, "تحديث", kind="neutral", palette=palette, width=80, height=36)
        search_layout.addWidget(debt_refresh_button)
        layout.addWidget(search_bar)

        debt_tree = QTableView(win)
        debt_model = _DebtTableModel(debt_tree)
        debt_proxy = QSortFilterProxyModel(debt_tree)
        debt_proxy.setSourceModel(debt_model)
        debt_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        debt_proxy.setFilterKeyColumn(-1)  # Search all visible columns.
        debt_proxy.setSortRole(Qt.ItemDataRole.UserRole + 1)
        debt_tree.setModel(debt_proxy)
        debt_tree.setSortingEnabled(True)
        _configure_table_view(debt_tree, palette, (75, 280, 160, 160))
        layout.addWidget(debt_tree, 1)
        summary_label = _make_label(win, "", palette, size=12, bold=True, color=palette["muted"])
        layout.addWidget(summary_label)

        def refresh(_event=None):
            try:
                rows = get_debt_customers()
            except Exception as exc:
                _message("error", "خطأ", f"تعذر تحميل العملاء المدينين:\n{exc}", win)
                return

            records = [
                (int(customer_id), str(name), str(phone or ""), int(debt))
                for customer_id, name, phone, debt in rows
            ]
            debt_model.set_records(records)
            debt_proxy.setFilterFixedString(search_debt_entry.text().strip())
            total = sum(record[3] for record in records)
            summary_label.setText(
                f"إجمالي الديون: {minor_to_money(total)}   |   عدد العملاء المدينين: {len(records)}"
            )

        def selected_debtor():
            proxy_index = debt_tree.currentIndex()
            if not proxy_index.isValid():
                _message("warning", "اختر عميلًا", "اختر عميلًا من القائمة أولًا.", win)
                return None
            source_index = debt_proxy.mapToSource(
                proxy_index.sibling(proxy_index.row(), 0)
            )
            return debt_model.record_at(source_index.row())

        def current_shift_id():
            row = current_shift["row"]
            return int(row[0]) if row else None

        def form_dialog(title: str, fields: list[tuple], on_submit: Callable,
                        submit_text: str = "تأكيد", confirm: Callable | None = None):
            """Open a small modal form. Field tuple: key, label, kind, default, values."""
            dlg = _new_dialog(win, title, palette)
            dlg.setMinimumWidth(410)
            form_layout = QFormLayout()
            form_layout.setContentsMargins(16, 14, 16, 8)
            form_layout.setVerticalSpacing(8)
            form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            variables: dict[str, QWidget] = {}
            first_entry: QLineEdit | None = None
            for key, label, kind, default, choices in fields:
                if kind == "combo":
                    widget = _style_combo(QComboBox(dlg), palette, 34)
                    for value in choices:
                        widget.addItem(str(value), value)
                    target = widget.findText(str(default))
                    if target >= 0:
                        widget.setCurrentIndex(target)
                else:
                    widget = _style_line_edit(QLineEdit(dlg), palette, height=34)
                    widget.setText(str(default))
                    if first_entry is None:
                        first_entry = widget
                form_layout.addRow(_make_label(dlg, label, palette, size=10, bold=True), widget)
                variables[key] = widget
            body = QVBoxLayout(dlg)
            body.addLayout(form_layout)
            button_row = QHBoxLayout()
            submit_button = _make_button(dlg, submit_text, kind="primary", palette=palette)
            cancel_button = _make_button(dlg, "إلغاء", kind="neutral", palette=palette)
            button_row.addWidget(submit_button)
            button_row.addStretch(1)
            button_row.addWidget(cancel_button)
            body.addLayout(button_row)

            def submit():
                values = {}
                for key, widget in variables.items():
                    values[key] = widget.currentData() if isinstance(widget, QComboBox) else widget.text()
                    if values[key] is None and isinstance(widget, QComboBox):
                        values[key] = widget.currentText()
                if confirm is not None and not confirm(values, dlg):
                    return
                try:
                    message = on_submit(values)
                except Exception as exc:
                    _message("error", "تعذر تنفيذ العملية", str(exc), dlg)
                    return
                dlg.accept()
                refresh()
                if message:
                    _message("info", title, message, win)

            submit_button.clicked.connect(submit)
            cancel_button.clicked.connect(dlg.reject)
            if first_entry is not None:
                first_entry.returnPressed.connect(submit)
                QTimer.singleShot(100, first_entry.setFocus)
            dlg.exec()

        def pay_selected():
            picked = selected_debtor()
            if not picked:
                return
            customer_id, name, debt = picked
            if current_shift_id() is None:
                _message("warning", "لا توجد وردية مفتوحة", "ابدأ وردية الكاشير قبل تسديد الدين.", win)
                return

            def submit(values):
                method_id = method_labels.get(values["method"])
                if method_id is None:
                    raise ValueError("اختر طريقة دفع")
                amount = money_to_minor(values["amount"] or "0")
                result = pay_customer_debt(customer_id, method_id, cashier_id, current_shift_id(), amount)
                return (
                    f"تم تسجيل التسديد {result['number']}\n"
                    f"المبلغ: {minor_to_money(result['amount'])}\n"
                    f"المتبقي على العميل: {minor_to_money(result['remaining_debt'])}"
                )

            form_dialog(
                f"تسديد دين: {name}",
                [("method", "طريقة الدفع", "combo", payment_menu.currentText(), list(method_labels)),
                 ("amount", f"المبلغ المسدد (الدين الحالي {minor_to_money(debt)})", "entry", minor_to_money(debt), None)],
                submit, "تسديد",
            )

        def update_selected():
            picked = selected_debtor()
            if not picked:
                return
            customer_id, name, debt = picked

            def submit(values):
                result = update_customer_debt(
                    customer_id, money_to_minor(values["new_debt"] or "0"), cashier_id,
                    values["reason"], current_shift_id(),
                )
                return (
                    f"تم تعديل الدين ({result['number']})\n"
                    f"من {minor_to_money(result['debt_before'])} إلى {minor_to_money(result['debt_after'])}"
                )

            form_dialog(
                f"تعديل دين: {name}",
                [("new_debt", f"قيمة الدين الجديدة (الحالية {minor_to_money(debt)})", "entry", minor_to_money(debt), None),
                 ("reason", "سبب التعديل *", "entry", "", None)],
                submit, "حفظ التعديل",
            )

        def remove_selected_debt():
            picked = selected_debtor()
            if not picked:
                return
            customer_id, name, debt = picked

            def confirm_remove(values, dlg):
                try:
                    amount = money_to_minor(values["amount"] or "0")
                except Exception as exc:
                    _message("error", "خطأ", str(exc), dlg)
                    return False
                return _ask_yes_no(
                    "تأكيد حذف الدين",
                    f"سيتم حذف {minor_to_money(amount)} من دين العميل {name} "
                    "دون استلام أي نقدية، وسيُسجَّل ذلك للمدير.\nهل تريد المتابعة؟",
                    dlg,
                )

            def submit(values):
                result = remove_customer_debt(
                    customer_id, cashier_id, values["reason"],
                    money_to_minor(values["amount"] or "0"), current_shift_id(),
                )
                return f"تم حذف الدين ({result['number']})\nالمتبقي على العميل: {minor_to_money(result['debt_after'])}"

            form_dialog(
                f"حذف دين: {name}",
                [("amount", f"المبلغ المراد حذفه (الدين الحالي {minor_to_money(debt)})", "entry", minor_to_money(debt), None),
                 ("reason", "سبب الحذف *", "entry", "", None)],
                submit, "حذف", confirm=confirm_remove,
            )

        def add_debt():
            names = [label for label, customer_id in customer_labels.items() if customer_id is not None]
            if not names:
                _message("warning", "لا يوجد عملاء", "الدين يُسجَّل للعملاء المسجلين فقط. أضف العميل أولًا من صفحة البيع.", win)
                return
            selected_name = names[0]
            selected_debt_row = debt_tree.currentIndex()
            if selected_debt_row.isValid():
                source_index = debt_proxy.mapToSource(
                    selected_debt_row.sibling(selected_debt_row.row(), 0)
                )
                selected_record = debt_model.record_at(source_index.row())
                if selected_record:
                    selected_id = selected_record[0]
                    selected_name = next(
                        (label for label, cid in customer_labels.items() if cid == selected_id),
                        selected_name,
                    )

            def submit(values):
                customer_id = customer_labels.get(values["customer"])
                if customer_id is None:
                    raise ValueError("اختر عميلًا مسجلًا؛ لا يُسجَّل دين لغير العملاء")
                result = add_customer_debt(
                    customer_id, money_to_minor(values["amount"] or "0"), cashier_id,
                    values["reason"], current_shift_id(),
                )
                return f"تمت إضافة الدين ({result['number']})\nإجمالي دين العميل الآن: {minor_to_money(result['debt_after'])}"

            form_dialog(
                "إضافة دين",
                [("customer", "العميل", "combo", selected_name, names),
                 ("amount", "مبلغ الدين المضاف", "entry", "", None),
                 ("reason", "سبب إضافة الدين *", "entry", "", None)],
                submit, "إضافة",
            )

        pay_button.clicked.connect(pay_selected)
        update_button.clicked.connect(update_selected)
        remove_button.clicked.connect(remove_selected_debt)
        add_debt_button.clicked.connect(add_debt)
        search_debt_entry.textChanged.connect(refresh)
        debt_refresh_button.clicked.connect(refresh)
        win.destroyed.connect(lambda *_: debt_window.update({"win": None}))
        refresh()
        win.show()
        win.raise_()
        win.activateWindow()

    # ---------------- connect signals and add checkout actions ----------------
    add_button.clicked.connect(search_and_add)
    search_entry.returnPressed.connect(search_and_add)
    increase_button.clicked.connect(lambda: change_selected_qty(1))
    decrease_button.clicked.connect(lambda: change_selected_qty(-1))
    remove_button.clicked.connect(remove_selected)
    clear_button.clicked.connect(clear_cart)
    tree.doubleClicked.connect(lambda _index: change_selected_qty(1))
    delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), tree)
    delete_shortcut.activated.connect(remove_selected)
    warehouse_menu.currentIndexChanged.connect(on_warehouse_change)
    new_customer_check.toggled.connect(lambda _checked: refresh_customer_mode(reset_payment=True))
    customer_menu.currentIndexChanged.connect(lambda _index: refresh_customer_mode(reset_payment=True))

    confirm_button = _make_button(controls_body, "تأكيد البيع", kind="success", palette=palette, height=46, font_size=13)
    controls_body_layout.addWidget(confirm_button)
    confirm_button.clicked.connect(confirm_sale)
    controls_body_layout.addWidget(_make_button(controls_body, "مرتجع بيع", open_return_dialog, kind="danger", palette=palette, height=39))
    controls_body_layout.addWidget(_make_button(controls_body, "تحديث الأصناف والعملاء", lambda: (build_quick_access(force=True), refresh_customers()), kind="neutral", palette=palette, height=37))
    controls_body_layout.addWidget(_make_button(controls_body, "فتح مجلد تقارير الوردية", open_session_reports, kind="info", palette=palette, height=37))
    controls_body_layout.addWidget(_make_button(controls_body, "إدارة ديون العملاء", show_debt_customers, kind="info", palette=palette, height=37))
    controls_body_layout.addWidget(_make_label(
        controls_body,
        "اختصارات: Enter لإضافة البحث، Delete لحذف الصنف، والنقر المزدوج لزيادة الكمية.",
        palette, size=9, color=palette["muted"], wrap=True,
    ))
    controls_body_layout.addStretch(1)

    build_quick_access()
    refresh_shift_ui()
    refresh_customer_mode()
    repaint_cart()
    return True
