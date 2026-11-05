"""Centralized page navigation for the single MyShop QMainWindow.

These functions never construct a QMainWindow or QApplication. They only
replace the existing window's central page.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow


def _validate_main_window(root: QMainWindow) -> None:
    if not isinstance(root, QMainWindow):
        raise TypeError(
            "The router expects the existing BaseWindow/QMainWindow instance; "
            f"received {type(root).__name__}."
        )


def go_login(root: QMainWindow):
    _validate_main_window(root)
    from UI.login_page import show_login

    return show_login(root)


def go_admin(root: QMainWindow):
    _validate_main_window(root)
    from UI.ui_admin import open_admin

    return open_admin(root)


def go_cashier(root: QMainWindow, username: str):
    _validate_main_window(root)
    from UI.sell_ui import build_sell_ui

    return build_sell_ui(root, username)
