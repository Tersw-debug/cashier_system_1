from Database.Schema import db
from .security import PasswordHasher


def login(username, password):
    row = db.fetch_one("""
        SELECT u.id, u.password_hash, r.name, u.is_active
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.username = ?
    """, (username,))

    if row is None:
        return False, None

    user_id, password_hash, role_name, is_active = row

    if not is_active or not PasswordHasher.verify(password, password_hash):
        return False, None

    with db.transaction() as c:
        c.execute("UPDATE users SET last_login_at = datetime('now','localtime') WHERE id = ?",
                  (user_id,))
        if PasswordHasher.needs_rehash(password_hash):      # silently migrate old PBKDF2 users
            c.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                      (PasswordHasher.hash(password), user_id))

    return True, role_name