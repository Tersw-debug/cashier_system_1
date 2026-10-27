from Database.migrations.helpers import TS, add_updated_at_trigger, add_permissions

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


def apply(c):
    statements = [
        f"""CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
            parent_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            is_system INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        f"""CREATE TABLE journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            entry_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            description TEXT,
            source_type TEXT,            -- 'SALE', 'PURCHASE_INVOICE', 'PAYMENT', 'EXPENSE', ...
            source_id INTEGER,
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT','POSTED','REVERSED')),
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS}
        )""",
        "CREATE INDEX idx_journal_source ON journal_entries(source_type, source_id)",
        "CREATE INDEX idx_journal_date ON journal_entries(entry_date)",
        """CREATE TABLE journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            partner_id INTEGER REFERENCES partners(id),
            debit INTEGER NOT NULL DEFAULT 0 CHECK (debit >= 0),
            credit INTEGER NOT NULL DEFAULT 0 CHECK (credit >= 0),
            description TEXT,
            CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
        )""",
        "CREATE INDEX idx_lines_entry ON journal_lines(entry_id)",
        "CREATE INDEX idx_lines_account ON journal_lines(account_id)",
        "CREATE INDEX idx_lines_partner ON journal_lines(partner_id)",

        # A journal entry must be assembled as DRAFT, then posted only after validation.
        # Explicitly reject callers that try to create a POSTED/REVERSED entry directly.
        """CREATE TRIGGER trg_journal_entries_start_draft
        BEFORE INSERT ON journal_entries
        WHEN NEW.status <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'journal entries must be created as DRAFT');
        END""",
        """CREATE TRIGGER trg_journal_entries_validate_posting
        BEFORE UPDATE OF status ON journal_entries
        WHEN OLD.status = 'DRAFT' AND NEW.status = 'POSTED'
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(*) FROM journal_lines WHERE entry_id = OLD.id) < 2
                THEN RAISE(ABORT, 'cannot post a journal entry with fewer than two lines')
            END;
            SELECT CASE
                WHEN COALESCE((SELECT SUM(debit) FROM journal_lines WHERE entry_id = OLD.id), 0)
                   <> COALESCE((SELECT SUM(credit) FROM journal_lines WHERE entry_id = OLD.id), 0)
                THEN RAISE(ABORT, 'cannot post an unbalanced journal entry')
            END;
        END""",
        # Once posted, header fields are immutable. The only permitted header transition
        # is POSTED -> REVERSED, with all other fields unchanged.
        """CREATE TRIGGER trg_journal_entries_no_update_after_posting
        BEFORE UPDATE ON journal_entries
        WHEN OLD.status <> 'DRAFT'
         AND NOT (
            OLD.status = 'POSTED'
            AND NEW.status = 'REVERSED'
            AND NEW.id IS OLD.id
            AND NEW.number IS OLD.number
            AND NEW.entry_date IS OLD.entry_date
            AND NEW.description IS OLD.description
            AND NEW.source_type IS OLD.source_type
            AND NEW.source_id IS OLD.source_id
            AND NEW.user_id IS OLD.user_id
            AND NEW.created_at IS OLD.created_at
         )
        BEGIN
            SELECT RAISE(ABORT, 'posted journal entries are immutable; post a reversal instead');
        END""",
        """CREATE TRIGGER trg_journal_lines_insert_only_draft
        BEFORE INSERT ON journal_lines
        WHEN COALESCE((SELECT status FROM journal_entries WHERE id = NEW.entry_id), '') <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'journal lines can only be added to DRAFT entries');
        END""",
        """CREATE TRIGGER trg_journal_lines_no_update_after_posting
        BEFORE UPDATE ON journal_lines
        WHEN COALESCE((SELECT status FROM journal_entries WHERE id = OLD.entry_id), '') <> 'DRAFT'
          OR COALESCE((SELECT status FROM journal_entries WHERE id = NEW.entry_id), '') <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'posted journal lines are immutable; post a reversal instead');
        END""",
        """CREATE TRIGGER trg_journal_lines_no_delete_after_posting
        BEFORE DELETE ON journal_lines
        WHEN COALESCE((SELECT status FROM journal_entries WHERE id = OLD.entry_id), '') <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'posted journal lines are immutable; post a reversal instead');
        END""",
        """CREATE TRIGGER trg_journal_entries_no_delete_after_posting
        BEFORE DELETE ON journal_entries
        WHEN OLD.status <> 'DRAFT'
        BEGIN
            SELECT RAISE(ABORT, 'posted journal entries cannot be deleted');
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

        f"""CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            expense_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            account_id INTEGER NOT NULL REFERENCES accounts(id),      -- an EXPENSE account
            method_id INTEGER NOT NULL REFERENCES payment_methods(id),
            partner_id INTEGER REFERENCES partners(id),
            shift_id INTEGER REFERENCES cash_shifts(id),
            amount INTEGER NOT NULL CHECK (amount > 0),
            description TEXT,
            journal_entry_id INTEGER REFERENCES journal_entries(id),
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS}
        )""",
        "CREATE INDEX idx_expenses_date ON expenses(expense_date)",

        # payment methods post to an account (cash drawer vs bank)
        "ALTER TABLE payment_methods ADD COLUMN account_id INTEGER REFERENCES accounts(id)",
    ]
    for sql in statements:
        c.execute(sql)

    add_updated_at_trigger(c, "accounts")

    c.executemany(
        "INSERT INTO accounts (code, name, type, is_system) VALUES (?, ?, ?, 1)", ACCOUNTS
    )
    c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", list(ACCOUNT_SETTINGS.items()))

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
