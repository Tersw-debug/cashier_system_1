"""MySQL-compatible first-run administrator bootstrap using Database.Schema.db."""
import secrets

from Database.Schema import db
from Database.audit import write_audit
from Services.security import PasswordHasher


def ensure_first_admin():
    """Create an administrator with a random password on first run; return it once."""
    with db.transaction() as c:
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0]:
            return None

        # Use '?' placeholders because Database.Schema translates them to PyMySQL's %s.
        c.execute("SELECT id FROM roles WHERE name = ?", ("Admin",))
        role = c.fetchone()
        if not role:
            raise RuntimeError("Required role 'Admin' is missing from the database.")
        role_id = role[0]

        password = secrets.token_urlsafe(9)
        c.execute(
            """INSERT INTO users
               (username, password_hash, full_name, role_id, must_change_password)
               VALUES (?, ?, ?, ?, 1)""",
            ("admin", PasswordHasher.hash(password), "Administrator", role_id),
        )
        user_id = c.lastrowid
        write_audit(c, user_id, "CREATE", "users", user_id, note="first-run admin")
        return password
