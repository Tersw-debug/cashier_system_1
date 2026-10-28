from Database.migrations.helpers import TS, TS_UPDATED, TABLE_OPTS, add_permissions

VERSION = 6
DESCRIPTION = "Employees, attendance, payroll"


def apply(c):
    statements = [
        f"""CREATE TABLE departments (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL UNIQUE,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED}
        ) {TABLE_OPTS}""",

        # user_id = login account, optional
        f"""CREATE TABLE employees (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) UNIQUE,
            full_name VARCHAR(150) NOT NULL,
            phone VARCHAR(40),
            national_id VARCHAR(50),
            job_title VARCHAR(100),
            department_id INT NULL,
            hire_date DATE NULL,
            termination_date DATE NULL,
            salary_type VARCHAR(10) NOT NULL DEFAULT 'MONTHLY',
            base_salary BIGINT NOT NULL DEFAULT 0,
            user_id INT NULL UNIQUE,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_emp_salary_type CHECK (salary_type IN ('MONTHLY','DAILY','HOURLY')),
            CONSTRAINT chk_emp_salary CHECK (base_salary >= 0),
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",

        # check_in / check_out are full date-times: 'YYYY-MM-DD HH:MM:SS'
        f"""CREATE TABLE attendance (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            employee_id INT NOT NULL,
            work_date DATE NOT NULL,
            check_in DATETIME NULL,
            check_out DATETIME NULL,
            status VARCHAR(10) NOT NULL DEFAULT 'PRESENT',
            note TEXT,
            UNIQUE KEY uq_attendance_day (employee_id, work_date),
            CONSTRAINT chk_att_status CHECK (status IN ('PRESENT','ABSENT','LATE','LEAVE','HOLIDAY')),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        ) {TABLE_OPTS}""",
        "CREATE INDEX idx_attendance_date ON attendance(work_date)",

        f"""CREATE TABLE payroll_runs (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            number VARCHAR(40) NOT NULL UNIQUE,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            status VARCHAR(10) NOT NULL DEFAULT 'DRAFT',
            journal_entry_id INT NULL,
            created_by INT NULL,
            created_at {TS},
            updated_at {TS_UPDATED},
            CONSTRAINT chk_pr_status CHECK (status IN ('DRAFT','POSTED','PAID')),
            CONSTRAINT chk_pr_period CHECK (period_end >= period_start),
            FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
        f"""CREATE TABLE payslips (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            run_id INT NOT NULL,
            employee_id INT NOT NULL,
            base_salary BIGINT NOT NULL DEFAULT 0,
            allowances BIGINT NOT NULL DEFAULT 0,
            deductions BIGINT NOT NULL DEFAULT 0,
            advances_deducted BIGINT NOT NULL DEFAULT 0,
            net_pay BIGINT NOT NULL,
            method_id INT NULL,
            paid_at DATETIME NULL,
            UNIQUE KEY uq_payslip_run_employee (run_id, employee_id),
            FOREIGN KEY (run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (method_id) REFERENCES payment_methods(id)
        ) {TABLE_OPTS}""",

        # allowances, bonuses, deductions and advances; payslip_id is set once applied
        f"""CREATE TABLE employee_adjustments (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            employee_id INT NOT NULL,
            kind VARCHAR(10) NOT NULL,
            amount BIGINT NOT NULL,
            effective_date DATE NOT NULL DEFAULT (CURRENT_DATE),
            note TEXT,
            payslip_id INT NULL,
            CONSTRAINT chk_adj_kind CHECK (kind IN ('ALLOWANCE','BONUS','DEDUCTION','ADVANCE')),
            CONSTRAINT chk_adj_amount CHECK (amount > 0),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (payslip_id) REFERENCES payslips(id) ON DELETE SET NULL
        ) {TABLE_OPTS}""",
    ]
    for sql in statements:
        c.execute(sql)

    add_permissions(c, [
        ("hr.view",         "View employees and attendance"),
        ("hr.manage",       "Add and edit employees, record attendance"),
        ("payroll.manage",  "Run and post payroll"),
    ])