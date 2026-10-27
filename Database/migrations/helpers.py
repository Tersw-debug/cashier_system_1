TS = "TEXT NOT NULL DEFAULT (datetime('now','localtime'))"


def add_updated_at_trigger(c, table):
    c.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{table}_updated_at
        AFTER UPDATE ON {table}
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
            UPDATE {table} SET updated_at = datetime('now','localtime')
            WHERE id = NEW.id;
        END
    """)


def add_permissions(c, permissions, grants=None):
    """
    permissions: [(code, description), ...]   (all granted to Admin)
    grants: {'Cashier': ['sales.create', ...]} (extra grants for other roles)
    """
    c.executemany("INSERT INTO permissions (code, description) VALUES (?, ?)", permissions)

    c.execute("SELECT id FROM roles WHERE name = 'Admin'")
    admin_id = c.fetchone()[0]
    for code, _ in permissions:
        c.execute("INSERT INTO role_permissions SELECT ?, id FROM permissions WHERE code = ?",
                  (admin_id, code))

    for role, codes in (grants or {}).items():
        c.execute("SELECT id FROM roles WHERE name = ?", (role,))
        role_id = c.fetchone()[0]
        for code in codes:
            c.execute("INSERT INTO role_permissions SELECT ?, id FROM permissions WHERE code = ?",
                      (role_id, code))