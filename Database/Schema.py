import os
from contextlib import contextmanager
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlite3

from Database.keystore import KeyStore
from Database.migrator import Migrator
from Database.migrations import ALL_MIGRATIONS
from Database.recovery import RecoveryEscrow

class DatabaseError(Exception):
    pass


class Database:
    def __init__(self, path=None, keystore=None):
        base = Path(os.getenv("APPDATA") or Path.home()) / "MyShop"
        self.path = Path(path) if path else base / "erp.db"
        self.keystore = keystore or KeyStore()

    # ---------- connections ----------
    def _has_data(self) -> bool:
        return self.path.exists() and self.path.stat().st_size > 0

    def connect(self):
        """Open an encrypted connection in autocommit mode (transactions are explicit)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = self.keystore.get_key(create=not self._has_data())

        conn = sqlite3.connect(str(self.path), isolation_level=None)
        try:
            # raw 256-bit key: skips the slow passphrase key derivation on every open
            conn.execute(f"PRAGMA key = \"x'{key}'\"")
            conn.execute("SELECT count(*) FROM sqlite_master")   # fails if the key is wrong
        except sqlite3.DatabaseError as e:
            conn.close()
            raise DatabaseError("Cannot open the database: wrong key or damaged file.") from e

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def transaction(self):
        """
        with db.transaction() as c:
            c.execute(...)
            c.execute(...)      # all or nothing
        """
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn.cursor()
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
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
    def initialize(self):
        """Create the database if needed and apply every pending migration."""
        conn = self.connect()
        try:
            Migrator(conn, ALL_MIGRATIONS).run()
        finally:
            conn.close()
        self._ensure_recovery_file()

    def _ensure_recovery_file(self):
        target = self.path.parent / "recovery.blob"
        if target.exists():
            return
        escrow = RecoveryEscrow()
        if not escrow.is_configured():
            return                      # no developer key embedded yet
        target.write_text(escrow.seal(self.keystore.get_key()), encoding="ascii")

db = Database()   # shared instance: from Database.Schema import db