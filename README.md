# 🧾 Cashier System (Supermarket POS Desktop App)

A full-featured **Point of Sale (POS) desktop application** designed for supermarkets and retail stores.

It supports:
- Sales processing
- Barcode scanning
- Inventory management
- Customer tracking
- Sales restoration
- PDF reporting

Built using a modular architecture in **Python + CustomTkinter + SQLite (SQLCipher)**.

---

## 🚀 Features

### 🛒 Cashier (POS System)
- Add products via:
  - Name search
  - Barcode scanning (`pyzbar + OpenCV`)
- Live cart system
- Quantity adjustment (increase / delete items)
- Automatic total calculation per item and full invoice

---

### 📦 Inventory Management
- Automatic stock updates after sales
- Inventory tracking system
- Product quantity management
- Full inventory history logging
- Safe rollback support via restore system

---

### 👤 Customer Management
- Optional customer linking per sale
- Stores:
  - Customer name
  - Phone number
  - Debt tracking
- Automatic debt calculation and updates

---

### 🔁 Sales Restoration System
- Restore previous sales using:
  - Sale ID
  - Customer validation
- Automatically restores:
  - Product stock
  - Customer debt
  - Sale records

---

### 📊 Reporting System
- Generates PDF reports using `reportlab`
- Supports Arabic text rendering using:
  - `arabic_reshaper`
  - `python-bidi`
- Reports include:
  - Inventory reports
  - Sales summaries

---

### 🔐 Authentication System
- Login system for:
  - Admin
  - Cashier
- Role-based access control

---

### 📷 Barcode Scanner Integration
- Uses:
  - `OpenCV`
  - `pyzbar`
- Real-time barcode scanning via camera
- Automatically adds products to cart

---

### 🎨 Modern GUI
- Built with:
  - `CustomTkinter`
  - `Tkinter`
- Clean, responsive interface
- Dark/Light theme support
- Separate Admin & Cashier dashboards

---

## 🧱 Project Architecture

The system follows a layered architecture:

📦 Project Root
├── UI/ → User Interface (Tkinter / CustomTkinter)
├── Services/ → Business Logic Layer
├── Domain/ → Core Models (Product, Cart, Sale)
├── Database/ → Database Schema & Connection
├── Infrastructure/ → External integrations (future expansion)


---

## 🖥 UI Modules

### 👨‍💼 Admin Panel
Handles:
- Product management
- Inventory control
- User management
- Reports & analytics

### 🧾 Cashier Panel
Handles:
- Product scanning & search
- Cart management
- Checkout process
- Customer handling
- Sales restoration

---

## 📂 Project Structure
.
├── main.py
├── UI/
│ ├── ui_admin.py
│ ├── ui_cashier.py
│ ├── login_ui.py
│ ├── router.py
│ └── assets/
│
├── Services/
│ ├── admin_service.py
│ ├── cashier_service.py
│ └── auth.py
│
├── Domain/
│ ├── product.py
│ ├── cart.py
│ └── sale.py
│
├── Database/
│ ├── Schema.py
│ └── .env
│
├── output/
│ ├── build/
│ └── dist/
│
└── reports/
├── inventory_history.pdf
└── storage_report.pdf


---

## 🛠 Tech Stack

- Python 3
- CustomTkinter / Tkinter
- SQLite / SQLCipher
- OpenCV
- pyzbar (barcode scanning)
- ReportLab (PDF generation)
- Pandas / OpenPyXL
- Arabic text rendering libraries

---

## ▶️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-repo/cashier-system.git
cd cashier-system

2. Install dependencies
pip install customtkinter opencv-python pyzbar reportlab arabic-reshaper python-bidi openpyxl pandas sqlcipher3

🚀 Run the Application
python main.py

📦 Build Executable (Optional)
pyinstaller --onefile --windowed main.py
