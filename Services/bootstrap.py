"""First-run administrator bootstrap for the MyShop MySQL database."""
from __future__ import annotations

import secrets

from Database.Schema import db
from Database.audit import write_audit
from Services.security import PasswordHasher


_ADMIN_USERNAME = "admin"
_ADMIN_FULL_NAME = "Administrator"
_ADMIN_ROLE_NAME = "Admin"

# Prevent concurrent application instances from bootstrapping simultaneously.
_BOOTSTRAP_LOCK_NAME = "myshop_first_admin_bootstrap"
_BOOTSTRAP_LOCK_TIMEOUT = 10


def ensure_first_admin() -> str | None:
    """Create the first administrator when the users table is empty.

    Returns:
        The generated plaintext password when an administrator is created.
        None when at least one user already exists.

    The generated password is returned only to the caller so that it can be
    displayed once during first-run setup. Only its hash is stored in MySQL.

    Raises:
        RuntimeError: If the bootstrap lock cannot be acquired or the required
            Admin role does not exist.
        Database errors: Propagated to the caller; the transaction is rolled
            back by Database.transaction().
    """
    with db.transaction() as c:
        # GET_LOCK is connection-scoped. Database.transaction() closes its
        # connection after commit/rollback, automatically releasing the lock.
        c.execute(
            "SELECT GET_LOCK(%s, %s)",
            (_BOOTSTRAP_LOCK_NAME, _BOOTSTRAP_LOCK_TIMEOUT),
        )
        lock_row = c.fetchone()

        if lock_row is None or lock_row[0] != 1:
            raise RuntimeError(
                "Could not acquire the first-admin bootstrap lock. "
                "Another instance may be initializing the application. "
                "Please try again."
            )

        # We only need to know whether any user exists.
        c.execute("SELECT id FROM users LIMIT 1")

        if c.fetchone() is not None:
            return None

        # Resolve the administrator role before creating the user.
        c.execute(
            "SELECT id FROM roles WHERE name = %s LIMIT 1",
            (_ADMIN_ROLE_NAME,),
        )
        role_row = c.fetchone()

        if role_row is None:
            raise RuntimeError(
                "The required 'Admin' role does not exist. "
                "Run the core/security database migration first."
            )

        role_id = int(role_row[0])

        # Generate a password for the first login.
        password = secrets.token_urlsafe(9)
        password_hash = PasswordHasher.hash(password)

        c.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role_id,
                must_change_password
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                _ADMIN_USERNAME,
                password_hash,
                _ADMIN_FULL_NAME,
                role_id,
                1,
            ),
        )

        user_id = c.lastrowid

        if not user_id:
            raise RuntimeError(
                "The administrator was not created successfully."
            )

        # Keep the audit entry in the same transaction as the user creation.
        write_audit(
            c,
            user_id,
            "CREATE",
            "users",
            user_id,
            note="first-run admin",
        )

        return password