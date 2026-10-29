from Database.migrations.helpers import TS, TABLE_OPTS

VERSION = 7
DESCRIPTION = "Manual customer debt adjustments (add / remove / update) with audit trail"


def apply(c):
    statements = [
        # Every manual change to a customer's debt is one immutable row here.
        # kind ADD    -> the customer owes more   (+amount)
        # kind REMOVE -> the customer owes less   (-amount, write-off)
        # "Update debt" is stored as the ADD or REMOVE needed to reach the new value.
        # Customer debt = v_customer_balances.balance + SUM(ADD) - SUM(REMOVE).
        f"""CREATE TABLE customer_debt_adjustments (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            partner_id INT NOT NULL,
            kind VARCHAR(10) NOT NULL,
            amount BIGINT NOT NULL,
            reason TEXT NOT NULL,
            user_id INT NULL,
            shift_id INT NULL,
            created_at {TS},
            CONSTRAINT chk_debt_adj_kind CHECK (kind IN ('ADD','REMOVE')),
            CONSTRAINT chk_debt_adj_amount CHECK (amount > 0),
            FOREIGN KEY (partner_id) REFERENCES partners(id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (shift_id) REFERENCES cash_shifts(id)
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_debt_adj_partner ON customer_debt_adjustments(partner_id)",

        # Append-only, like stock_movements: history can never be edited or erased.
        """CREATE TRIGGER trg_debt_adj_no_update
        BEFORE UPDATE ON customer_debt_adjustments
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'customer_debt_adjustments is append-only'""",
        """CREATE TRIGGER trg_debt_adj_no_delete
        BEFORE DELETE ON customer_debt_adjustments
        FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'customer_debt_adjustments is append-only'""",
    ]
    for sql in statements:
        c.execute(sql)

    c.execute(
        """
        INSERT IGNORE INTO doc_sequences
            (name, prefix, next_number, padding)
        VALUES ('DEBT_ADJ', 'DBT-', 1, 6)
        """
    )