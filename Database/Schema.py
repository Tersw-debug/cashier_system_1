"""MySQL 8 database layer (replaces the SQLCipher / SQLite version).

Requires:  pip install pymysql cryptography
Config (environment variables, all optional):
    MYSHOP_DB_HOST (127.0.0.1)  MYSHOP_DB_PORT (3306)  MYSHOP_DB_NAME (myshop)
    MYSHOP_DB_USER (myshop)
Password: MYSHOP_DB_PASSWORD if set, otherwise the OS credential store
(save it once with:  python -m Database.keystore).
"""
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

MIN_MYSQL = (8, 0, 23)            # INVISIBLE columns, enforced CHECK, indexed generated columns
CHARSET = "utf8mb4"
COLLATION = "utf8mb4_0900_as_ci"  # case-insensitive, but keeps Arabic hamza/diacritic differences


class DatabaseError(Exception):
    pass


# ---------- compatibility layer so the existing services keep working ----------
# 1. DECIMAL -> float (quantities) or int (money sums), DATE/DATETIME -> str,
#    matching what SQLite returned.
def _decimal(s):
    return float(s) if "." in s else int(s)


_CONV = conversions.copy()
for _t in (FIELD_TYPE.DECIMAL, FIELD_TYPE.NEWDECIMAL):
    _CONV[_t] = _decimal
for _t in (FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.DATE):
    _CONV[_t] = lambda s: s


def _translate(sql, params):
    """SQLite style '?' placeholders -> MySQL '%s' (literal % are escaped)."""
    if params is None or (isinstance(params, (list, tuple)) and not params):
        return sql, None
    if isinstance(params, dict):
        return sql, params
    return sql.replace("%", "%%").replace("?", "%s"), params


def _local_utc_offset() -> str:
    """The PC's current UTC offset, so CURRENT_TIMESTAMP / CURRENT_DATE are local time
    (the old SQLite schema used 'localtime')."""
    total = int(datetime.now().astimezone().utcoffset().total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


class _Cursor(Cursor):
    def execute(self, query, args=None):
        sql, params = _translate(query, args)
        return super().execute(sql, params)

    def executemany(self, query, args):
        return super().executemany(query.replace("%", "%%").replace("?", "%s"), args)

    def fetchall(self):
        return list(super().fetchall())


class _Connection(Connection):
    def execute(self, sql, params=None):
        """sqlite3 style shortcut: conn.execute(...) returns a cursor."""
        cur = self.cursor()
        cur.execute(sql, params)
        return cur


class Database:
    def __init__(self, **overrides):
        self.config = {
            "host": os.getenv("MYSHOP_DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("MYSHOP_DB_PORT", "3306")),
            "database": os.getenv("MYSHOP_DB_NAME", "myshop"),
            "user": os.getenv("MYSHOP_DB_USER", "myshop"),
            **overrides,
        }
        self._password = self.config.pop("password", None)
        if not re.fullmatch(r"[A-Za-z0-9_]+", self.config["database"]):
            raise DatabaseError("Invalid database name.")

    # ---------- connections ----------
    def _get_password(self):
        if self._password is None:
            if "MYSHOP_DB_PASSWORD" in os.environ:
                self._password = os.environ["MYSHOP_DB_PASSWORD"]
            else:
                self._password = KeyStore().get_password()     # raises KeyStoreError
        return self._password

    def _open(self, use_database=True):
        cfg = self.config
        try:
            return _Connection(
                host=cfg["host"], port=cfg["port"],
                user=cfg["user"], password=self._get_password(),
                database=cfg["database"] if use_database else None,
                charset=CHARSET, autocommit=True,      # transactions are explicit
                cursorclass=_Cursor, conv=_CONV,
                connect_timeout=5,
                init_command=f"SET time_zone = '{_local_utc_offset()}'",
            )
        except pymysql.MySQLError as e:
            raise DatabaseError(
                f"Cannot connect to MySQL at {cfg['host']}:{cfg['port']}: {e}") from e

    def connect(self):
        return self._open()

    @contextmanager
    def transaction(self):
        """
        with db.transaction() as c:
            c.execute(...)
            c.execute(...)      # all or nothing
        Lock rows you are about to change with SELECT ... FOR UPDATE.
        """
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
            raise DatabaseError("MariaDB is not supported (needs MySQL 8.0.23 or newer).")
        nums = tuple(int(x) for x in re.findall(r"\d+", version)[:3])
        if nums < MIN_MYSQL:
            raise DatabaseError(f"MySQL {version} is too old (needs 8.0.23 or newer).")

    def _ensure_database(self):
        conn = self._open(use_database=False)
        try:
            cur = conn.cursor()
            cur.execute("SELECT VERSION()")
            self._check_version(cur.fetchone()[0])
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.config['database']}` "
                        f"CHARACTER SET {CHARSET} COLLATE {COLLATION}")
        except pymysql.MySQLError as e:
            raise DatabaseError(f"Cannot prepare the database: {e}") from e
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


db = Database()   # shared instance: from Database.Schema import db