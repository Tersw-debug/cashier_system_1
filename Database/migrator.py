class MigrationError(Exception):
    pass


class Migrator:
    """Applies numbered migrations. Each migration module has VERSION, DESCRIPTION, apply(cursor).

    MySQL commits every CREATE/ALTER/DROP immediately, so a failed migration cannot be
    rolled back. If one fails, the schema may be partly migrated.
    """

    LOCK_NAME = "myshop_migrations"

    def __init__(self, conn, migrations):
        self.conn = conn
        self.migrations = sorted(migrations, key=lambda m: m.VERSION)
        versions = [m.VERSION for m in self.migrations]
        if len(versions) != len(set(versions)):
            raise MigrationError("Duplicate migration version numbers.")

    def current_version(self) -> int:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INT NOT NULL PRIMARY KEY,
                description VARCHAR(255) NOT NULL,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        return self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()[0]

    def run(self):
        # one process at a time (two cashiers opening the app together)
        got = self.conn.execute("SELECT GET_LOCK(?, 30)", (self.LOCK_NAME,)).fetchone()[0]
        if got != 1:
            raise MigrationError("Another instance is updating the database. Try again.")
        try:
            current = self.current_version()
            newest = self.migrations[-1].VERSION if self.migrations else 0
            if current > newest:
                raise MigrationError("Database is newer than this application.")
            for m in self.migrations:
                if m.VERSION > current:
                    self._apply(m)
        finally:
            self.conn.execute("SELECT RELEASE_LOCK(?)", (self.LOCK_NAME,)).fetchone()

    def _apply(self, m):
        c = self.conn.cursor()
        try:
            m.apply(c)
            c.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (m.VERSION, m.DESCRIPTION)
            )
        except Exception as e:
            raise MigrationError(
                f"Migration {m.VERSION} ({m.DESCRIPTION}) failed: {e}\n"
                "MySQL cannot undo schema changes, so the database may be partly migrated. "
                "During development: DROP DATABASE and start again. In production: restore the backup."
            ) from e