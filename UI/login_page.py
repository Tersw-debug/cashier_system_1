"""Native PySide6 login page for MyShop ERP."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from UI.common import is_dark
from UI.login_ui import login_ui


class _ScaledBackground(QLabel):
    """Background image that scales to the available left-hand panel."""
    def __init__(self, image_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self._source = QPixmap(str(image_path))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #121212;")
        self._update_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self):
        if self._source.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        self.setPixmap(
            self._source.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class LoginLineEdit(QLineEdit):
    """QLineEdit with .get() to keep the existing login_ui service compatible."""
    def get(self) -> str:
        return self.text()


def show_login(root: QWidget) -> QWidget:
    """Create and install the login page in a BaseWindow/QMainWindow."""
    dark = is_dark()
    bg_color = "#121212" if dark else "#f4f6f8"
    card_color = "#1e1e1e" if dark else "#ffffff"
    text_color = "#ffffff" if dark else "#101820"
    muted_color = "#777777"

    page = QWidget()
    page.setObjectName("loginPage")
    page.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    page.setStyleSheet(f"QWidget#loginPage {{ background: {bg_color}; }}")

    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    # Left visual panel.
    left = QWidget(page)
    left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    assets_dir = Path(__file__).resolve().parent / "assets"
    background = _ScaledBackground(assets_dir / "background.png", left)
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.addWidget(background)

    # Right login panel.
    right = QWidget(page)
    right.setMinimumWidth(400)
    right.setMaximumWidth(480)
    right.setStyleSheet(f"background: {bg_color};")
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(24, 24, 24, 24)
    right_layout.addStretch(1)

    frame = QFrame(right)
    frame.setObjectName("loginCard")
    frame.setMinimumSize(400, 450)
    frame.setMaximumWidth(440)
    frame.setStyleSheet(
        f"QFrame#loginCard {{ background: {card_color}; border: 1px solid {'#333943' if dark else '#dce2e8'}; border-radius: 16px; }}"
    )
    card_layout = QVBoxLayout(frame)
    card_layout.setContentsMargins(40, 28, 40, 28)
    card_layout.setSpacing(0)

    title = QLabel("Welcome Back", frame)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"color: {text_color}; font: bold 26px 'Segoe UI'; background: transparent;")
    card_layout.addWidget(title)
    card_layout.addSpacing(8)

    subtitle = QLabel("Login to your account", frame)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setStyleSheet("color: #777777; font: 13px 'Segoe UI'; background: transparent;")
    card_layout.addWidget(subtitle)
    card_layout.addSpacing(25)

    username_label = QLabel("Username", frame)
    username_label.setStyleSheet(f"color: {muted_color}; font: bold 12px 'Segoe UI'; background: transparent;")
    card_layout.addWidget(username_label)
    card_layout.addSpacing(6)

    e1 = LoginLineEdit(frame)
    e1.setPlaceholderText("Enter your username")
    e1.setMinimumHeight(40)
    e1.setFont(title.font())
    e1.setStyleSheet(
        f"QLineEdit {{ color: {text_color}; background: {bg_color}; border: 1px solid {'#414954' if dark else '#cfd6dd'}; border-radius: 9px; padding: 0 12px; font: 13px 'Segoe UI'; }}"
        "QLineEdit:focus { border: 1px solid #4f46e5; }"
    )
    card_layout.addWidget(e1)
    card_layout.addSpacing(15)

    password_label = QLabel("Password", frame)
    password_label.setStyleSheet(f"color: {muted_color}; font: bold 12px 'Segoe UI'; background: transparent;")
    card_layout.addWidget(password_label)
    card_layout.addSpacing(6)

    e2 = LoginLineEdit(frame)
    e2.setPlaceholderText("Enter your password")
    e2.setEchoMode(QLineEdit.EchoMode.Password)
    e2.setMinimumHeight(40)
    e2.setStyleSheet(e1.styleSheet())
    card_layout.addWidget(e2)
    card_layout.addSpacing(25)

    login_button = QPushButton("Login", frame)
    login_button.setMinimumHeight(45)
    login_button.setCursor(Qt.CursorShape.PointingHandCursor)
    login_button.setStyleSheet(
        "QPushButton { color: white; background: #4f46e5; border: none; border-radius: 12px; font: bold 16px 'Segoe UI'; }"
        "QPushButton:hover { background: #4338ca; }"
        "QPushButton:pressed { background: #3730a3; }"
    )
    login_button.clicked.connect(lambda: login_ui(root, e1, e2, frame))
    card_layout.addWidget(login_button)

    right_layout.addWidget(frame, 0, Qt.AlignmentFlag.AlignHCenter)
    right_layout.addStretch(1)

    page_layout.addWidget(left, 3)
    page_layout.addWidget(right, 2)

    # QShortcut is the Qt equivalent of binding Return on the whole window.
    return_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), page)
    enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Enter), page)
    return_shortcut.activated.connect(login_button.click)
    enter_shortcut.activated.connect(login_button.click)
    page._login_shortcuts = (return_shortcut, enter_shortcut)

    if hasattr(root, "set_page"):
        root.set_page(page)
    else:
        from PySide6.QtWidgets import QMainWindow
        if isinstance(root, QMainWindow):
            root.setCentralWidget(page)
        else:
            old_layout = root.layout()
            if old_layout is None:
                old_layout = QVBoxLayout(root)
                old_layout.setContentsMargins(0, 0, 0, 0)
            else:
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            old_layout.addWidget(page)

    return page
