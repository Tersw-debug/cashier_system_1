from Database.migrations.helpers import TS, add_updated_at_trigger, add_permissions

VERSION = 6
DESCRIPTION = "Employees, attendance, payroll"


def apply(c):
    statements = [
        f"""CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        f"""CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            full_name TEXT NOT NULL,
            phone TEXT,
            national_id TEXT,
            job_title TEXT,
            department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
            hire_date TEXT,
            termination_date TEXT,
            salary_type TEXT NOT NULL DEFAULT 'MONTHLY'
                CHECK (salary_type IN ('MONTHLY','DAILY','HOURLY')),
            base_salary INTEGER NOT NULL DEFAULT 0 CHECK (base_salary >= 0),
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,  -- login account, optional
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS}
        )""",
        """CREATE TABLE attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            work_date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'PRESENT'
                CHECK (status IN ('PRESENT','ABSENT','LATE','LEAVE','HOLIDAY')),
            note TEXT,
            UNIQUE (employee_id, work_date)
        )""",
        f"""CREATE TABLE payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','PAID')),
            journal_entry_id INTEGER REFERENCES journal_entries(id),
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at {TS},
            updated_at {TS},
            CHECK (period_end >= period_start)
        )""",
        """CREATE TABLE payslips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            base_salary INTEGER NOT NULL DEFAULT 0,
            allowances INTEGER NOT NULL DEFAULT 0,
            deductions INTEGER NOT NULL DEFAULT 0,
            advances_deducted INTEGER NOT NULL DEFAULT 0,
            net_pay INTEGER NOT NULL,
            method_id INTEGER REFERENCES payment_methods(id),
            paid_at TEXT,
            UNIQUE (run_id, employee_id)
        )""",
        # allowances, bonuses, deductions and advances; payslip_id is set once applied
        """CREATE TABLE employee_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('ALLOWANCE','BONUS','DEDUCTION','ADVANCE')),
            amount INTEGER NOT NULL CHECK (amount > 0),
            effective_date TEXT NOT NULL DEFAULT (date('now','localtime')),
            note TEXT,
            payslip_id INTEGER REFERENCES payslips(id) ON DELETE SET NULL
        )""",
        "CREATE INDEX idx_adjustments_employee ON employee_adjustments(employee_id)",
        "CREATE INDEX idx_attendance_date ON attendance(work_date)",
    ]
    for sql in statements:
        c.execute(sql)

    for table in ("departments", "employees", "payroll_runs"):
        add_updated_at_trigger(c, table)

    add_permissions(c, [
        ("hr.view",         "View employees and attendance"),
        ("hr.manage",       "Add and edit employees, record attendance"),
        ("payroll.manage",  "Run and post payroll"),
    ])