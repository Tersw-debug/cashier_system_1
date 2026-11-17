"""MyShop ERP database credential management.

Credential lookup order:
    1. Windows Credential Manager (through ``keyring``).
    2. A complete username/password pair from process environment variables.
    3. A complete username/password pair from the application ``.env`` file.
    4. A native PySide6 credential dialog (unless prompting is disabled).

Connection settings (host, port and database name) are read separately by
``Database.Schema``. Environment variables take precedence over ``.env``.

Supported username variables:
    MYSQL_USERNAME, MYSHOP_DB_USERNAME, MYSHOP_DB_USER, MYSQL_USER

Supported password variables:
    MYSHOP_DB_PASSWORD, MYSQL_PASSWORD

For a non-interactive process, set MYSHOP_ALLOW_DB_CREDENTIAL_PROMPT=0 and
provide credentials through Credential Manager or a complete environment pair.
"""
from __future__ import annotations

import getpass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

try:
    import keyring
except ImportError:  # Environment/.env credentials can still be used.
    keyring = None  # type: ignore[assignment]


_LOG = logging.getLogger(__name__)
_USERNAME_KEYS = (
    "MYSQL_USERNAME",
    "MYSHOP_DB_USERNAME",
    "MYSHOP_DB_USER",
    "MYSQL_USER",
)
_PASSWORD_KEYS = (
    "MYSHOP_DB_PASSWORD",
    "MYSQL_PASSWORD",
)

# Keep an internally-created QApplication alive if this module is used by a
# command-line utility that needs to display the credential dialog.
_OWNED_QAPPLICATION = None


class KeyStoreError(RuntimeError):
    """Raised when usable MySQL credentials cannot be obtained."""


class KeyStore:
    """Load and save a matched MySQL username/password pair.

    New Credential Manager entries store both values together in one versioned
    JSON secret. Legacy username-keyed entries are still read and migrated.
    """

    CREDENTIAL_ACCOUNT = "mysql-database-credentials-v1"
    DEFAULT_USERNAME = "ERP"

    def __init__(
        self,
        service: str = "ShopERP",
        account: str = DEFAULT_USERNAME,
        env_file: str | Path | None = None,
        allow_prompt: bool | None = None,
    ) -> None:
        self.service = service
        # Older releases used the MySQL username as the keyring account name.
        self.account = account
        self.project_root = self._application_directory()
        configured_env_file = Path(env_file).expanduser() if env_file else Path(".env")
        if configured_env_file.is_absolute():
            self.env_file = configured_env_file.resolve()
        else:
            self.env_file = (self.project_root / configured_env_file).resolve()
        self.allow_prompt = (
            self._prompt_setting() if allow_prompt is None else bool(allow_prompt)
        )
        self._credentials_cache: tuple[str, str] | None = None

    @staticmethod
    def _application_directory() -> Path:
        """Return the EXE directory or source project root."""
        if getattr(sys, "frozen", False):
            # PyInstaller one-file builds extract __file__ into _MEIPASS; the
            # user's .env belongs beside the executable instead.
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def _prompt_setting() -> bool:
        value = os.environ.get(
            "MYSHOP_ALLOW_DB_CREDENTIAL_PROMPT", "1"
        ).strip().lower()
        return value not in {"0", "false", "no", "off"}

    @staticmethod
    def _first_value(
        values: Mapping[str, object],
        names: tuple[str, ...],
        *,
        preserve_whitespace: bool = False,
    ) -> str | None:
        """Return the first non-empty value for the supplied aliases.

        Password values can legitimately contain leading/trailing spaces, so
        callers may request that whitespace be preserved.
        """
        for name in names:
            raw = values.get(name)
            if raw is None:
                continue
            value = str(raw) if preserve_whitespace else str(raw).strip()
            if value != "" and (preserve_whitespace or bool(value.strip())):
                return value
        return None

    @staticmethod
    def _read_dotenv_file(path: Path) -> dict[str, str]:
        """Read supported settings without mutating ``os.environ``."""
        if not path.is_file():
            return {}

        try:
            file_values = dotenv_values(path, interpolate=False)
        except (OSError, UnicodeError, ValueError) as exc:
            _LOG.warning("Could not read .env file %s: %s", path, exc)
            return {}

        result: dict[str, str] = {}
        aliases = (
            ("username", _USERNAME_KEYS),
            ("password", _PASSWORD_KEYS),
            ("port", ("MYSHOP_DB_PORT",)),
            ("host", ("MYSHOP_DB_HOST",)),
            ("db_name", ("MYSHOP_DB_NAME", "MYSQL_DATABASE")),
        )
        for output_name, names in aliases:
            value = KeyStore._first_value(
                file_values,
                names,
                preserve_whitespace=(output_name == "password"),
            )
            if value is not None:
                result[output_name] = value

        result.setdefault("port", "3306")
        result.setdefault("host", "localhost")
        result.setdefault("db_name", "myshop")
        return result

    def _process_credentials(self) -> tuple[str | None, str | None]:
        return (
            self._first_value(os.environ, _USERNAME_KEYS),
            self._first_value(
                os.environ, _PASSWORD_KEYS, preserve_whitespace=True
            ),
        )

    def _file_credentials(self) -> tuple[str | None, str | None]:
        values = self._read_dotenv_file(self.env_file)
        return values.get("username"), values.get("password")

    def _read_keyring_secret(self, account: str) -> str | None:
        if keyring is None:
            return None
        try:
            value = keyring.get_password(self.service, account)
            return value if value else None
        except Exception as exc:
            # Different keyring backends raise different exception classes.
            _LOG.debug(
                "Credential Manager read failed for account %s: %s",
                account,
                type(exc).__name__,
            )
            return None

    def _get_keyring_credentials(
        self,
        username_hints: tuple[str | None, ...],
    ) -> tuple[str, str] | None:
        # Preferred format: username and password in the same versioned secret.
        raw = self._read_keyring_secret(self.CREDENTIAL_ACCOUNT)
        if raw:
            try:
                saved = json.loads(raw)
                if not isinstance(saved, dict):
                    raise TypeError("Credential payload must be a JSON object")
                username = str(saved.get("username", "")).strip()
                password = str(saved.get("password", ""))
                if username and password:
                    return username, password
            except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                _LOG.warning(
                    "Stored MyShop database credential entry is malformed."
                )

        # Backward compatibility: previous releases stored just the password
        # under the username (or the old default account).
        candidates: list[str] = []
        for candidate in (*username_hints, self.account, self.DEFAULT_USERNAME):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        for username in candidates:
            password = self._read_keyring_secret(username)
            if password:
                try:
                    self._save_keyring_credentials(username, password)
                except (KeyStoreError, ValueError):
                    # The legacy entry remains usable for this process.
                    _LOG.debug("Could not migrate a legacy Credential Manager entry.")
                return username, password
        return None

    def _save_keyring_credentials(self, username: str, password: str) -> None:
        username = (username or "").strip()
        if not username:
            raise ValueError("The MySQL username cannot be empty.")
        if not password:
            raise ValueError("The MySQL password cannot be empty.")
        if keyring is None:
            raise KeyStoreError(
                "The 'keyring' package is not installed, so credentials cannot be "
                "saved to the OS credential store. Install it with: pip install keyring"
            )

        secret = json.dumps(
            {"version": 1, "username": username, "password": password},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            keyring.set_password(self.service, self.CREDENTIAL_ACCOUNT, secret)
        except Exception as exc:
            raise KeyStoreError(
                "Could not save MySQL credentials in the OS credential store. "
                "Check that Windows Credential Manager is available for the "
                "Windows account running MyShop."
            ) from exc

    def set_credentials(self, username: str, password: str) -> None:
        """Persist both credentials and cache the matched pair."""
        username = (username or "").strip()
        if not username:
            raise ValueError("The MySQL username cannot be empty.")
        if not password:
            raise ValueError("The MySQL password cannot be empty.")
        self._save_keyring_credentials(username, password)
        self.account = username
        self._credentials_cache = (username, password)

    def set_password(self, password: str, username: str | None = None) -> None:
        """Compatibility API; prefer ``set_credentials``."""
        process_username, _ = self._process_credentials()
        file_username, _ = self._file_credentials()
        resolved_username = (
            username or process_username or file_username or self.account
        )
        self.set_credentials(resolved_username, password)

    def delete_credentials(self) -> bool:
        """Delete the new-format secret and known legacy username-keyed secrets.

        Returns True if at least one entry was deleted. Missing entries are not
        errors. Unknown Credential Manager failures are reported to the caller.
        """
        if keyring is None:
            raise KeyStoreError("The 'keyring' package is not installed.")

        process_username, _ = self._process_credentials()
        file_username, _ = self._file_credentials()
        # Also remove a legacy username-keyed entry matching the username in
        # the current versioned payload, if that payload is still readable.
        new_secret = self._read_keyring_secret(self.CREDENTIAL_ACCOUNT)
        stored_username = None
        if new_secret:
            try:
                payload = json.loads(new_secret)
                if isinstance(payload, dict):
                    stored_username = str(payload.get("username", "")).strip() or None
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        candidates: list[str] = []
        for candidate in (
            stored_username,
            self._credentials_cache[0] if self._credentials_cache else None,
            self.account,
            process_username,
            file_username,
            self.DEFAULT_USERNAME,
        ):
            if candidate and candidate != self.CREDENTIAL_ACCOUNT and candidate not in candidates:
                candidates.append(candidate)

        deleted_any = False
        accounts = [self.CREDENTIAL_ACCOUNT, *candidates]
        try:
            for account in accounts:
                try:
                    keyring.delete_password(self.service, account)
                    deleted_any = True
                except keyring.errors.PasswordDeleteError:
                    # The entry does not exist (or the backend reports it as absent).
                    continue
                except Exception as exc:
                    raise KeyStoreError(
                        f"Could not delete MySQL credentials for Credential Manager "
                        f"entry {account!r}."
                    ) from exc
        finally:
            self._credentials_cache = None
        return deleted_any

    def _prompt_for_credentials(
        self,
        username_hint: str | None = None,
        parent=None,
    ) -> tuple[str, str]:
        """Collect credentials in a native, modal PySide6 dialog."""
        if not self.allow_prompt:
            raise KeyStoreError(
                "Interactive credential prompting is disabled. Configure "
                "Credential Manager or a complete environment/.env credential pair."
            )

        try:
            from PySide6.QtCore import Qt, QThread
            from PySide6.QtWidgets import (
                QApplication,
                QDialog,
                QDialogButtonBox,
                QFormLayout,
                QLabel,
                QLineEdit,
                QMessageBox,
                QVBoxLayout,
                QWidget,
            )
        except Exception as exc:
            raise KeyStoreError(
                "Could not load the native PySide6 credential dialog."
            ) from exc

        global _OWNED_QAPPLICATION
        app = QApplication.instance()
        if app is None:
            try:
                _OWNED_QAPPLICATION = QApplication(sys.argv[:1])
                app = _OWNED_QAPPLICATION
            except Exception as exc:
                raise KeyStoreError(
                    "No QApplication is available to display the database "
                    "credential dialog. Start the Qt application first or "
                    "configure non-interactive credentials."
                ) from exc

        if QThread.currentThread() != app.thread():
            raise KeyStoreError(
                "The database credential dialog must be opened on the Qt GUI thread."
            )

        if parent is None:
            parent = app.activeWindow()
        if parent is not None and not isinstance(parent, QWidget):
            parent = None

        dialog = QDialog(parent)
        dialog.setWindowTitle("MyShop — MySQL Database Credentials")
        dialog.setModal(True)
        dialog.setMinimumWidth(430)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        description = QLabel(
            "Database credentials were not found. Enter the MySQL account "
            "used by MyShop. Credentials will be saved in Windows Credential "
            "Manager when it is available."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        username_edit = QLineEdit(dialog)
        username_edit.setText(username_hint or self.account or self.DEFAULT_USERNAME)
        username_edit.setPlaceholderText("MySQL username")
        password_edit = QLineEdit(dialog)
        password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        password_edit.setPlaceholderText("MySQL password")
        form.addRow("MySQL username:", username_edit)
        form.addRow("MySQL password:", password_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save,
            parent=dialog,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setDefault(True)
        layout.addWidget(buttons)

        def validate_and_accept() -> None:
            if not username_edit.text().strip():
                QMessageBox.warning(dialog, "Missing username", "Enter the MySQL username.")
                username_edit.setFocus()
                return
            if not password_edit.text():
                QMessageBox.warning(dialog, "Missing password", "Enter the MySQL password.")
                password_edit.setFocus()
                return
            dialog.accept()

        buttons.accepted.connect(validate_and_accept)
        buttons.rejected.connect(dialog.reject)
        password_edit.returnPressed.connect(validate_and_accept)
        username_edit.returnPressed.connect(password_edit.setFocus)
        username_edit.setFocus()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            raise KeyStoreError("Database credential setup was cancelled.")

        username = username_edit.text().strip()
        password = password_edit.text()
        if not username or not password:
            # Defensive check in case the dialog is changed later.
            raise KeyStoreError("A MySQL username and password are required.")
        return username, password

    def get_credentials(self) -> tuple[str, str]:
        """Return a matched ``(username, password)`` pair from the best source."""
        if self._credentials_cache is not None:
            return self._credentials_cache

        process_username, process_password = self._process_credentials()
        file_username, file_password = self._file_credentials()
        username_hints = (process_username, file_username, self.account)

        # 1. Credential Manager has the highest priority.
        stored = self._get_keyring_credentials(username_hints)
        if stored:
            self._credentials_cache = stored
            self.account = stored[0]
            return stored

        # Never combine a username from one source with a password from another:
        # that can silently authenticate as the wrong MySQL account.
        credentials: tuple[str, str] | None = None
        if process_username and process_password:
            credentials = (process_username, process_password)
        elif file_username and file_password:
            credentials = (file_username, file_password)
        elif (process_username or process_password) or (file_username or file_password):
            _LOG.warning(
                "A partial MySQL credential pair was found in environment/.env; "
                "the values were not combined across sources."
            )

        if credentials:
            try:
                self._save_keyring_credentials(*credentials)
            except KeyStoreError as exc:
                # Environment/.env credentials remain usable for this run.
                _LOG.warning("Could not persist configured DB credentials: %s", exc)
            self.account = credentials[0]
            self._credentials_cache = credentials
            return credentials

        # 4. Interactive fallback. If Credential Manager is unavailable, the
        # entered pair is still valid for this process; do not discard it.
        username, password = self._prompt_for_credentials(
            process_username or file_username or self.account or self.DEFAULT_USERNAME
        )
        try:
            self._save_keyring_credentials(username, password)
        except KeyStoreError as exc:
            _LOG.warning("Credentials will be used for this session only: %s", exc)
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox

                parent = QApplication.activeWindow() if QApplication.instance() else None
                QMessageBox.warning(
                    parent,
                    "Credential Manager unavailable",
                    "The MySQL credentials could not be saved in Windows "
                    "Credential Manager. They will be used for this session "
                    "only; configure Credential Manager or environment "
                    "variables to avoid being prompted again.",
                )
            except Exception:
                pass

        self.account = username
        self._credentials_cache = (username, password)
        return self._credentials_cache

    def get_username(self) -> str:
        """Return the configured MySQL username."""
        return self.get_credentials()[0]

    def get_password(self) -> str:
        """Return the configured MySQL password (legacy-compatible API)."""
        return self.get_credentials()[1]


if __name__ == "__main__":
    # This explicit setup utility is intentionally console-based. It does not
    # import or start the ERP GUI.
    username = input(f"MySQL username [{KeyStore.DEFAULT_USERNAME}]: ").strip()
    username = username or KeyStore.DEFAULT_USERNAME
    password = getpass.getpass("MySQL password for the MyShop user: ")
    try:
        store = KeyStore(allow_prompt=False)
        store.set_credentials(username, password)
    except (KeyStoreError, ValueError) as exc:
        raise SystemExit(f"Could not save database credentials: {exc}") from exc
    print("Database username and password saved in the OS credential store.")
