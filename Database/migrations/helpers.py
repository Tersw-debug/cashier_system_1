"""MySQL 8 helpers shared by all migrations."""

TS = "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
TS_UPDATED = "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_ci"


def add_updated_at_trigger(c, table):
    """No trigger needed in MySQL: the updated_at column refreshes itself on every UPDATE.
    Kept only so any old code that imports it keeps working."""
    c.execute(
        f"ALTER TABLE `{table}` MODIFY updated_at "
        "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )


def add_permissions(c, permissions, grants=None):
    """
    permissions: [(code, description), ...]   (all granted to Admin)
    grants: {'Cashier': ['sales.create', ...]} (extra grants for other roles)
    """
    c.executemany("INSERT INTO permissions (code, description) VALUES (?, ?)", permissions)

    c.execute("SELECT id FROM roles WHERE name = 'Admin'")
    admin_id = c.fetchone()[0]
    for code, _ in permissions:
        c.execute(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT ?, id FROM permissions WHERE code = ?", (admin_id, code))

    for role, codes in (grants or {}).items():
        c.execute("SELECT id FROM roles WHERE name = ?", (role,))
        role_id = c.fetchone()[0]
        for code in codes:
            c.execute(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT ?, id FROM permissions WHERE code = ?", (role_id, code))