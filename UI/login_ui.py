"""PySide6 login action; authentication remains in Services.auth."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QLineEdit, QMainWindow

from Services.auth import login as authenticate
from UI.router import go_admin, go_cashier, go_login

def _entry_text(entry) -> str:
    """Accept a QLineEdit or the former get()-compatible login field."""
    if isinstance(entry, QLineEdit):
        return entry.text()
    getter = getattr(entry, "get", None)
    if callable(getter):
        return str(getter())
    raise TypeError(f"Unsupported login input widget: {type(entry).__name__}")


def login_ui(
    root: QMainWindow,
    entry_username,
    entry_password,
    _login_card=None,
) -> bool:
    """Authenticate and navigate by replacing the current central page.

    `_login_card` is accepted only for compatibility with login_screen.py. It
    is deliberately not destroyed: set_page() replaces the complete login page.
    """
    username = _entry_text(entry_username).strip()
    password = _entry_text(entry_password)

    if not username or not password:
        QMessageBox.warning(root, "بيانات الدخول", "أدخل اسم المستخدم وكلمة المرور.")
        return False

    try:
        success, role = authenticate(username, password)
    except Exception as exc:
        QMessageBox.critical(
            root,
            "تعذر تسجيل الدخول",
            f"حدث خطأ أثناء التحقق من بيانات الدخول:\n{type(exc).__name__}: {exc}",
        )
        return False

    if not success:
        QMessageBox.warning(root, "تسجيل الدخول", "اسم المستخدم أو كلمة المرور غير صحيح.")
        if isinstance(entry_password, QLineEdit):
            entry_password.clear()
            entry_password.setFocus()
        return False

    # admin_ui uses this value for the dashboard header and audit operations.
    from UI.ui_admin import getUsername

    getUsername(username)

    if role == "Admin":
        go_admin(root)
    elif role == "Cashier":
        result = go_cashier(root, username)

        if result is False:
            QMessageBox.warning(
                root,
                "تعذر فتح واجهة الكاشير",
                "تعذر تهيئة واجهة الكاشير. تحقق من إعدادات النظام.",
            )
            go_login(root)
            return False
    else:
        QMessageBox.critical(
            root,
            "خطأ في الصلاحيات",
            "الدور المرتبط بهذا الحساب غير معروف.",
        )
        go_login(root)
    return False
