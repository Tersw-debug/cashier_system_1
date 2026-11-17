"""MySQL 8 database layer (PyMySQL implementation).

Requires:
    pip install pymysql cryptography keyring python-dotenv PySide6

Connection settings are resolved in this order:
    1. Explicit constructor overrides.
    2. Process environment variables.
    3. The application's .env file.
    4. Defaults.

Credentials are resolved as one matched username/password pair by
Database.keystore.KeyStore. Credential Manager takes priority, followed by
complete process-environment and .env pairs, then an optional PySide6 dialog.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.constants import FIELD_TYPE
from pymysql.converters import conversions
from pymysql.cursors import Cursor

from Database.keystore import KeyStore, KeyStoreError
from Database.migrator import Migrator
from Database.migrations import ALL_MIGRATIONS

MIN_MYSQL = (8, 0, 23)  # Required MySQL features used by the schema.
CHARSET = "utf8mb4"
COLLATION = "utf8mb4_0900_as_ci"


class DatabaseError(RuntimeError):
    """Raised for database configuration, connection, and setup failures."""


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def _dotenv_config() -> dict[str, str]:
    """Read supported .env settings without prompting or exposing credentials."""
    try:
        store = KeyStore(allow_prompt=False)
        values = store._read_dotenv_file(store.env_file)
        # Connection configuration never needs credential values; keep them in
        # KeyStore so passwords are not copied into unrelated configuration.
        return {
            key: values[key]
            for key in ("host", "port", "db_name")
            if key in values
        }
    except Exception:
        # .env settings are optional; process environment/defaults remain usable.
        return {}


def _local_utc_offset() -> str:
    """Return the current local UTC offset for the MySQL session time zone."""
    offset = datetime.now().astimezone().utcoffset()
    total = int(offset.total_seconds()) if offset is not None else 0
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


def _translate(sql: str, params):
    """Translate legacy SQLite '?' placeholders safely for PyMySQL.

    Question marks inside quoted strings, quoted identifiers, and SQL comments
    are preserved. Literal percent signs are escaped for PyMySQL's percent-
    based parameter interpolation, while native %s / %(name)s placeholders are
    preserved outside quoted strings and comments.
    """
    if params is None or (isinstance(params, (list, tuple)) and not params):
        return sql, None

    mapping_params = isinstance(params, dict)
    output: list[str] = []
    i = 0
    length = len(sql)
    quote: str | None = None
    line_comment = False
    block_comment = False

    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""

        if line_comment:
            if char == "%":
                if next_char == "%":
                    output.append("%%")
                    i += 2
                    continue
                output.append("%%")
            else:
                output.append(char)
            if char in "\r\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            if char == "*" and next_char == "/":
                output.append("*/")
                i += 2
                block_comment = False
                continue
            if char == "%":
                if next_char == "%":
                    output.append("%%")
                    i += 2
                    continue
                output.append("%%")
            else:
                output.append(char)
            i += 1
            continue

        if quote is not None:
            # Percent signs in literals/identifiers are always literal, not
            # placeholders. Escape them so PyMySQL does not interpolate them.
            if char == "%":
                if next_char == "%":
                    output.append("%%")
                    i += 2
                    continue
                output.append("%%")
                i += 1
                continue
            output.append(char)
            if char == "\\" and quote in ("'", '"') and next_char:
                output.append(next_char)
                i += 2
                continue
            if char == quote:
                if next_char == quote:  # SQL doubled quote, e.g. 'it''s'.
                    output.append(next_char)
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        # Outside a quoted token/comment.
        if char in ("'", '"', "`"):
            quote = char
            output.append(char)
            i += 1
            continue

        if char == "#":
            line_comment = True
            output.append(char)
            i += 1
            continue

        if char == "-" and next_char == "-":
            after = sql[i + 2] if i + 2 < length else ""
            # MySQL treats -- as a comment only when followed by whitespace
            # or a control character.
            if not after or after.isspace() or ord(after) < 32:
                line_comment = True
                output.append("--")
                i += 2
                continue

        if char == "/" and next_char == "*":
            block_comment = True
            output.append("/*")
            i += 2
            continue

        if char == "?":
            if mapping_params:
                raise TypeError(
                    "Cannot mix SQLite '?' placeholders with PyMySQL named parameters."
                )
            output.append("%s")
            i += 1
            continue

        if char == "%":
            if next_char == "%":
                output.append("%%")
                i += 2
                continue
            if not mapping_params and next_char == "s":
                output.append("%s")
                i += 2
                continue
            if mapping_params and next_char == "(":
                match = re.match(r"%\([A-Za-z_][A-Za-z0-9_]*\)s", sql[i:])
                if match:
                    output.append(match.group(0))
                    i += len(match.group(0))
                    continue
            output.append("%%")
            i += 1
            continue

        output.append(char)
        i += 1

    return "".join(output), params


# ---------------------------------------------------------------------------
# PyMySQL compatibility wrappers
# ---------------------------------------------------------------------------
# Preserve MySQL DECIMAL precision. Services that require a float can convert
# explicitly at their boundary; monetary amounts in this schema are stored as
# integer minor currency units and are therefore unaffected.
def _decimal(value):
    text = value.decode() if isinstance(value, bytes) else str(value)
    return Decimal(text)


_CONV = conversions.copy()
for _type in (FIELD_TYPE.DECIMAL, FIELD_TYPE.NEWDECIMAL):
    _CONV[_type] = _decimal
for _type in (FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.DATE):
    _CONV[_type] = lambda value: value


class _Cursor(Cursor):
    """PyMySQL cursor with SQLite-compatible execute return behavior."""

    def execute(self, query, args=None):
        sql, params = _translate(query, args)
        try:
            super().execute(sql, params)
            # Existing services sometimes use cursor.execute(...).fetchone().
            return self
        except TypeError as exc:
            if "format" not in str(exc).lower():
                raise
            parameter_count = (
                len(args) if isinstance(args, (tuple, list, dict)) else "unknown"
            )
            raise TypeError(
                "PyMySQL parameter-formatting failure in execute(). "
                f"SQL={query!r}; parameter_type={type(args).__name__}; "
                f"parameter_count={parameter_count}"
            ) from exc

    def executemany(self, query, args):
        """Execute each parameter set through the same safe translator."""
        rows = list(args)
        if not rows:
            self.rowcount = 0
            return self

        total_affected = 0
        try:
            for row in rows:
                self.execute(query, row)
                if self.rowcount > 0:
                    total_affected += self.rowcount
            self.rowcount = total_affected
            return self
        except TypeError as exc:
            if "format" not in str(exc).lower():
                raise
            first_row_width = (
                len(rows[0]) if isinstance(rows[0], (tuple, list, dict)) else "unknown"
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
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor


# ---------------------------------------------------------------------------
# Database service
# ---------------------------------------------------------------------------
class Database:
    def __init__(self, **overrides):
        self._key_store = KeyStore()
        dotenv_config = _dotenv_config()

        username_override = overrides.pop("username", None)
        user_alias = overrides.pop("user", None)
        password_override = overrides.pop("password", None)

        if username_override is not None and user_alias is not None:
            if str(username_override).strip() != str(user_alias).strip():
                raise DatabaseError("Conflicting 'username' and 'user' overrides.")
        if username_override is None:
            username_override = user_alias

        if (username_override is None) != (password_override is None):
            raise DatabaseError(
                "Provide both username and password overrides, or neither. "
                "A username must never be combined with a password from another source."
            )
        if username_override is not None and not str(username_override).strip():
            raise DatabaseError("The MySQL username override cannot be empty.")

        # Explicit connection overrides have the highest priority, followed by
        # process environment, .env, and safe local defaults.
        host_override = overrides.pop("host", None)
        port_override = overrides.pop("port", None)
        database_override = overrides.pop("database", None)

        host = (
            host_override
            if host_override is not None
            else os.getenv("MYSHOP_DB_HOST")
            or dotenv_config.get("host")
            or "localhost"
        )
        port_value = (
            port_override
            if port_override is not None
            else os.getenv("MYSHOP_DB_PORT")
            or dotenv_config.get("port")
            or "3306"
        )
        database_name = (
            database_override
            if database_override is not None
            else os.getenv("MYSHOP_DB_NAME")
            or os.getenv("MYSQL_DATABASE")
            or dotenv_config.get("db_name")
            or "myshop"
        )

        try:
            port = int(port_value)
        except (TypeError, ValueError) as exc:
            raise DatabaseError("MYSHOP_DB_PORT must be an integer.") from exc
        if not 1 <= port <= 65535:
            raise DatabaseError("MYSHOP_DB_PORT must be between 1 and 65535.")

        host = str(host).strip()
        database_name = str(database_name).strip()
        if not host:
            raise DatabaseError("MYSHOP_DB_HOST cannot be empty.")
        if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
            raise DatabaseError(
                "Invalid database name. Use letters, digits, or underscores."
            )

        self.config = {
            "host": host,
            "port": port,
            "database": database_name,
            **overrides,
        }

        self._username: str | None = (
            str(username_override).strip()
            if username_override is not None
            else None
        )
        self._password: str | None = password_override
        self._credentials_loaded = username_override is not None

    def _resolve_credentials(self) -> tuple[str, str]:
        """Resolve one consistent username/password pair on first connection."""
        if not self._credentials_loaded:
            try:
                username, password = self._key_store.get_credentials()
            except KeyStoreError:
                raise
            except Exception as exc:
                raise DatabaseError(
                    f"Could not resolve MySQL credentials: {type(exc).__name__}: {exc}"
                ) from exc
            self._username = username
            self._password = password
            self._credentials_loaded = True

        if not self._username or self._password is None:
            raise DatabaseError("MySQL username or password is missing.")
        return self._username, self._password

    @property
    def username(self) -> str:
        """Return the resolved username (may display the credential dialog)."""
        return self._resolve_credentials()[0]

    def _get_password(self) -> str:
        """Compatibility helper retained for existing callers."""
        return self._resolve_credentials()[1]

    def _open(self, use_database: bool = True):
        cfg = self.config
        username, password = self._resolve_credentials()
        try:
            connection_options = {
                key: value
                for key, value in cfg.items()
                if key not in {"host", "port", "database"}
            }
            # Core options are intentionally fixed so callers cannot bypass the
            # cursor compatibility layer or silently disable explicit commits.
            connection_options.update(
                {
                    "host": cfg["host"],
                    "port": cfg["port"],
                    "user": username,
                    "password": password,
                    "database": cfg["database"] if use_database else None,
                    "charset": CHARSET,
                    "autocommit": True,
                    "cursorclass": _Cursor,
                    "conv": _CONV,
                    "connect_timeout": 5,
                    "init_command": f"SET time_zone = '{_local_utc_offset()}'",
                }
            )
            return _Connection(**connection_options)
        except pymysql.MySQLError as exc:
            raise DatabaseError(
                f"Cannot connect to MySQL at {cfg['host']}:{cfg['port']}: {exc}"
            ) from exc

    def connect(self):
        """Open a new connection to the configured database."""
        return self._open(use_database=True)

    @contextmanager
    def transaction(self):
        """Run yielded statements in one transaction and always close resources."""
        connection = self.connect()
        cursor = None
        try:
            connection.begin()
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except BaseException:
            try:
                connection.rollback()
            except pymysql.MySQLError:
                pass
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except pymysql.MySQLError:
                    pass
            connection.close()

    # -----------------------------------------------------------------------
    # Read helpers
    # -----------------------------------------------------------------------
    def fetch_all(self, sql, params=()):
        connection = self.connect()
        try:
            return connection.execute(sql, params).fetchall()
        finally:
            connection.close()

    def fetch_one(self, sql, params=()):
        connection = self.connect()
        try:
            return connection.execute(sql, params).fetchone()
        finally:
            connection.close()

    # -----------------------------------------------------------------------
    # Setup and migrations
    # -----------------------------------------------------------------------
    @staticmethod
    def _check_version(version: str) -> None:
        if "mariadb" in version.lower():
            raise DatabaseError(
                "MariaDB is not supported (needs MySQL 8.0.23 or newer)."
            )
        numbers = tuple(int(value) for value in re.findall(r"\d+", version)[:3])
        if len(numbers) < 3 or numbers < MIN_MYSQL:
            raise DatabaseError(
                f"MySQL {version} is too old or its version could not be parsed "
                f"(needs {'.'.join(map(str, MIN_MYSQL))} or newer)."
            )

    def _ensure_database(self) -> None:
        """Create the configured schema only when it does not already exist.

        Existing deployments therefore do not need CREATE DATABASE privilege
        merely to start the ERP. First-time installation still requires it.
        """
        connection = self._open(use_database=False)
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            self._check_version(cursor.fetchone()[0])
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME = %s",
                (self.config["database"],),
            )
            exists = cursor.fetchone()
            if not exists:
                cursor.execute(
                    f"CREATE DATABASE `{self.config['database']}` "
                    f"CHARACTER SET {CHARSET} COLLATE {COLLATION}"
                )
        except pymysql.MySQLError as exc:
            raise DatabaseError(
                "Cannot prepare the MySQL database. Ensure the configured user "
                "has permission to create the database on first installation "
                f"and required migration privileges: {exc}"
            ) from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except pymysql.MySQLError:
                    pass
            connection.close()

    def initialize(self) -> None:
        """Create the database if absent and apply all pending migrations."""
        self._ensure_database()
        connection = self.connect()
        try:
            Migrator(connection, ALL_MIGRATIONS).run()
        finally:
            connection.close()


# Shared instance: existing services import it using
# ``from Database.Schema import db``.
db = Database()
