"""MyShop ERP database credential management.

Credential lookup order:
    1. Windows Credential Manager (through ``keyring``).
    2. Process environment variables (useful when the ERP is launched by a
       service wrapper that supplies environment variables).
    3. A ``.env`` file beside the EXE, or at the project root when running
       from source. Values found in either configuration source are saved to
       Credential Manager on first use where possible.
    4. An interactive username/password dialog. The entered credentials are
       saved to Credential Manager before being returned.

Supported username variables:
    MYSQL_USERNAME, MYSHOP_DB_USERNAME, MYSHOP_DB_USER, MYSQL_USER

Supported password variables:
    MYSHOP_DB_PASSWORD, MYSQL_PASSWORD

To configure credentials manually:
    python -m Database.keystore

For a non-interactive service process, set MYSHOP_ALLOW_DB_CREDENTIAL_PROMPT=0
and provide credentials through Credential Manager or environment variables.
"""
from __future__ import annotations

import getpass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Mapping

try:
    import keyring
except ImportError:  # Configuration sources can still be read if keyring is not installed.
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


class KeyStoreError(RuntimeError):
    """Raised when usable MySQL credentials cannot be obtained or saved."""


class KeyStore:
    """Load a matching MySQL username/password pair from configured sources.

    ``get_credentials()`` is the preferred API. ``get_username()`` and
    ``get_password()`` are provided for compatibility with older callers.
    Credential Manager stores the pair as one versioned JSON secret under a
    stable account name, so the username and password cannot accidentally
    come from different saved entries.
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
        # Kept for backwards compatibility with older keyring entries where
        # the MySQL username itself was used as the Credential Manager key.
        self.account = account
        self.project_root = self._application_directory()
        self.env_file = Path(env_file).expanduser() if env_file else self.project_root / ".env"
        if not self.env_file.is_absolute():
            self.env_file = (self.project_root / self.env_file).resolve()
        self.allow_prompt = self._prompt_setting() if allow_prompt is None else bool(allow_prompt)
        self._credentials_cache: tuple[str, str] | None = None

    @staticmethod
    def _application_directory() -> Path:
        """Return the directory containing the EXE, or the source project root."""
        if getattr(sys, "frozen", False):
            # In a PyInstaller one-file build, __file__ may point inside the
            # temporary _MEIPASS directory. The user's .env belongs beside EXE.
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def _prompt_setting() -> bool:
        value = os.environ.get("MYSHOP_ALLOW_DB_CREDENTIAL_PROMPT", "1").strip().lower()
        return value not in {"0", "false", "no", "off"}

    @staticmethod
    def _first_value(values: Mapping[str, object], names: tuple[str, ...]) -> str | None:
        for name in names:
            raw = values.get(name)
            if raw is not None:
                value = str(raw).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _read_dotenv_file(path: Path) -> dict[str, str]:
        """Read a simple .env file without requiring python-dotenv in the EXE.

        Supports KEY=value, optional ``export ``, comments, and single- or
        double-quoted values. Values are not interpolated, intentionally.
        """
        result: dict[str, str] = {}
        if not path.is_file():
            return result
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            _LOG.warning("Could not read .env file %s: %s", path, exc)
            return result

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, separator, value = line.partition("=")
            if not separator:
                continue
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            else:
                # In unquoted dotenv values, a whitespace-prefixed # begins a comment.
                comment_index = value.find(" #")
                if comment_index >= 0:
                    value = value[:comment_index].rstrip()
            result[key] = value
        return result

    def _process_credentials(self) -> tuple[str | None, str | None]:
        return (
            self._first_value(os.environ, _USERNAME_KEYS),
            self._first_value(os.environ, _PASSWORD_KEYS),
        )

    def _file_credentials(self) -> tuple[str | None, str | None]:
        values = self._read_dotenv_file(self.env_file)
        return (
            self._first_value(values, _USERNAME_KEYS),
            self._first_value(values, _PASSWORD_KEYS),
        )

    def _read_keyring_secret(self, account: str) -> str | None:
        if keyring is None:
            return None
        try:
            value = keyring.get_password(self.service, account)
            return value if value else None
        except Exception as exc:  # keyring backends can raise non-KeyringError exceptions too
            _LOG.debug("Credential Manager read failed for account %s: %s", account, exc)
            return None

    def _get_keyring_credentials(
        self,
        username_hints: tuple[str | None, ...],
    ) -> tuple[str, str] | None:
        # New format: the username and password are held together in one secret.
        raw = self._read_keyring_secret(self.CREDENTIAL_ACCOUNT)
        if raw:
            try:
                saved = json.loads(raw)
                username = str(saved.get("username", "")).strip()
                password = str(saved.get("password", ""))
                if username and password:
                    return username, password
            except (json.JSONDecodeError, AttributeError, TypeError):
                # A malformed/new-format entry should not prevent trying legacy keys.
                _LOG.warning("Stored MyShop database credential entry is malformed.")

        # Backward compatibility with older versions that stored only the
        # password under the MySQL username (or the old default account).
        candidates: list[str] = []
        for candidate in (*username_hints, self.account, self.DEFAULT_USERNAME):
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        for username in candidates:
            password = self._read_keyring_secret(username)
            if password:
                try:
                    self._save_keyring_credentials(username, password)
                except KeyStoreError:
                    # The existing legacy entry remains usable for this run.
                    pass
                return username, password
        return None

    def _save_keyring_credentials(self, username: str, password: str) -> None:
        username = username.strip()
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
                "Could not save the MySQL credentials in the OS credential store. "
                "Check that Windows Credential Manager is available for the "
                "Windows account running this ERP application."
            ) from exc

    def set_credentials(self, username: str, password: str) -> None:
        """Store both credentials in the OS credential store and cache them."""
        username = (username or "").strip()
        if not username:
            raise ValueError("The MySQL username cannot be empty.")
        if not password:
            raise ValueError("The MySQL password cannot be empty.")
        self._save_keyring_credentials(username, password)
        self.account = username
        self._credentials_cache = (username, password)

    def set_password(self, password: str, username: str | None = None) -> None:
        """Compatibility method for older code that only saved a password.

        Prefer ``set_credentials(username, password)``. The username is taken
        from an explicit argument, environment/.env config, or the old default.
        """
        process_username, _ = self._process_credentials()
        file_username, _ = self._file_credentials()
        resolved_username = username or process_username or file_username or self.account
        self.set_credentials(resolved_username, password)

    def _prompt_for_credentials(self, username_hint: str | None = None) -> tuple[str, str]:
        if not self.allow_prompt:
            raise KeyStoreError(
                "No MySQL credentials were found in Windows Credential Manager, "
                "process environment variables, or .env. Interactive credential "
                "prompting is disabled. Configure credentials for the process "
                "or enable MYSHOP_ALLOW_DB_CREDENTIAL_PROMPT=1 in an interactive session."
            )

        try:
            import tkinter as tk
            from tkinter import messagebox
            from tkinter import ttk
        except Exception as exc:
            raise KeyStoreError(
                "No MySQL credentials were found, and the credential dialog "
                "could not be loaded in this environment."
            ) from exc

        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            dialog = tk.Toplevel(root)
            dialog.title("MyShop — MySQL Database Credentials")
            dialog.resizable(False, False)
            dialog.transient(root)
            dialog.grab_set()

            outer = ttk.Frame(dialog, padding=16)
            outer.grid(row=0, column=0, sticky="nsew")
            ttk.Label(
                outer,
                text=(
                    "Database credentials were not found. Enter the MySQL "
                    "account used by MyShop. They will be saved to Windows "
                    "Credential Manager."
                ),
                wraplength=390,
                justify="left",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

            username_var = tk.StringVar(value=username_hint or self.account or "")
            password_var = tk.StringVar()
            ttk.Label(outer, text="MySQL username:").grid(row=1, column=0, sticky="w", pady=4)
            username_entry = ttk.Entry(outer, textvariable=username_var, width=38)
            username_entry.grid(row=1, column=1, sticky="ew", pady=4)
            ttk.Label(outer, text="MySQL password:").grid(row=2, column=0, sticky="w", pady=4)
            password_entry = ttk.Entry(outer, textvariable=password_var, width=38, show="•")
            password_entry.grid(row=2, column=1, sticky="ew", pady=4)

            result: dict[str, str] = {}

            def submit() -> None:
                username = username_var.get().strip()
                password = password_var.get()
                if not username:
                    messagebox.showerror("Missing username", "Enter the MySQL username.", parent=dialog)
                    username_entry.focus_set()
                    return
                if not password:
                    messagebox.showerror("Missing password", "Enter the MySQL password.", parent=dialog)
                    password_entry.focus_set()
                    return
                result["username"] = username
                result["password"] = password
                dialog.destroy()

            def cancel() -> None:
                dialog.destroy()

            buttons = ttk.Frame(outer)
            buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
            ttk.Button(buttons, text="Cancel", command=cancel).grid(row=0, column=0, padx=(0, 8))
            ttk.Button(buttons, text="Save credentials", command=submit).grid(row=0, column=1)
            dialog.protocol("WM_DELETE_WINDOW", cancel)
            dialog.bind("<Return>", lambda _event: submit())
            dialog.bind("<Escape>", lambda _event: cancel())
            username_entry.focus_set()
            dialog.update_idletasks()
            width = dialog.winfo_reqwidth()
            height = dialog.winfo_reqheight()
            x = max(0, (dialog.winfo_screenwidth() - width) // 2)
            y = max(0, (dialog.winfo_screenheight() - height) // 2)
            dialog.geometry(f"{width}x{height}+{x}+{y}")
            root.wait_window(dialog)

            if not result:
                raise KeyStoreError("Database credential setup was cancelled.")
            return result["username"], result["password"]
        except KeyStoreError:
            raise
        except Exception as exc:
            raise KeyStoreError(
                "Could not display the MySQL credential dialog. This usually "
                "happens when the ERP is running in a non-interactive Windows service session."
            ) from exc
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass

    def get_credentials(self) -> tuple[str, str]:
        """Return ``(username, password)`` from the best available source."""
        if self._credentials_cache:
            return self._credentials_cache

        process_username, process_password = self._process_credentials()
        file_username, file_password = self._file_credentials()
        username_hints = (process_username, file_username, self.account)

        # 1. Existing OS Credential Manager entry.
        stored = self._get_keyring_credentials(username_hints)
        if stored:
            self._credentials_cache = stored
            self.account = stored[0]
            return stored

        # 2. Process environment (can be supplied by a service wrapper). Fill
        #    missing values from .env, then persist the pair for future runs.
        # 3. .env beside the EXE/project root, likewise imported once.
        username = process_username or file_username
        password = process_password or file_password
        if username and password:
            credentials = (username, password)
            try:
                self._save_keyring_credentials(*credentials)
            except KeyStoreError as exc:
                # Configured credentials remain usable for this run even if
                # Credential Manager is unavailable; the .env/env source stays
                # as a fallback on the next run.
                _LOG.warning("Could not persist configured DB credentials: %s", exc)
            self.account = username
            self._credentials_cache = credentials
            return credentials

        # 4. Developer/user fallback. Prompt only when credentials are missing.
        username_hint = username or self.account or self.DEFAULT_USERNAME
        prompted_username, prompted_password = self._prompt_for_credentials(username_hint)
        self._save_keyring_credentials(prompted_username, prompted_password)
        self.account = prompted_username
        self._credentials_cache = (prompted_username, prompted_password)
        return self._credentials_cache

    def get_username(self) -> str:
        """Return the configured MySQL username."""
        return self.get_credentials()[0]

    def get_password(self) -> str:
        """Return the configured MySQL password (legacy-compatible API)."""
        return self.get_credentials()[1]


if __name__ == "__main__":
    username = input(f"MySQL username [{KeyStore.DEFAULT_USERNAME}]: ").strip()
    username = username or KeyStore.DEFAULT_USERNAME
    password = getpass.getpass("MySQL password for the MyShop user: ")
    try:
        store = KeyStore(allow_prompt=False)
        store.set_credentials(username, password)
    except (KeyStoreError, ValueError) as exc:
        raise SystemExit(f"Could not save database credentials: {exc}") from exc
    print("Database username and password saved in the OS credential store.")
