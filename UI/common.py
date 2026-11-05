"""Shared PySide6 application, palette, and main-window infrastructure."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget


def _palette(dark: bool) -> QPalette:
    palette = QPalette()
    if dark:
        window, base, text = "#121212", "#1e1e1e", "#ffffff"
        button, muted = "#2b2b2b", "#aab4be"
    else:
        window, base, text = "#f4f6f8", "#ffffff", "#101820"
        button, muted = "#e6e9ec", "#59636e"

    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(base))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(window))
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.Button, QColor(button))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(base))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(muted))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#265777"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return palette


def init_app(argv: list[str] | None = None, dark: bool = True) -> QApplication:
    """Return the single QApplication and apply the global application style."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv or [])

    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setFont(QFont("Segoe UI", 10))
    app.setPalette(_palette(dark))
    app.setQuitOnLastWindowClosed(True)
    return app


def is_dark() -> bool:
    app = QApplication.instance()
    if app is None:
        return True
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


class BaseWindow(QMainWindow):
    """One persistent top-level window whose central QWidget is the active page."""

    def __init__(self, title: str = "System", fullscreen: bool = True):
        if QApplication.instance() is None:
            raise RuntimeError("Call init_app() before constructing BaseWindow")
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(900, 600)
        self._start_maximized = bool(fullscreen)
        if not fullscreen:
            self.resize(1100, 700)

        self._fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self._fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape_shortcut.activated.connect(self.exit_fullscreen)

    def set_page(self, page: QWidget) -> None:
        """Replace the central page without creating or showing another window."""
        if page is self.centralWidget():
            return

        old_page = self.takeCentralWidget()
        self.setCentralWidget(page)
        if old_page is not None:
            old_page.deleteLater()

    def show(self) -> None:
        if self._start_maximized:
            super().showMaximized()
        else:
            super().show()

    def toggle_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def exit_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()

    def mainloop(self) -> int:
        """Compatibility method; prefer QApplication.exec() in new startup code."""
        self.show()
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication is not initialized")
        return app.exec()
