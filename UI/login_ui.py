"""Native PySide6 login action; authentication stays in Services.auth."""
from __future__ import annotations

import logging
import threading
from typing import Any
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QLineEdit, QMessageBox, QPushButton, QWidget

from UI.router import go_admin, go_cashier, go_login

LOGGER = logging.getLogger(__name__)


class _LoginSignals(QObject):
    """Signals used to return authentication results to the GUI thread."""

    completed = Signal(object)
    failed = Signal(str)


class _LoginController(QObject):
    """Handle worker results and perform all UI operations on the GUI thread."""

    def __init__(
        self,
        root: QWidget,
        username: str,
        entry_username: QLineEdit,
        entry_password: QLineEdit,
        login_button: QPushButton | None,
    ) -> None:
        super().__init__(root)
        self.root = root
        self.username = username
        self.entry_username = entry_username
        self.entry_password = entry_password
        self.login_button = login_button
        self.signals = _LoginSignals(self)
        self.signals.completed.connect(self.on_completed)
        self.signals.failed.connect(self.on_failed)

    def _restore_controls(self) -> None:
        """Re-enable the login form if authentication or navigation fails."""
        for widget in (
            self.entry_username,
            self.entry_password,
            self.login_button,
        ):
            if widget is None:
                continue
            try:
                widget.setEnabled(True)
            except RuntimeError:
                # The login page may have been replaced while a worker finished.
                pass

        if self.login_button is not None:
            try:
                self.login_button.setText("Login")
            except RuntimeError:
                pass

    def _finish(self) -> None:
        """Release the pending state and references held on the main window."""
        try:
            self.root._login_pending = False
            if getattr(self.root, "_login_controller", None) is self:
                self.root._login_controller = None
            if getattr(self.root, "_login_signals", None) is self.signals:
                self.root._login_signals = None
        except RuntimeError:
            # The underlying C++ window has already been destroyed.
            pass
        self.deleteLater()

    @Slot(str)
    def on_failed(self, error_message: str) -> None:
        LOGGER.error("Login authentication failed: %s", error_message)
        self._restore_controls()
        QMessageBox.critical(
            self.root,
            "تعذر تسجيل الدخول",
            "تعذر التحقق من بيانات الدخول بسبب خطأ داخلي أو مشكلة في الاتصال.\n"
            "تحقق من اتصال قاعدة البيانات ثم حاول مرة أخرى.",
        )
        self._finish()

    @Slot(object)
    def on_completed(self, result: Any) -> None:
        try:
            if not isinstance(result, tuple) or len(result) != 2:
                raise TypeError(
                    "Services.auth.login() must return (success, role); "
                    f"received {type(result).__name__}."
                )

            success, role = result
            if not success:
                self._restore_controls()
                QMessageBox.warning(
                    self.root,
                    "تسجيل الدخول",
                    "اسم المستخدم أو كلمة المرور غير صحيح.",
                )
                try:
                    self.entry_password.clear()
                    self.entry_password.setFocus()
                except RuntimeError:
                    pass
                self._finish()
                return

            normalized_role = str(role or "").strip().casefold()

            # All navigation and widget creation remain on the GUI thread.
            # All navigation and widget creation remain on the GUI thread.
            if normalized_role == "admin":
                
                from UI.ui_admin import getUsername

                getUsername(self.username)

                # Navigate to the admin dashboard.
                # Any navigation exception will be handled by the surrounding try/except.
                go_admin(self.root)

            elif normalized_role == "cashier":
                navigation_result = go_cashier(self.root, self.username)
                if navigation_result is False:
                    QMessageBox.warning(
                        self.root,
                        "تعذر فتح واجهة الكاشير",
                        "تعذر تهيئة واجهة الكاشير. تحقق من إعدادات المخزن وطرق الدفع.",
                    )
                    go_login(self.root)

            else:
                QMessageBox.critical(
                    self.root,
                    "خطأ في الصلاحيات",
                    f"الدور المرتبط بهذا الحساب غير معروف: {normalized_role or 'غير محدد'}",
                )
                go_login(self.root)

            self._finish()

        except Exception as exc:
            LOGGER.exception("Post-authentication navigation failed")
            self._restore_controls()
            QMessageBox.critical(
                self.root,
                "تعذر فتح الصفحة",
                "تم التحقق من الحساب، لكن تعذر فتح الواجهة.\n"
                f"التفاصيل: {type(exc).__name__}: {exc}",
            )
            self._finish()


def _entry_text(entry: QLineEdit) -> str:
    """Read a native Qt line edit; legacy Tk-style widgets are not supported."""
    if not isinstance(entry, QLineEdit):
        raise TypeError(
            f"Expected PySide6 QLineEdit, received {type(entry).__name__}."
        )
    return entry.text()


def _resolve_login_button(
    candidate: QWidget | QPushButton | None,
) -> QPushButton | None:
    """Accept an explicit button or find it in an older call's card argument."""
    if isinstance(candidate, QPushButton):
        return candidate
    if isinstance(candidate, QWidget):
        for button in candidate.findChildren(QPushButton):
            if button.objectName() == "loginButton" or button.text().strip().casefold() == "login":
                return button
    return None


def login_ui(
    root: QWidget,
    entry_username: QLineEdit,
    entry_password: QLineEdit,
    login_button: QWidget | QPushButton | None = None,
    *,
    login_card: QWidget | None = None,
) -> bool:
    """Start background authentication and return whether it was started.

    `Services.auth.login()` performs the authentication/database work. The UI
    does not issue SQL or open database connections directly. Its contract is
    to return `(success, role)`.

    The fourth positional argument may be either the login QPushButton or the
    older login-card QWidget, preserving compatibility with existing callers.
    """
    if getattr(root, "_login_pending", False):
        return False

    username = _entry_text(entry_username).strip()
    password = _entry_text(entry_password)

    if not username or not password:
        QMessageBox.warning(
            root,
            "بيانات الدخول",
            "أدخل اسم المستخدم وكلمة المرور.",
        )
        if not username:
            entry_username.setFocus()
        else:
            entry_password.setFocus()
        return False

    candidate = login_card if login_card is not None else login_button
    resolved_button = _resolve_login_button(candidate)

    # Mark pending before starting the worker so rapid repeated clicks cannot
    # launch concurrent authentication requests.
    root._login_pending = True
    entry_username.setEnabled(False)
    entry_password.setEnabled(False)
    if resolved_button is not None:
        resolved_button.setEnabled(False)
        resolved_button.setText("Signing in…")

    controller = _LoginController(
        root,
        username,
        entry_username,
        entry_password,
        resolved_button,
    )
    root._login_controller = controller
    root._login_signals = controller.signals

    def authenticate_in_background() -> None:
        try:
            # Import inside the worker to keep authentication dependencies out
            # of the UI module's import-time dependency graph.
            from Services.auth import login as authenticate

            result = authenticate(username, password)
        except Exception as exc:
            LOGGER.exception("Authentication service raised an exception")
            try:
                controller.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            except RuntimeError:
                # The application may have closed while authentication ran.
                pass
        else:
            try:
                controller.signals.completed.emit(result)
            except RuntimeError:
                pass

    worker = threading.Thread(
        target=authenticate_in_background,
        name="MyShop-Login-Authentication",
        daemon=True,
    )
    root._login_thread = worker

    try:
        worker.start()
    except Exception as exc:
        LOGGER.exception("Could not start the login worker thread")
        controller._restore_controls()
        controller._finish()
        QMessageBox.critical(
            root,
            "تعذر بدء تسجيل الدخول",
            f"تعذر تشغيل عملية تسجيل الدخول: {type(exc).__name__}: {exc}",
        )
        return False

    return True
