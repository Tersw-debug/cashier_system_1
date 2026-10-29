from Database.Schema import db
from .security import PasswordHasher


def login(username: str, password: str) -> tuple[bool, str | None]:
    """Authenticate a user and update their login metadata."""

    row = db.fetch_one(
        """
        SELECT u.id, u.password_hash, r.name, u.is_active
        FROM users AS u
        JOIN roles AS r ON r.id = u.role_id
        WHERE u.username = %s
        LIMIT 1
        """,
        (username,),
    )

    if row is None:
        return False, None

    user_id, password_hash, role_name, is_active = row

    if not is_active or not PasswordHasher.verify(password, password_hash):
        return False, None

    with db.transaction() as c:
        c.execute(
            """
            UPDATE users
            SET last_login_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (user_id,),
        )

        # Upgrade older password hashes after successful authentication.
        if PasswordHasher.needs_rehash(password_hash):
            c.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
                """,
                (PasswordHasher.hash(password), user_id),
            )

    return True, role_name