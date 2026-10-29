"""MySQL 8 helpers shared by all MyShop migrations.

All query parameters use native PyMySQL ``%s`` placeholders. The functions in
this module accept a DB-API cursor (normally the project's MySQL cursor wrapper).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

TS = "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
TS_UPDATED = "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_ci"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def add_updated_at_trigger(c, table: str) -> None:
    """Ensure a table's ``updated_at`` column updates automatically in MySQL.

    The historical function name is retained for compatibility; MySQL handles
    this through the column definition, so no trigger is created.
    """
    if not _IDENTIFIER_RE.fullmatch(table):
        raise ValueError(f"Invalid SQL table identifier: {table!r}")

    c.execute(
        f"ALTER TABLE `{table}` MODIFY COLUMN `updated_at` "
        "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    )


def _role_id(c, role_name: str) -> int:
    """Return a role ID or raise a clear error instead of indexing None."""
    c.execute("SELECT id FROM roles WHERE name = %s LIMIT 1", (role_name,))
    row = c.fetchone()
    if row is None:
        raise RuntimeError(
            f"Cannot assign migration permissions: required role {role_name!r} "
            "does not exist. Ensure the base/security migration creates it first."
        )
    return int(row[0])


def add_permissions(
    c,
    permissions: Iterable[tuple[str, str]],
    grants: Mapping[str, Iterable[str]] | None = None,
) -> None:
    """Seed permissions and role grants using MySQL-compatible SQL.

    ``permissions`` contains ``(code, description)`` pairs. Every listed
    permission is granted to the ``Admin`` role. ``grants`` maps additional
    role names to permission codes, e.g. ``{"Cashier": ["sales.create"]}``.

    This helper is safe to rerun: permission descriptions are refreshed and
    existing role-permission links are ignored rather than duplicated.
    """
    permission_rows = list(permissions)
    if not permission_rows:
        return

    c.executemany(
        """
        INSERT INTO permissions (code, description)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE description = VALUES(description)
        """,
        permission_rows,
    )

    c.execute("SELECT id FROM roles WHERE name = %s", ("Admin",))
    admin_row = c.fetchone()
    if not admin_row:
        raise RuntimeError("Required Admin role was not found.")
    admin_id = admin_row[0]

    for code, _ in permission_rows:
        c.execute(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT %s, id FROM permissions WHERE code = %s",
            (admin_id, code),
        )

    for role_name, codes in (grants or {}).items():
        code_list = list(codes)
        if not code_list:
            continue
        role_id = _role_id(c, role_name)
        c.executemany(
            "INSERT IGNORE INTO role_permissions (role_id, permission_id) "
            "SELECT %s, p.id FROM permissions AS p WHERE p.code = %s",
            [(role_id, code) for code in code_list],
        )
