from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS, add_permissions

VERSION = 5
DESCRIPTION = "Chart of accounts, journal, expenses"

ACCOUNTS = [
    ("1000", "النقدية",                    "ASSET"),
    ("1010", "البنك",                      "ASSET"),
    ("1100", "العملاء (ذمم مدينة)",        "ASSET"),
    ("1200", "المخزون",                    "ASSET"),
    ("2000", "الموردون (ذمم دائنة)",       "LIABILITY"),
    ("2100", "ضريبة القيمة المضافة المستحقة", "LIABILITY"),
    ("3000", "رأس المال",                  "EQUITY"),
    ("4000", "إيرادات المبيعات",           "REVENUE"),
    ("4100", "مردودات المبيعات",           "REVENUE"),
    ("5000", "تكلفة البضاعة المباعة",      "EXPENSE"),
    ("5100", "تسويات المخزون",             "EXPENSE"),
    ("6000", "الرواتب والأجور",            "EXPENSE"),
    ("6100", "الإيجار",                    "EXPENSE"),
    ("6200", "المرافق",                    "EXPENSE"),
    ("6900", "مصروفات أخرى",               "EXPENSE"),
]

# which account each service uses; changeable in settings
ACCOUNT_SETTINGS = {
    "account.cash": "1000", "account.bank": "1010", "account.receivable": "1100",
    "account.inventory": "1200", "account.payable": "2000", "account.tax_payable": "2100",
    "account.equity": "3000", "account.sales": "4000", "account.sales_returns": "4100",
    "account.cogs": "5000", "account.inventory_adjustment": "5100", "account.salaries": "6000",
}


def _signal(message):
    return f"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{message}';"


def apply(c):
    statements = [
        f"""CREATE TABLE accounts (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(20) NOT NULL UNIQUE,
            name VARCHAR(150) NOT NULL,
            `type` VARCHAR(20) NOT NULL,
            parent_id INT NULL,
            is_system TINYINT(1) NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_account_type CHECK (`type` IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
            FOREIGN KEY (parent_id) REFERENCES accounts(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",

        # source_type: 'SALE', 'PURCHASE_INVOICE', 'PAYMENT', 'EXPENSE', ...
        f"""CREATE TABLE journal_entries (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            entry_date DATE NOT NULL DEFAULT (CURRENT_DATE),
            description TEXT,
            source_type VARCHAR(50) NULL,
            source_id INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
            user_id INT NULL,
            created_at {TS},
            CONSTRAINT chk_je_status CHECK (status IN ('DRAFT','POSTED','REVERSED')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_journal_source ON journal_entries(source_type, source_id)",
        "CREATE INDEX idx_journal_date ON journal_entries(entry_date)",
        f"""CREATE TABLE journal_lines (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            entry_id INT NOT NULL,
            account_id INT NOT NULL,
            partner_id INT NULL,
            debit BIGINT NOT NULL DEFAULT 0,
            credit BIGINT NOT NULL DEFAULT 0,
            description TEXT,
            CONSTRAINT chk_jl_amounts CHECK (debit >= 0 AND credit >= 0
                AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))),
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (partner_id) REFERENCES partners(id)
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_lines_account ON journal_lines(account_id)",
        "CREATE INDEX idx_lines_partner ON journal_lines(partner_id)",

        # A journal entry must be assembled as DRAFT, then posted only after validation.
        # (Triggers do not fire for ON DELETE CASCADE in MySQL; that only affects DRAFT
        # entries, because deleting a non-draft entry is blocked below.)
        f"""CREATE TRIGGER trg_journal_entries_start_draft
        BEFORE INSERT ON journal_entries
        FOR EACH ROW
        BEGIN
            IF NEW.status <> 'DRAFT' THEN
                {_signal('journal entries must be created as DRAFT')}
            END IF;
        END""",
        f"""CREATE TRIGGER trg_journal_entries_validate_posting
        BEFORE UPDATE ON journal_entries
        FOR EACH ROW
        BEGIN
            IF OLD.status = 'DRAFT' AND NEW.status = 'POSTED' THEN
                IF (SELECT COUNT(*) FROM journal_lines WHERE entry_id = OLD.id) < 2 THEN
                    {_signal('cannot post a journal entry with fewer than two lines')}
                END IF;
                IF COALESCE((SELECT SUM(debit) FROM journal_lines WHERE entry_id = OLD.id), 0)
                   <> COALESCE((SELECT SUM(credit) FROM journal_lines WHERE entry_id = OLD.id), 0) THEN
                    {_signal('cannot post an unbalanced journal entry')}
                END IF;
            END IF;
        END""",
        # Once posted, header fields are immutable. The only permitted header transition
        # is POSTED -> REVERSED, with all other fields unchanged.
        f"""CREATE TRIGGER trg_journal_entries_no_update_after_posting
        BEFORE UPDATE ON journal_entries
        FOR EACH ROW
        BEGIN
            IF OLD.status <> 'DRAFT'
               AND NOT (
                    OLD.status = 'POSTED'
                    AND NEW.status = 'REVERSED'
                    AND NEW.id <=> OLD.id
                    AND NEW.number <=> OLD.number
                    AND NEW.entry_date <=> OLD.entry_date
                    AND NEW.description <=> OLD.description
                    AND NEW.source_type <=> OLD.source_type
                    AND NEW.source_id <=> OLD.source_id
                    AND NEW.user_id <=> OLD.user_id
                    AND NEW.created_at <=> OLD.created_at
               ) THEN
                {_signal('posted journal entries are immutable; post a reversal instead')}
            END IF;
        END""",
        f"""CREATE TRIGGER trg_journal_lines_insert_only_draft
        BEFORE INSERT ON journal_lines
        FOR EACH ROW
        BEGIN
            IF COALESCE((SELECT status FROM journal_entries WHERE id = NEW.entry_id), '') <> 'DRAFT' THEN
                {_signal('journal lines can only be added to DRAFT entries')}
            END IF;
        END""",
        f"""CREATE TRIGGER trg_journal_lines_no_update_after_posting
        BEFORE UPDATE ON journal_lines
        FOR EACH ROW
        BEGIN
            IF COALESCE((SELECT status FROM journal_entries WHERE id = OLD.entry_id), '') <> 'DRAFT'
               OR COALESCE((SELECT status FROM journal_entries WHERE id = NEW.entry_id), '') <> 'DRAFT' THEN
                {_signal('posted journal lines are immutable; post a reversal instead')}
            END IF;
        END""",
        f"""CREATE TRIGGER trg_journal_lines_no_delete_after_posting
        BEFORE DELETE ON journal_lines
        FOR EACH ROW
        BEGIN
            IF COALESCE((SELECT status FROM journal_entries WHERE id = OLD.entry_id), '') <> 'DRAFT' THEN
                {_signal('posted journal lines are immutable; post a reversal instead')}
            END IF;
        END""",
        f"""CREATE TRIGGER trg_journal_entries_no_delete_after_posting
        BEFORE DELETE ON journal_entries
        FOR EACH ROW
        BEGIN
            IF OLD.status <> 'DRAFT' THEN
                {_signal('posted journal entries cannot be deleted')}
            END IF;
        END""",

        # Audit backstop: should be empty for every POSTED/REVERSED entry.
        # The LEFT JOIN also detects entries with no lines.
        """CREATE VIEW v_unbalanced_entries AS
        SELECT
            je.id AS entry_id,
            COALESCE(SUM(jl.debit), 0) AS total_debit,
            COALESCE(SUM(jl.credit), 0) AS total_credit
        FROM journal_entries je
        LEFT JOIN journal_lines jl ON jl.entry_id = je.id
        WHERE je.status IN ('POSTED', 'REVERSED')
        GROUP BY je.id
        HAVING COUNT(jl.id) < 2
            OR COALESCE(SUM(jl.debit), 0) <> COALESCE(SUM(jl.credit), 0)""",

        # account_id must be an EXPENSE account
        f"""CREATE TABLE expenses (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            expense_date DATE NOT NULL DEFAULT (CURRENT_DATE),
            account_id INT NOT NULL,
            method_id INT NOT NULL,
            partner_id INT NULL,
            shift_id INT NULL,
            amount BIGINT NOT NULL,
            description TEXT,
            journal_entry_id INT NULL,
            user_id INT NULL,
            created_at {TS},
            CONSTRAINT chk_expense_amount CHECK (amount > 0),
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (method_id) REFERENCES payment_methods(id),
            FOREIGN KEY (partner_id) REFERENCES partners(id),
            FOREIGN KEY (shift_id) REFERENCES cash_shifts(id),
            FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_expenses_date ON expenses(expense_date)",

        # payment methods post to an account (cash drawer vs bank)
        "ALTER TABLE payment_methods ADD COLUMN account_id INT NULL, "
        "ADD CONSTRAINT fk_payment_methods_account FOREIGN KEY (account_id) REFERENCES accounts(id)",
    ]
    for sql in statements:
        c.execute(sql)

    c.executemany(
        "INSERT INTO accounts (code, name, `type`, is_system) VALUES (?, ?, ?, 1)", ACCOUNTS
    )
    c.executemany("INSERT INTO settings (`key`, `value`) VALUES (?, ?)", list(ACCOUNT_SETTINGS.items()))

    c.execute("""UPDATE payment_methods SET account_id =
                 (SELECT id FROM accounts WHERE code = '1000') WHERE kind = 'CASH'""")
    c.execute("""UPDATE payment_methods SET account_id =
                 (SELECT id FROM accounts WHERE code = '1010') WHERE kind <> 'CASH'""")

    add_permissions(c, [
        ("accounting.view",  "View accounts and journal"),
        ("accounting.post",  "Post manual journal entries"),
        ("expenses.view",    "View expenses"),
        ("expenses.create",  "Record expenses"),
        ("reports.view",     "View reports"),
    ])