"""Cashier page (PySide6)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from UI.basewindow import BaseWindow, is_dark
from UI.router import go_login
from .sell_ui import build_sell_ui

THEME = {
    "Dark": {
        "bg": "#121212", "card": "#1e1e1e", "text": "#ffffff",
        "button_fg": "#1f3b4d", "button_hover": "#2c526a",
        "danger": "#e74c3c", "bottom_bg": "#1e1e1e",
    },
    "Light": {
        "bg": "#f4f6f8", "card": "#ffffff", "text": "#000000",
        "button_fg": "#1f3b4d", "button_hover": "#2c526a",
        "danger": "#e74c3c", "bottom_bg": "#ffffff",
    },
}


def _button(text: str, bg: str, hover: str, on_click, fg: str = "white") -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background:{bg}; color:{fg}; border:none;"
        f" border-radius:6px; padding:8px 18px; font:18px 'Arial'; }}"
        f"QPushButton:hover {{ background:{hover}; }}"
    )
    btn.clicked.connect(lambda _checked=False: on_click())
    return btn


def open_cashier(root: BaseWindow, username: str) -> QWidget:
    colors = THEME["Dark" if is_dark() else "Light"]

    # ===== MAIN PAGE =====
    page = QWidget()
    page.setObjectName("cashierPage")
    page.setStyleSheet(f"#cashierPage {{ background:{colors['bg']}; }}")
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    # ===== HEADER =====
    # Layouts are mirrored (RTL), so the first widget added sits on the RIGHT.
    # Physical placement matches the old screen: user on the right, title on the left.
    header = QFrame()
    header.setObjectName("header")
    header.setFixedHeight(80)
    header.setStyleSheet(f"#header {{ background:{colors['button_fg']}; }}")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(20, 0, 20, 0)

    user_label = QLabel(f"👤 {username}")
    user_label.setStyleSheet(f"color:{colors['text']}; font:20px 'Segoe UI';")
    title_label = QLabel("صفحة الكاشير")
    title_label.setStyleSheet(f"color:{colors['text']}; font:bold 30px 'Segoe UI';")

    header_layout.addWidget(user_label)
    header_layout.addStretch(1)
    header_layout.addWidget(title_label)
    page_layout.addWidget(header)

    # ===== CONTENT (sell UI is mounted here) =====
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(20, 20, 20, 20)
    page_layout.addWidget(content, 1)

    # build_sell_ui must be ported to take this QWidget (it adds its own layout).
    if not build_sell_ui(content, username):
        fallback = QLabel("تعذر تحميل نقطة البيع. راجع رسالة الخطأ ثم حاول مرة أخرى.")
        fallback.setWordWrap(True)
        fallback.setAlignment(Qt.AlignCenter)
        fallback.setStyleSheet("font:16px 'Segoe UI';")
        content_layout.addWidget(fallback)

    # ===== BOTTOM BAR =====
    bottom = QFrame()
    bottom.setObjectName("bottom")
    bottom.setFixedHeight(60)
    bottom.setStyleSheet(f"#bottom {{ background:{colors['bottom_bg']}; }}")
    bottom_layout = QHBoxLayout(bottom)
    bottom_layout.setContentsMargins(10, 0, 20, 0)
    bottom_layout.setSpacing(10)

    welcome = QLabel(f"أهلاً بك : {username}")
    welcome.setStyleSheet(f"color:{colors['text']}; font:18px 'Arial';")

    switch_btn = _button("تبديل المستخدم", "gray", "#6b6b6b", lambda: go_login(root))
    exit_btn = _button("✕ خروج", colors["danger"], "#c0392b", root.close)

    # Right -> left: welcome, (stretch), switch user, exit  => exit ends up far left.
    bottom_layout.addWidget(welcome)
    bottom_layout.addStretch(1)
    bottom_layout.addWidget(switch_btn)
    bottom_layout.addWidget(exit_btn)
    page_layout.addWidget(bottom)

    root.set_page(page)  # replaces the previous page (login) and frees it
    return page