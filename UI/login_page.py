"""Native PySide6 login page for MyShop ERP."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from UI.common import is_dark
from UI.login_ui import login_ui


class ScaledBackground(QLabel):
    """A QLabel background that cover-fills its panel without distortion."""

    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = QPixmap(str(image_path))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setMargin(0)
        self.setText("")
        self.setStyleSheet("background-color: #121212;")
        self._update_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._source.isNull() or self.width() <= 0 or self.height() <= 0:
            return

        target_size = self.size()
        scaled = self._source.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        # KeepAspectRatioByExpanding may make the pixmap larger than the label.
        # Crop from the center so the image covers the panel without stretching.
        x = max(0, (scaled.width() - target_size.width()) // 2)
        y = max(0, (scaled.height() - target_size.height()) // 2)
        cropped = scaled.copy(
            x,
            y,
            min(target_size.width(), scaled.width() - x),
            min(target_size.height(), scaled.height() - y),
        )
        self.setPixmap(cropped)


def _clear_layout(layout) -> None:
    """Remove and schedule deletion of all widgets in an existing layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()

        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _install_page(root: QWidget, page: QWidget) -> None:
    """Install a page in the supported MyShop window and QWidget hosts."""
    set_page = getattr(root, "set_page", None)
    if callable(set_page):
        set_page(page)
        return

    if isinstance(root, QMainWindow):
        root.setCentralWidget(page)
        return

    layout = root.layout()
    if layout is None:
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
    else:
        _clear_layout(layout)

    layout.addWidget(page)


def show_login(root: QWidget) -> QWidget:
    """Create and install the login page in a BaseWindow/QMainWindow."""
    dark = is_dark()
    bg_color = "#121212" if dark else "#f4f6f8"
    card_color = "#1e1e1e" if dark else "#ffffff"
    text_color = "#ffffff" if dark else "#101820"
    muted_color = "#b8c0cc" if dark else "#667085"
    border_color = "#333943" if dark else "#dce2e8"
    input_border = "#414954" if dark else "#cfd6dd"

    page = QWidget()
    page.setObjectName("loginPage")
    page.setMinimumSize(760, 480)
    page.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    page.setStyleSheet(
        f"QWidget#loginPage {{ background-color: {bg_color}; }}"
    )

    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    # Left visual panel.
    left = QWidget(page)
    left.setObjectName("loginVisualPanel")
    left.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)

    assets_dir = Path(__file__).resolve().parent / "assets"
    background = ScaledBackground(assets_dir / "background.png", left)
    left_layout.addWidget(background)

    # Right login panel.
    right = QWidget(page)
    right.setObjectName("loginFormPanel")
    right.setMinimumWidth(400)
    right.setMaximumWidth(480)
    right.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Expanding,
    )
    right.setStyleSheet(f"background-color: {bg_color};")

    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(20, 24, 20, 24)
    right_layout.setSpacing(0)
    right_layout.addStretch(1)

    frame = QFrame(right)
    frame.setObjectName("loginCard")
    frame.setMinimumWidth(340)
    frame.setMaximumWidth(440)
    frame.setStyleSheet(
        "QFrame#loginCard {"
        f"background-color: {card_color};"
        f"border: 1px solid {border_color};"
        "border-radius: 16px;"
        "}"
    )

    card_layout = QVBoxLayout(frame)
    card_layout.setContentsMargins(32, 30, 32, 30)
    card_layout.setSpacing(0)

    title = QLabel("Welcome Back", frame)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color: {text_color}; font: bold 26px 'Segoe UI'; background: transparent;"
    )
    card_layout.addWidget(title)
    card_layout.addSpacing(8)

    subtitle = QLabel("Login to your account", frame)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setStyleSheet(
        f"color: {muted_color}; font: 13px 'Segoe UI'; background: transparent;"
    )
    card_layout.addWidget(subtitle)
    card_layout.addSpacing(25)

    username_label = QLabel("Username", frame)
    username_label.setStyleSheet(
        f"color: {muted_color}; font: bold 12px 'Segoe UI'; background: transparent;"
    )
    card_layout.addWidget(username_label)
    card_layout.addSpacing(6)

    username_input = QLineEdit(frame)
    username_input.setObjectName("usernameInput")
    username_input.setPlaceholderText("Enter your username")
    username_input.setMinimumHeight(42)
    username_input.setClearButtonEnabled(True)
    username_input.setStyleSheet(
        "QLineEdit {"
        f"color: {text_color}; background-color: {bg_color};"
        f"border: 1px solid {input_border};"
        "border-radius: 9px; padding: 0 12px; font: 13px 'Segoe UI';"
        "}"
        "QLineEdit:focus { border: 1px solid #4f46e5; }"
    )
    card_layout.addWidget(username_input)
    card_layout.addSpacing(15)

    password_label = QLabel("Password", frame)
    password_label.setStyleSheet(
        f"color: {muted_color}; font: bold 12px 'Segoe UI'; background: transparent;"
    )
    card_layout.addWidget(password_label)
    card_layout.addSpacing(6)

    password_input = QLineEdit(frame)
    password_input.setObjectName("passwordInput")
    password_input.setPlaceholderText("Enter your password")
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setMinimumHeight(42)
    password_input.setStyleSheet(username_input.styleSheet())
    card_layout.addWidget(password_input)
    card_layout.addSpacing(25)

    login_button = QPushButton("Login", frame)
    login_button.setObjectName("loginButton")
    login_button.setMinimumHeight(46)
    login_button.setCursor(Qt.CursorShape.PointingHandCursor)
    login_button.setDefault(True)
    login_button.setAutoDefault(True)
    login_button.setStyleSheet(
        "QPushButton {"
        "color: white; background-color: #4f46e5; border: none;"
        "border-radius: 12px; font: bold 16px 'Segoe UI';"
        "padding: 7px 12px;"
        "}"
        "QPushButton:hover { background-color: #4338ca; }"
        "QPushButton:pressed { background-color: #3730a3; }"
        "QPushButton:disabled { background-color: #8580df; color: #eeeeee; }"
    )
    card_layout.addWidget(login_button)

    right_layout.addWidget(frame, 0, Qt.AlignmentFlag.AlignHCenter)
    right_layout.addStretch(1)

    # Keep the image and form proportions while retaining a usable form width.
    page_layout.addWidget(left, 3)
    page_layout.addWidget(right, 2)

    # Enter works from either input, including the numeric keypad Enter key.
    login_button.clicked.connect(
        lambda _checked=False: login_ui(
            root,
            username_input,
            password_input,
            login_button=login_button,
        )
    )
    username_input.returnPressed.connect(login_button.click)
    password_input.returnPressed.connect(login_button.click)

    # Expose the controls on the page for predictable UI testing/integration.
    page.username_input = username_input
    page.password_input = password_input
    page.login_button = login_button
    page.background_label = background

    _install_page(root, page)
    username_input.setFocus()
    return page
