"""Compact cashier page with a small, disposable logout control group."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from Services.cashier_service import get_open_shift, get_username_id
from UI.basewindow import BaseWindow, is_dark
from UI.router import go_login
from .sell_ui import build_sell_ui


THEME = {
    "Dark": {
        "bg": "#121212",
        "text": "#ffffff",
        "button_fg": "#1f3b4d",
        "danger": "#e74c3c",
        "footer_bg": "#1e1e1e",
        "footer_border": "#343434",
    },
    "Light": {
        "bg": "#f4f6f8",
        "text": "#000000",
        "button_fg": "#1f3b4d",
        "danger": "#e74c3c",
        "footer_bg": "#ffffff",
        "footer_border": "#dce2e8",
    },
}


FOOTER_OBJECT_NAME = "cashierFooter"
STATUS_BAR_OBJECT_NAME = "cashierStatusBar"


def _button(
    text: str,
    bg: str,
    hover: str,
    on_click: Callable[[], None],
    fg: str = "white",
) -> QPushButton:
    """Create a compact footer button."""
    button = QPushButton(text)
    button.setObjectName("cashierFooterButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    button.setFixedHeight(28)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    button.setAutoDefault(False)
    button.setDefault(False)
    button.setStyleSheet(
        "QPushButton#cashierFooterButton {"
        f" background-color: {bg}; color: {fg}; border: none;"
        " border-radius: 4px; padding: 3px 9px;"
        " font: 12px 'Segoe UI';"
        "}"
        "QPushButton#cashierFooterButton:hover {"
        f" background-color: {hover};"
        "}"
    )
    button.clicked.connect(lambda _checked=False: on_click())
    return button


def _logout_allowed(root: BaseWindow, username: str) -> bool:
    """Block switching/exiting while a shift is open or its status is unknown."""
    try:
        cashier_id = get_username_id(str(username))
        if cashier_id is None:
            raise RuntimeError("لم يتم العثور على حساب الكاشير الحالي.")

        open_shift = get_open_shift(int(cashier_id))
    except Exception as exc:
        QMessageBox.critical(
            root,
            "تعذر التحقق من الوردية",
            "لم نتمكن من التأكد من حالة وردية الكاشير، لذلك تم منع تسجيل الخروج.\n\n"
            f"التفاصيل: {exc}",
        )
        return False

    if open_shift:
        shift_id = None
        if isinstance(open_shift, (tuple, list)) and open_shift:
            shift_id = open_shift[0]
        elif isinstance(open_shift, dict):
            shift_id = open_shift.get("id") or open_shift.get("shift_id")

        suffix = f" رقم الوردية: {shift_id}." if shift_id is not None else ""
        QMessageBox.warning(
            root,
            "لا يمكن تسجيل الخروج",
            "لا يمكنك تبديل المستخدم أو الخروج أثناء وجود وردية مفتوحة.\n"
            "ارجع إلى شاشة الكاشير وأغلق الوردية أولاً."
            f"{suffix}",
        )
        return False

    return True


def _remove_cashier_footer(root: BaseWindow) -> None:
    """Destroy this page's footer before navigating to another user/page."""
    status_bar_method = getattr(root, "statusBar", None)
    if not callable(status_bar_method):
        return

    status_bar = status_bar_method()
    footer = status_bar.findChild(QWidget, FOOTER_OBJECT_NAME)
    if footer is not None:
        status_bar.removeWidget(footer)
        footer.hide()
        footer.setParent(None)
        footer.deleteLater()

    # The cashier status bar is only used for this compact control group.
    # Hide it after removing the group so the login page has no empty strip.
    status_bar.hide()


def _install_cashier_footer(
    root: BaseWindow,
    username: str,
    colors: dict[str, str],
) -> QWidget:
    """Put a compact two-button box at the bottom-left of the main window."""
    status_bar_method = getattr(root, "statusBar", None)
    if not callable(status_bar_method):
        raise TypeError("BaseWindow must provide QMainWindow.statusBar().")

    status_bar = status_bar_method()

    # Remove an earlier cashier footer before installing a fresh one.
    old_footer = status_bar.findChild(QWidget, FOOTER_OBJECT_NAME)
    if old_footer is not None:
        status_bar.removeWidget(old_footer)
        old_footer.hide()
        old_footer.setParent(None)
        old_footer.deleteLater()

    status_bar.setObjectName(STATUS_BAR_OBJECT_NAME)
    # QStatusBar.addWidget() places ordinary widgets on the left in LTR mode.
    status_bar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    status_bar.setSizeGripEnabled(False)
    status_bar.setStyleSheet(
        "QStatusBar#cashierStatusBar {"
        f" background-color: {colors['footer_bg']};"
        f" color: {colors['text']};"
        f" border-top: 1px solid {colors['footer_border']};"
        " padding: 2px 5px;"
        "}"
        "QStatusBar#cashierStatusBar::item { border: none; }"
    )

    # This frame contains only the two actions; its size is driven by its contents.
    footer = QFrame(status_bar)
    footer.setObjectName(FOOTER_OBJECT_NAME)
    footer.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    footer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    footer.setStyleSheet(
        "QFrame#cashierFooter {"
        f" background-color: {colors['footer_bg']};"
        f" border: 1px solid {colors['footer_border']};"
        " border-radius: 6px;"
        "}"
    )

    footer_layout = QHBoxLayout(footer)
    footer_layout.setContentsMargins(4, 3, 4, 3)
    footer_layout.setSpacing(5)

    def switch_user() -> None:
        if not _logout_allowed(root, username):
            return
        # The status-bar widget survives central-page replacement, so explicitly
        # destroy it before go_login() installs the login page.
        _remove_cashier_footer(root)
        go_login(root)

    def exit_application() -> None:
        if not _logout_allowed(root, username):
            return
        _remove_cashier_footer(root)
        root.close()

    switch_button = _button(
        "تبديل المستخدم",
        "#666666",
        "#555555",
        switch_user,
    )
    exit_button = _button(
        "✕ خروج",
        colors["danger"],
        "#c0392b",
        exit_application,
    )

    footer_layout.addWidget(switch_button)
    footer_layout.addWidget(exit_button)

    status_bar.addWidget(footer, 0)
    status_bar.setVisible(True)
    footer.show()
    return footer


def open_cashier(root: BaseWindow, username: str) -> QWidget:
    colors = THEME["Dark" if is_dark() else "Light"]

    # Clear any footer left by a previous cashier page before rebuilding.
    _remove_cashier_footer(root)

    page = QWidget()
    page.setObjectName("cashierPage")
    page.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    page.setStyleSheet(f"#cashierPage {{ background:{colors['bg']}; }}")

    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    # Compact header: smaller height, padding, and typography.
    header = QFrame(page)
    header.setObjectName("cashierHeader")
    header.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    header.setFixedHeight(48)
    header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    header.setStyleSheet(
        f"QFrame#cashierHeader {{ background:{colors['button_fg']}; }}"
    )

    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(12, 0, 12, 0)
    header_layout.setSpacing(8)

    user_label = QLabel(f"👤 {username}", header)
    user_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    user_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    user_label.setStyleSheet(f"color:{colors['text']}; font:13px 'Segoe UI';")

    title_label = QLabel("صفحة الكاشير", header)
    title_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    title_label.setStyleSheet(f"color:{colors['text']}; font:bold 19px 'Segoe UI';")

    header_layout.addWidget(user_label)
    header_layout.addStretch(1)
    header_layout.addWidget(title_label)
    page_layout.addWidget(header, 0)

    content = QWidget(page)
    content.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(12, 10, 12, 10)
    content_layout.setSpacing(0)
    page_layout.addWidget(content, 1)

    if not build_sell_ui(content, username):
        fallback = QLabel(
            "تعذر تحميل نقطة البيع. راجع رسالة الخطأ ثم حاول مرة أخرى.",
            content,
        )
        fallback.setWordWrap(True)
        fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fallback.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        fallback.setStyleSheet("font:14px 'Segoe UI';")
        content_layout.addWidget(fallback)

    # Install the page before the status-bar control group.
    root.set_page(page)
    page.show()
    _install_cashier_footer(root, username, colors)
    return page
