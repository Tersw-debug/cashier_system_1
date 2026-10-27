class MigrationError(Exception):
    pass


class Migrator:
    """Applies numbered migrations. Each migration module has VERSION, DESCRIPTION, apply(cursor)."""

    def __init__(self, conn, migrations):
        self.conn = conn
        self.migrations = sorted(migrations, key=lambda m: m.VERSION)
        versions = [m.VERSION for m in self.migrations]
        if len(versions) != len(set(versions)):
            raise MigrationError("Duplicate migration version numbers.")

    def current_version(self) -> int:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        return self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()[0]

    def run(self):
        current = self.current_version()
        newest = self.migrations[-1].VERSION if self.migrations else 0
        if current > newest:
            raise MigrationError("Database is newer than this application.")

        for m in self.migrations:
            if m.VERSION > current:
                self._apply(m)

    def _apply(self, m):
        c = self.conn.cursor()
        c.execute("BEGIN IMMEDIATE")
        try:
            m.apply(c)
            c.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (m.VERSION, m.DESCRIPTION)
            )
            c.execute("COMMIT")
        except Exception as e:
            c.execute("ROLLBACK")
            raise MigrationError(f"Migration {m.VERSION} ({m.DESCRIPTION}) failed: {e}") from e