from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import traceback
from pathlib import Path
from tempfile import gettempdir
from typing import TextIO


# ============================================================
# Configuration
# ============================================================

SEED_CATALOG_FLAG = "--seed-print-catalog-once"
SEED_MARKER_KEY = "seed_print_catalog_v1"
SEED_LOCK_NAME = "myshop_catalog_seed_v1"
SEED_LOCK_TIMEOUT_SECONDS = 10

SEED_LOG_FILENAME = "seed_print_catalog_once.log"
STARTUP_LOG_FILENAME = "startup.log"

LOGGER = logging.getLogger("myshop.startup")
_LOG_PATH: Path | None = None
_QT_MESSAGE_HANDLER = None


# ============================================================
# Paths and persistent diagnostics
# ============================================================
def _application_directory() -> Path:
    """Return the executable directory or the source directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_directory() -> Path | None:
    """Return PyInstaller's temporary bundle directory, if available."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    return Path(bundle_dir) if bundle_dir else None


def _diagnostic_directory() -> Path:
    """Choose a writable per-user log directory, with safe fallbacks."""
    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "MyShop" / "logs")

    candidates.extend(
        [
            Path.home() / "AppData" / "Local" / "MyShop" / "logs",
            _application_directory() / "logs",
            Path(gettempdir()) / "MyShop" / "logs",
        ]
    )

    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return directory
        except OSError:
            continue

    return Path(gettempdir())


def _configure_diagnostics() -> Path | None:
    """Start an always-on startup log before importing application modules."""
    global _LOG_PATH
    try:
        _LOG_PATH = _diagnostic_directory() / STARTUP_LOG_FILENAME
        for old_handler in list(LOGGER.handlers):
            try:
                old_handler.close()
            except Exception:
                pass
        LOGGER.handlers.clear()

        handler = logging.FileHandler(
            _LOG_PATH,
            mode="a",
            encoding="utf-8",
            delay=False,
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        LOGGER.addHandler(handler)
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.propagate = False

        LOGGER.info("\n%s", "=" * 76)
        LOGGER.info("MyShop startup entered")
        LOGGER.info("Python: %s", sys.version.replace("\n", " "))
        LOGGER.info("Executable: %s", sys.executable)
        LOGGER.info("Application directory: %s", _application_directory())
        LOGGER.info("Frozen build: %s", bool(getattr(sys, "frozen", False)))
        LOGGER.info("Arguments: %r", sys.argv)
        LOGGER.info("Diagnostic log: %s", _LOG_PATH)
        return _LOG_PATH
    except Exception:
        _LOG_PATH = None
        return None


def _log_stage(message: str) -> None:
    """Log and flush a startup checkpoint."""
    if LOGGER.handlers:
        LOGGER.info("STAGE: %s", message)
        for handler in LOGGER.handlers:
            try:
                handler.flush()
            except Exception:
                pass


def _log_exception(stage: str, exc: BaseException) -> None:
    """Persist an exception with its full traceback."""
    if LOGGER.handlers:
        LOGGER.error(
            "FAILED at stage: %s | %s: %s",
            stage,
            type(exc).__name__,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        for handler in LOGGER.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        return

    try:
        path = _diagnostic_directory() / STARTUP_LOG_FILENAME
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"\nFAILED at stage: {stage}\n")
            traceback.print_exception(
                type(exc), exc, exc.__traceback__, file=stream
            )
    except Exception:
        pass


def _install_exception_hooks() -> None:
    """Log uncaught main-thread and worker-thread Python exceptions."""
    previous_sys_hook = sys.excepthook

    def sys_exception_hook(exc_type, exc_value, exc_tb):
        if LOGGER.handlers:
            LOGGER.critical(
                "Uncaught main-thread exception",
                exc_info=(exc_type, exc_value, exc_tb),
            )
        try:
            previous_sys_hook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = sys_exception_hook

    if hasattr(threading, "excepthook"):
        previous_thread_hook = threading.excepthook

        def thread_exception_hook(args):
            if LOGGER.handlers:
                LOGGER.critical(
                    "Uncaught worker-thread exception in %s",
                    args.thread.name if args.thread else "unknown",
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            try:
                previous_thread_hook(args)
            except Exception:
                pass

        threading.excepthook = thread_exception_hook


def _write_diagnostic(message: str) -> None:
    """Write a message even when a windowed executable has no stderr."""
    if LOGGER.handlers:
        LOGGER.error("%s", message)
        return

    for stream in (sys.stderr, sys.__stderr__):
        if stream is None:
            continue
        try:
            stream.write(message.rstrip() + "\n")
            stream.flush()
            return
        except Exception:
            continue

    try:
        path = _diagnostic_directory() / STARTUP_LOG_FILENAME
        with path.open("a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")
    except OSError:
        pass


def _show_native_error(title: str, message: str) -> None:
    """Show a Windows error dialog when Qt is not available yet."""
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    _write_diagnostic(f"{title}: {message}")


def _show_startup_error(
    title: str,
    exc: BaseException,
    *,
    parent=None,
    seed_mode: bool = False,
) -> None:
    """Show an error dialog when possible and preserve the traceback in log."""
    message = f"{type(exc).__name__}: {exc}"
    log_location = str(_LOG_PATH) if _LOG_PATH else "startup log unavailable"
    visible_message = f"{message}\n\nDiagnostic log:\n{log_location}"

    if seed_mode:
        _write_diagnostic(f"{title}: {message}")
        return

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is not None:
            QMessageBox.critical(
                parent,
                title,
                visible_message,
                QMessageBox.StandardButton.Ok,
            )
            return
    except Exception as dialog_exc:
        _write_diagnostic(
            "Could not create Qt error dialog: "
            f"{type(dialog_exc).__name__}: {dialog_exc}"
        )

    _show_native_error(title, visible_message)


# ============================================================
# Qt diagnostics
# ============================================================
def _install_qt_message_handler() -> None:
    """Route Qt warnings and critical messages into startup.log."""
    global _QT_MESSAGE_HANDLER
    from PySide6.QtCore import qInstallMessageHandler

    def handler(message_type, context, message):
        if LOGGER.handlers:
            LOGGER.warning(
                "Qt message (%s) %s | %s:%s | category=%s",
                message_type,
                message,
                getattr(context, "file", None),
                getattr(context, "line", None),
                getattr(context, "category", None),
            )

    _QT_MESSAGE_HANDLER = handler  # Keep a strong reference to the callback.
    qInstallMessageHandler(_QT_MESSAGE_HANDLER)


# ============================================================
# Seed-mode logging
# ============================================================
def _configure_seed_logging() -> TextIO:
    """Redirect seed-mode stdout/stderr to a dedicated log file."""
    candidates = [
        _application_directory() / SEED_LOG_FILENAME,
        _diagnostic_directory() / SEED_LOG_FILENAME,
    ]
    last_error: OSError | None = None
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open("w", encoding="utf-8", buffering=1)
            sys.stdout = stream
            sys.stderr = stream
            print(f"MyShop catalog seed log: {path}")
            print("=" * 60)
            return stream
        except OSError as exc:
            last_error = exc
    raise OSError(f"Could not create the seed log. {last_error}")


def _restore_seed_logging(
    stream: TextIO,
    original_stdout,
    original_stderr,
) -> None:
    """Restore the original process streams and close the seed log."""
    try:
        stream.flush()
    except Exception:
        pass
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        try:
            stream.close()
        except Exception:
            pass




# ============================================================
# Catalog seeding
# ============================================================
def _set_seed_marker(cursor, value: str) -> None:
    """Persist the catalog seed marker using MySQL-compatible parameters."""
    cursor.execute(
        """
        INSERT INTO settings (`key`, `value`)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
            `value` = %s,
            updated_at = CURRENT_TIMESTAMP
        """,
        (SEED_MARKER_KEY, value, value),
    )


def run_catalog_seed_once(database) -> None:
    """Seed the print catalog once under a MySQL advisory lock.

    The marker deliberately remains 'running' if seeding fails. Do not reset it
    automatically: inspect products and opening-stock movements before retrying.
    """
    from Services import admin_service as admin_svc
    from Services.seed_catalog import seed_print_catalog

    connection = database.connect()
    cursor = None
    lock_acquired = False
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT GET_LOCK(%s, %s)",
            (SEED_LOCK_NAME, SEED_LOCK_TIMEOUT_SECONDS),
        )
        lock_row = cursor.fetchone()
        lock_status = lock_row[0] if lock_row else None
        if lock_status != 1:
            raise RuntimeError(
                "تعذر الحصول على قفل تجهيز الكتالوج. "
                "قد تكون عملية تجهيز أخرى قيد التشغيل."
            )
        lock_acquired = True

        cursor.execute(
            "SELECT `value` FROM settings WHERE `key` = %s LIMIT 1",
            (SEED_MARKER_KEY,),
        )
        marker_row = cursor.fetchone()
        marker_value = (
            str(marker_row[0])
            if marker_row and marker_row[0] is not None
            else None
        )

        if marker_value == "completed":
            print("Catalog seed has already completed. No changes were made.")
            return
        if marker_value == "running":
            raise RuntimeError(
                "يوجد تسجيل سابق بأن تجهيز الكتالوج بدأ ولم يكتمل. "
                "لم تتم إعادة التشغيل تلقائيًا لتجنب تخطي منتجات قد تكون "
                "بلا مخزون افتتاحي. افحص المنتجات وحركات المخزون أولًا، "
                f"ثم عالج المفتاح {SEED_MARKER_KEY!r} يدويًا إذا لزم الأمر."
            )

        if admin_svc.get_username_id("admin") is None:
            raise RuntimeError(
                "لم يتم العثور على حساب admin. افتح التطبيق بصورة طبيعية "
                "وتأكد من إنشاء حساب المدير قبل تشغيل تجهيز الكتالوج."
            )

        # Database connections use autocommit=True; the marker is committed
        # before invoking the seed service, which may use its own connections.
        _set_seed_marker(cursor, "running")
        result = seed_print_catalog(username="admin")
        if not isinstance(result, dict):
            raise TypeError(
                "seed_print_catalog() must return a dictionary, "
                f"received {type(result).__name__}."
            )
        _set_seed_marker(cursor, "completed")

        print("\nCatalog seed completed successfully.")
        print(f"Created products: {result.get('created', 0)}")
        print(f"Skipped existing products: {result.get('skipped', 0)}")
        print(f"Products with opening stock: {result.get('with_stock', 0)}")
    finally:
        try:
            if lock_acquired and cursor is not None:
                try:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (SEED_LOCK_NAME,))
                    cursor.fetchone()
                except Exception:
                    LOGGER.exception("Could not explicitly release seed lock")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            connection.close()


# ============================================================
# Qt application and startup window
# ============================================================
def _initialize_qt_application(args: list[str]):
    """Create/configure the one QApplication used by the GUI process."""
    from PySide6.QtWidgets import QApplication
    from UI.common import init_app

    app = init_app(args, dark=True)
    if app is None:
        app = QApplication.instance()
    if app is None:
        raise RuntimeError("UI.common.init_app() did not create QApplication.")
    if not isinstance(app, QApplication):
        raise TypeError(
            "init_app() must return QApplication; "
            f"received {type(app).__name__}."
        )
    if QApplication.instance() is not app:
        raise RuntimeError("The returned QApplication is not the active instance.")
    return app


def _create_startup_window():
    """Show a visible startup page before database/bootstrap work begins."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QApplication
    from UI.basewindow import BaseWindow

    root = BaseWindow("MyShop ERP", fullscreen=True)
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 32, 32, 32)

    label = QLabel("جاري تشغيل MyShop ERP...\nPlease wait")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        "QLabel { font-size: 20px; font-weight: 600; padding: 24px; }"
    )
    layout.addStretch(1)
    layout.addWidget(label)
    layout.addStretch(1)

    root.set_page(page)
    root.show()
    QApplication.processEvents()
    return root


def _show_first_admin_credentials(first_password: str, parent=None) -> None:
    """Display the generated administrator password; copy only on user action."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QDialogButtonBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )

    dialog = QDialog(parent)
    dialog.setWindowTitle("First-run administrator account")
    dialog.setMinimumWidth(460)
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(22, 20, 22, 18)
    layout.setSpacing(12)

    message = QLabel(
        "تم إنشاء حساب المدير بنجاح. احتفظ بكلمة المرور؛ "
        "سيُطلب منك تغييرها عند أول تسجيل دخول."
    )
    message.setWordWrap(True)
    layout.addWidget(message)

    username = QLineEdit("admin", dialog)
    username.setReadOnly(True)
    password = QLineEdit(first_password, dialog)
    password.setReadOnly(True)
    password.setEchoMode(QLineEdit.EchoMode.Normal)

    from PySide6.QtWidgets import QFormLayout
    form = QFormLayout()
    form.addRow("Username:", username)
    form.addRow("Password:", password)
    layout.addLayout(form)

    action_row = QHBoxLayout()
    copy_button = QPushButton("Copy password", dialog)
    copy_status = QLabel("", dialog)
    copy_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    action_row.addWidget(copy_button)
    action_row.addWidget(copy_status, 1)
    layout.addLayout(action_row)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)

    def copy_password() -> None:
        try:
            QApplication.clipboard().setText(first_password)
            copy_status.setText("Copied")
        except Exception as exc:
            QMessageBox.warning(
                dialog,
                "Clipboard unavailable",
                f"Could not copy the password: {type(exc).__name__}: {exc}",
            )

    copy_button.clicked.connect(copy_password)
    dialog.exec()


# ============================================================
# Asynchronous database/bootstrap worker
# ============================================================
from PySide6.QtCore import QObject, QThread, Signal, Slot


class _StartupWorker(QObject):
    """Run database initialization and first-admin bootstrap off the GUI thread."""

    succeeded = Signal(object)  # Generated first-admin password, or None.
    failed = Signal(object)     # Original exception object.
    finished = Signal()

    def __init__(self, database):
        super().__init__()
        self.database = database

    @Slot()
    def run(self) -> None:
        try:
            _log_stage("background startup: db.initialize() started")
            self.database.initialize()
            _log_stage("background startup: db.initialize() completed")
            from Services.bootstrap import ensure_first_admin
            _log_stage("ensure_first_admin() started")
            first_password = ensure_first_admin()
            _log_stage("ensure_first_admin() completed")
            self.succeeded.emit(first_password)
        except Exception as exc:
            LOGGER.exception("Background startup failed")
            self.failed.emit(exc)
        finally:
            self.finished.emit()


class _StartupController(QObject):
    """Handle bootstrap results on the GUI thread and keep worker objects alive."""

    def __init__(self, root, app, thread: QThread, worker: _StartupWorker):
        super().__init__(root)
        self.root = root
        self.app = app
        self.thread = thread
        self.worker = worker

    @Slot(object)
    def on_succeeded(self, first_password) -> None:
        try:
            if first_password:
                _log_stage("showing first-admin credentials dialog")
                _show_first_admin_credentials(str(first_password), parent=self.root)
                _log_stage("first-admin credentials dialog closed")

            _log_stage("installing login page")
            from UI.router import go_login
            go_login(self.root)
            _log_stage("login page installed")
        except Exception as exc:
            _log_exception("finalizing GUI startup", exc)
            _show_startup_error(
                "MyShop startup error", exc, parent=self.root, seed_mode=False
            )
            self.app.exit(1)

    @Slot(object)
    def on_failed(self, exc) -> None:
        if not isinstance(exc, BaseException):
            exc = RuntimeError(str(exc))
        _log_exception("database/bootstrap initialization", exc)
        _show_startup_error(
            "MyShop startup error", exc, parent=self.root, seed_mode=False
        )
        self.app.exit(1)


# ============================================================
# Seed-only startup
# ============================================================
def _run_seed_mode() -> int:
    """Initialize database and run catalog seed without opening GUI prompts."""
    _log_stage("seed mode: importing Database.Schema")
    from Database.Schema import db

    # Seed mode is a console utility. Missing credentials must fail explicitly,
    # rather than attempting to display a Qt credential dialog.
    db._key_store.allow_prompt = False
    _log_stage("seed mode: Database.Schema imported")
    _log_stage("seed mode: db.initialize() started")
    db.initialize()
    _log_stage("seed mode: db.initialize() completed")

    _log_stage("seed mode: catalog seeding started")
    run_catalog_seed_once(db)
    _log_stage("seed mode: catalog seeding completed")
    return 0


# ============================================================
# Normal GUI startup
# ============================================================
def _run_gui_mode(args: list[str]) -> int:
    """Initialize Qt, resolve credentials, then bootstrap DB on a worker thread."""
    stage = "initializing QApplication"
    root = None
    thread = None

    try:
        _log_stage(stage)
        app = _initialize_qt_application(args)
        _install_qt_message_handler()
        app.aboutToQuit.connect(lambda: LOGGER.info("Qt aboutToQuit emitted"))
        _log_stage("QApplication initialized")

        stage = "creating visible startup window"
        _log_stage(stage)
        root = _create_startup_window()
        _log_stage("startup window shown and initial paint processed")

        stage = "importing Database.Schema"
        _log_stage(stage)
        from Database.Schema import db
        _log_stage("Database.Schema imported")

        # Credential prompting (when needed) must happen on the Qt GUI thread.
        # Once the pair is cached, the worker can open its own PyMySQL connections.
        stage = "resolving database credentials"
        _log_stage(stage)
        db._resolve_credentials()
        _log_stage("database credentials resolved")

        stage = "starting asynchronous database/bootstrap worker"
        _log_stage(stage)
        thread = QThread(app)
        worker = _StartupWorker(db)
        worker.moveToThread(thread)
        controller = _StartupController(root, app, thread, worker)

        thread.started.connect(worker.run)
        worker.succeeded.connect(controller.on_succeeded)
        worker.failed.connect(controller.on_failed)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)

        # Strong references prevent Python wrappers from being collected while
        # the Qt worker is still running.
        root._startup_thread = thread
        root._startup_worker = worker
        root._startup_controller = controller

        thread.start()
        _log_stage("startup worker started")

        stage = "entering QApplication event loop"
        _log_stage(stage)
        exit_code = app.exec()
        _log_stage(f"QApplication event loop exited with code {exit_code}")

        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()
        return int(exit_code)

    except BaseException as exc:
        _log_exception(stage, exc)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _show_startup_error(
            "MyShop startup error", exc, parent=root, seed_mode=False
        )
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()
        return 1


# ============================================================
# Main entry point
# ============================================================
def main(argv: list[str] | None = None) -> int:
    """Run normal ERP GUI mode or standalone catalog seed mode."""
    _configure_diagnostics()
    _install_exception_hooks()

    args = list(sys.argv if argv is None else argv)
    seed_mode = SEED_CATALOG_FLAG in args
    _log_stage("arguments parsed")
    _log_stage(f"mode selected: {'seed' if seed_mode else 'GUI'}")

    seed_log_stream: TextIO | None = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    if seed_mode:
        try:
            seed_log_stream = _configure_seed_logging()
            _log_stage("seed log configured")
        except Exception as exc:
            _log_exception("configuring seed log", exc)
            _show_startup_error(
                "Catalog seed logging error", exc, seed_mode=True
            )
            return 1

    try:
        if seed_mode:
            try:
                return _run_seed_mode()
            except BaseException as exc:
                _log_exception("seed startup", exc)
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                _show_startup_error("Catalog seed failed", exc, seed_mode=True)
                return 1

        return _run_gui_mode(args)

    except BaseException as exc:
        _log_exception("unhandled main() failure", exc)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _show_startup_error(
            "MyShop startup error", exc, seed_mode=seed_mode
        )
        return 1
    finally:
        if seed_log_stream is not None:
            _restore_seed_logging(
                seed_log_stream,
                original_stdout,
                original_stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())


# Windows PyInstaller example:
# pyinstaller --noconfirm --clean --onefile --console --name program ^
# --distpath output --workpath build ^
# --add-data "UI\assets;UI\assets" ^
# --collect-all PySide6 --collect-all keyring main.py
