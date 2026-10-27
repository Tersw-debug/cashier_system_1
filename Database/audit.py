import json


def write_audit(c, user_id, action, entity, entity_id=None, old=None, new=None, note=None):
    """Call with the cursor of the transaction that makes the change."""
    c.execute("""
        INSERT INTO audit_log (user_id, action, entity, entity_id, old_values, new_values, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, action, entity, entity_id,
        json.dumps(old, ensure_ascii=False) if old is not None else None,
        json.dumps(new, ensure_ascii=False) if new is not None else None,
        note
    ))