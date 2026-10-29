"""MySQL 8 database layer (replaces the SQLCipher / SQLite version).

Requires: pip install pymysql cryptography keyring

Configuration sources for connection settings (highest priority first):
    1. Process environment variables (useful for Windows service wrappers).
    2. .env beside the PyInstaller EXE, or project root when running from source.
    3. Defaults below.

Database connection settings:
    MYSHOP_DB_HOST (localhost)
    MYSHOP_DB_PORT (3306)
    MYSHOP_DB_NAME (myshop)

Username and password are resolved together by Database.keystore.KeyStore:
    1. Windows Credential Manager
    2. Process environment variables
    3. .env
    4. Interactive credential dialog (unless disabled)
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from datetime import datetime

import pymysql
from pymysql.connections import Connection
from pymysql.constants import FIELD_TYPE
from pymysql.converters import conversions
from pymysql.cursors import Cursor

from Database.keystore import KeyStore
from Database.migrator import Migrator
from Database.migrations import ALL_MIGRATIONS

MIN_MYSQL = (8, 0, 23)  # INVISIBLE columns, enforced CHECK, indexed generated columns
CHARSET = "utf8mb4"
COLLATION = "utf8mb4_0900_as_ci"  # case-insensitive, but keeps Arabic hamza/diacritic differences


class DatabaseError(Exception):
    pass


# ---------- configuration helpers ----------
def _dotenv_config() -> dict[str, str]:
    """Read the same .env file location used by KeyStore without prompting."""
    try:
        store = KeyStore(allow_prompt=False)
        # KeyStore owns the parser and resolves the correct source/EXE directory.
        return store._read_dotenv_file(store.env_file)
    except Exception:
        # .env settings are optional; the process environment/defaults remain usable.
        return {}


def _config_value(
    env_values: dict[str, str],
    names: tuple[str, ...],
    default: str,
) -> str:
    """Process environment takes precedence over the same .env keys."""
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip():
            return value.strip()
    for name in names:
        value = env_values.get(name)
        if value is not None and value.strip():
            return value.strip()
    return default


# ---------- compatibility layer so the existing services keep working ----------
# DECIMAL -> float (quantities) or int (money sums), DATE/DATETIME -> str,
# matching what SQLite returned.
def _decimal(s):
    return float(s) if "." in s else int(s)


_CONV = conversions.copy()
for _t in (FIELD_TYPE.DECIMAL, FIELD_TYPE.NEWDECIMAL):
    _CONV[_t] = _decimal
for _t in (FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.DATE):
    _CONV[_t] = lambda s: s


def _translate(sql, params):
    """Support legacy SQLite '?' and native PyMySQL '%s' placeholders."""
    if params is None or (isinstance(params, (list, tuple)) and not params):
        return sql, None

    if isinstance(params, dict):
        # Native PyMySQL named placeholders, e.g. %(username)s.
        return sql, params

    # Escape literal '%' characters without doubling native '%s' placeholders.
    sql = re.sub(r"%(?!s)", "%%", sql)
    # Convert legacy SQLite positional placeholders to MySQL syntax.
    sql = sql.replace("?", "%s")
    return sql, params


def _local_utc_offset() -> str:
    """Return the PC's current UTC offset for MySQL session time zone."""
    offset = datetime.now().astimezone().utcoffset()
    total = int(offset.total_seconds()) if offset is not None else 0
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


class _Cursor(Cursor):
    """PyMySQL cursor with SQLite-compatible execute return behavior."""

    def execute(self, query, args=None):
        sql, params = _translate(query, args)
        try:
            super().execute(sql, params)
            # SQLite-compatible: cursor.execute(...).fetchone()
            return self
        except TypeError as exc:
            if "format" not in str(exc).lower():
                raise
            parameter_count = (
                len(args)
                if isinstance(args, (tuple, list, dict))
                else "unknown"
            )
            raise TypeError(
                "PyMySQL parameter-formatting failure in execute(). "
                f"SQL={query!r}; parameter_type={type(args).__name__}; "
                f"parameter_count={parameter_count}"
            ) from exc

    def executemany(self, query, args):
        """Execute multiple parameter sets; preserve chainable return behavior."""
        rows = list(args)
        if not rows:
            self.rowcount = 0
            return self

        # Translate once using the original SQL; pass each row's parameters to
        # the original PyMySQL execute implementation to obtain an integer count.
        sql, _ = _translate(query, rows[0])
        total_affected = 0
        try:
            for row in rows:
                params = row if row else None
                total_affected += Cursor.execute(self, sql, params)
            self.rowcount = total_affected
            return self
        except TypeError as exc:
            if "format" not in str(exc).lower():
                raise
            first_row_width = (
                len(rows[0])
                if isinstance(rows[0], (tuple, list, dict))
                else "unknown"
            )
            raise TypeError(
                "PyMySQL parameter-formatting failure in executemany(). "
                f"SQL={query!r}; row_count={len(rows)}; "
                f"first_row_type={type(rows[0]).__name__}; "
                f"first_row_width={first_row_width}"
            ) from exc

    def fetchall(self):
        return list(super().fetchall())


class _Connection(Connection):
    def execute(self, sql, params=None):
        """sqlite3-style shortcut: conn.execute(...) returns a cursor."""
        cur = self.cursor()
        cur.execute(sql, params)
        return cur


class Database:
    def __init__(self, **overrides):
        # Keep the .env path consistent with KeyStore's EXE-aware path handling.
        self._key_store = KeyStore()
        dotenv_values = _dotenv_config()

        # Accept either the PyMySQL-style 'user' or the clearer 'username'
        # override without accidentally forwarding either as a connection option.
        username_override = overrides.pop("username", None)
        user_alias = overrides.pop("user", None)
        if username_override is None:
            username_override = user_alias
        password_override = overrides.pop("password", None)

        try:
            configured_port = int(
                _config_value(dotenv_values, ("MYSHOP_DB_PORT",), "3306")
            )
        except ValueError as exc:
            raise DatabaseError("MYSHOP_DB_PORT must be an integer.") from exc

        self.config = {
            "host": _config_value(
                dotenv_values,
                ("MYSHOP_DB_HOST",),
                "localhost",
            ),
            "port": configured_port,
            "database": _config_value(
                dotenv_values,
                ("MYSHOP_DB_NAME", "MYSQL_DATABASE"),
                "myshop",
            ),
            **overrides,
        }

        # Do not read credentials (or open a dialog) during module import. Resolve
        # them only when a connection is requested, using one KeyStore instance.
        self._username: str | None = (
            str(username_override).strip() if username_override else None
        )
        self._password: str | None = password_override
        self._credentials_loaded = bool(self._username and self._password is not None)

        if not re.fullmatch(r"[A-Za-z0-9_]+", str(self.config["database"])):
            raise DatabaseError("Invalid database name. Use letters, digits, or underscores.")

    def _resolve_credentials(self) -> tuple[str, str]:
        """Resolve a consistent username/password pair on first connection."""
        if not self._credentials_loaded:
            store_username, store_password = self._key_store.get_credentials()
            if self._username is None:
                self._username = store_username
            if self._password is None:
                self._password = store_password
            self._credentials_loaded = True

        if not self._username or self._password is None:
            raise DatabaseError("MySQL username or password is missing.")
        return self._username, self._password

    @property
    def username(self) -> str:
        """Return the resolved username (may trigger credential setup on access)."""
        return self._resolve_credentials()[0]

    def _get_password(self) -> str:
        """Compatibility helper retained for existing callers."""
        return self._resolve_credentials()[1]

    def _open(self, use_database=True):
        cfg = self.config
        username, password = self._resolve_credentials()
        try:
            return _Connection(
                host=cfg["host"],
                port=cfg["port"],
                user=username,
                password=password,
                database=cfg["database"] if use_database else None,
                charset=CHARSET,
                autocommit=True,  # transactions are explicit
                cursorclass=_Cursor,
                conv=_CONV,
                connect_timeout=5,
                init_command=f"SET time_zone = '{_local_utc_offset()}'",
            )
        except pymysql.MySQLError as exc:
            raise DatabaseError(
                f"Cannot connect to MySQL at {cfg['host']}:{cfg['port']}: {exc}"
            ) from exc

    def connect(self):
        return self._open()

    @contextmanager
    def transaction(self):
        """Run all yielded statements in one transaction."""
        conn = self.connect()
        try:
            conn.begin()
            yield conn.cursor()
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except pymysql.MySQLError:
                pass
            raise
        finally:
            conn.close()

    # ---------- read helpers ----------
    def fetch_all(self, sql, params=()):
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def fetch_one(self, sql, params=()):
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    # ---------- setup ----------
    @staticmethod
    def _check_version(version: str):
        if "mariadb" in version.lower():
            raise DatabaseError(
                "MariaDB is not supported (needs MySQL 8.0.23 or newer)."
            )
        nums = tuple(int(x) for x in re.findall(r"\d+", version)[:3])
        if nums < MIN_MYSQL:
            raise DatabaseError(
                f"MySQL {version} is too old (needs 8.0.23 or newer)."
            )

    def _ensure_database(self):
        conn = self._open(use_database=False)
        try:
            cur = conn.cursor()
            cur.execute("SELECT VERSION()")
            self._check_version(cur.fetchone()[0])
            # Database name is validated against the safe identifier pattern in __init__.
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.config['database']}` "
                f"CHARACTER SET {CHARSET} COLLATE {COLLATION}"
            )
        except pymysql.MySQLError as exc:
            raise DatabaseError(f"Cannot prepare the database: {exc}") from exc
        finally:
            conn.close()

    def initialize(self):
        """Create the database if needed and apply every pending migration."""
        self._ensure_database()
        conn = self.connect()
        try:
            Migrator(conn, ALL_MIGRATIONS).run()
        finally:
            conn.close()


db = Database()  # shared instance: from Database.Schema import db
