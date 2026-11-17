# 🧾 MyShop ERP — Retail Management & POS Desktop Application

A modular **Retail ERP and Point of Sale (POS) desktop application** built for supermarkets and retail stores.

MyShop combines cashier operations, inventory management, customer accounts, sales processing, reporting, and administrative tools in a single desktop application.

The project follows a layered architecture that separates the presentation layer, business logic, domain models, and database infrastructure.

**Built with Python, PySide6, SQLite/SQLCipher, and a modular service-oriented architecture.**

---

## 🚀 Features

### 🛒 1. Point of Sale (POS)

A dedicated cashier interface for everyday sales operations.

- Product selection through product search.
- Barcode scanning integration using OpenCV and pyzbar.
- Interactive shopping cart.
- Quantity adjustment and item removal.
- Automatic item subtotal and invoice total calculation.
- Customer association with sales.
- Sales processing and payment handling.
- Stock updates following completed sales.

### 📦 2. Inventory Management

Inventory operations integrated with the sales workflow.

- Product and catalog management.
- Stock quantity tracking.
- Inventory updates following sales.
- Inventory history and movement tracking.
- Inventory adjustments.
- Historical inventory reporting.
- Support for restoring stock following eligible sale reversals.

### 👤 3. Customer Management

Customer records and account management.

- Customer registration and information management.
- Customer association with sales.
- Customer debt tracking.
- Automatic debt calculation and updates.
- Customer payment and account history.

### 🔁 4. Sales Restoration & Recovery

Tools for handling sales reversals and database recovery.

- Restore eligible previous sales.
- Validate sales before restoration.
- Restore affected product quantities.
- Reconcile customer debt.
- Maintain database consistency during restoration.
- Dedicated recovery utilities.

### 📊 5. Reporting & Exporting

Reporting functionality for administrative and financial operations.

- PDF report generation using ReportLab.
- Arabic PDF rendering using:
  - `arabic_reshaper`
  - `python-bidi`
  - Amiri Arabic font.
- Excel sales register generation.
- Date-based cashier report organization.
- Inventory and sales reporting.

Excel reports are organized by date under `Cashier_Reports/`.

### 🔐 6. Authentication & Security

A separate authentication and security layer.

- User authentication.
- Admin and cashier roles.
- Role-based access control.
- Security-related services.
- Database key management.
- Audit logging.
- Database recovery utilities.

### 🏢 7. ERP Database Modules

The database architecture is organized into versioned migrations.

Current migration coverage includes:

| Migration | Module |
|---|---|
| `m001` | Core system and product catalog |
| `m002` | Inventory |
| `m003` | Partners and purchasing |
| `m004` | Sales and payments |
| `m005` | Accounting |
| `m006` | Human resources |
| `m007` | Customer debt |

These migrations establish the database structure for the broader ERP system. The existence of a database module does not necessarily imply that all corresponding user-facing workflows are implemented.

---

## 🎨 User Interface

The application uses **PySide6 (Qt Widgets)** for its native desktop interface.

### 👨‍💼 Admin Dashboard

Administrative functionality includes:

- Product and catalog management.
- Inventory management.
- User management.
- Sales and reporting operations.
- Administrative data views.

### 🧾 Cashier Dashboard

The cashier interface focuses on:

- Product search and selection.
- Barcode scanning.
- Cart management.
- Checkout and payment processing.
- Customer handling.
- Sales restoration.

### UI Implementation

- Native PySide6 widgets.
- Qt model/view architecture for tabular data.
- `QTableView` for structured administrative data.
- Separate presentation and business logic layers.
- Arabic right-to-left (RTL) interface support.
- Shared UI components and styling utilities.

---

## 🧱 Architecture

The project follows a layered architecture designed to separate responsibilities and keep the application maintainable.

```text
┌──────────────────────────────────────────────┐
│               Presentation Layer             │
│                                              │
│             UI / PySide6 / Qt                │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                Service Layer                 │
│                                              │
│      Authentication / Admin / Cashier        │
│       Business Operations / Bootstrap       │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│                 Domain Layer                 │
│                                              │
│            Product / Cart / Sale             │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│              Database Layer                  │
│                                              │
│       SQLite / SQLCipher / Migrations        │
│        Audit / Key Management / Recovery     │
└──────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| `UI/` | Qt widgets, screens, navigation, and presentation |
| `Services/` | Business operations, authentication, and application services |
| `Domain/` | Core business entities and domain models |
| `Database/` | Database schema, migrations, connections, security, and recovery |
| `Infrastructure/` | Reserved for external integrations and infrastructure components |

**Design principle:** UI components should handle presentation and user interaction, while business operations belong in the service layer rather than being implemented directly inside screens.

---

## 📂 Project Structure

```text
.
├── main.py
├── README.md
├── Amiri-Regular.ttf
│
├── Database/
│   ├── Schema.py
│   ├── audit.py
│   ├── keystore.py
│   ├── migrator.py
│   ├── recovery.py
│   │
│   └── migrations/
│       ├── helpers.py
│       ├── m001_core_and_catalog.py
│       ├── m002_inventory.py
│       ├── m003_partners_purchasing.py
│       ├── m004_sales_payments.py
│       ├── m005_accounting.py
│       ├── m006_hr.py
│       ├── m007_customer_debt.py
│       └── __init__.py
│
├── Domain/
│   ├── product.py
│   ├── cart.py
│   └── sale.py
│
├── Services/
│   ├── admin_service.py
│   ├── cashier_service.py
│   ├── auth.py
│   ├── security.py
│   ├── bootstrap.py
│   └── seed_catalog.py
│
├── UI/
│   ├── basewindow.py
│   ├── common.py
│   ├── login_page.py
│   ├── login_ui.py
│   ├── router.py
│   ├── rtl.py
│   ├── sell_ui.py
│   ├── ui_admin.py
│   ├── ui_cashier.py
│   │
│   └── assets/
│       ├── add.png
│       ├── background.png
│       ├── money.png
│       ├── search.png
│       ├── statistics.png
│       ├── storage.png
│       └── users.png
│
├── Cashier_Reports/
│   └── YYYY-MM-DD/
│       └── Sales_Register.xlsx
│
├── output/
│   └── main.spec
│
├── recovery_tool.py
├── get_password.py
├── seed_print_catalog.py
└── seed_print_catalog_once.py
```

Generated files, `__pycache__`, local environment files, and other runtime artifacts are omitted from this overview.

---

## 🛠 Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python 3 |
| Desktop GUI | PySide6 / Qt Widgets |
| Database | SQLite / SQLCipher |
| Database Architecture | Versioned schema migrations |
| Data Presentation | Qt Model/View (`QTableView`) |
| PDF Generation | ReportLab |
| Arabic Rendering | arabic-reshaper / python-bidi |
| Arabic Font | Amiri |
| Excel Processing | OpenPyXL / Pandas |
| Barcode Scanning | OpenCV / pyzbar |
| Executable Packaging | PyInstaller |

---

## 🗄 Database & Data Storage

The application uses an SQLite database with SQLCipher support for database encryption.

On Windows, the application database is stored in:

```text
%APPDATA%\MyShop\shop.db
```

### Database Management

The database layer includes:

- Centralized schema management.
- Versioned database migrations.
- Migration helpers.
- Database key management.
- Audit logging.
- Database recovery utilities.

The migration system separates schema evolution into individual, ordered migration files, making future database changes easier to manage.

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd MyShop
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

Install the project dependencies in the virtual environment.

The following is a baseline installation command; keep it synchronized with the project's actual imports:

```bash
python -m pip install PySide6 sqlcipher3 reportlab arabic-reshaper python-bidi openpyxl pandas opencv-python pyzbar
```

### 4. Configure the application

Configure the required local environment variables and database security settings.

Keep private keys and other sensitive configuration files outside version control.

### 5. Run the application

```bash
python main.py
```

---

## 📦 Building the Executable

The project includes a PyInstaller specification:

```text
output/main.spec
```

Build using:

```bash
python -m PyInstaller output/main.spec
```

Review the generated build configuration when adding new assets, fonts, database dependencies, or other external resources.

---

## 🔒 Security & Repository Hygiene

The application uses database encryption and separate security-related components.

The following files and data should remain private and must not be committed to a public repository:

- `.env` files.
- `developer_private.pem`.
- Database encryption keys and credentials.
- Production database files.
- Database backups containing real customer data.
- Sensitive generated reports.

If a private key has already been committed or pushed, removing it from the latest commit is not sufficient; the key should be replaced or revoked.

---

## 🎯 Project Goals

MyShop is intended to provide a maintainable foundation for a retail ERP system.

Its architecture separates the UI, business operations, domain logic, and persistence layers, allowing individual modules to evolve without unnecessarily coupling the entire application.

Future development can expand the purchasing, accounting, HR, inventory, and reporting capabilities while maintaining a consistent application architecture.

