from __future__ import annotations

import sys
from pathlib import Path
from tkinter import messagebox

from Database.Schema import db, DatabaseError
from Database.migrator import MigrationError
from Database.keystore import KeyStoreError
from Services.bootstrap import ensure_first_admin


SEED_CATALOG_FLAG = "--seed-print-catalog-once"
SEED_MARKER_KEY = "seed_print_catalog_v1"
SEED_LOCK_NAME = "myshop_catalog_seed_v1"
SEED_LOCK_TIMEOUT_SECONDS = 10
SEED_MODE = SEED_CATALOG_FLAG in sys.argv


def register_fonts() -> None:
    """Register Amiri for PDF reports in source and PyInstaller builds."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Prefer a font shipped beside the executable/source, then fall back to
    # PyInstaller's bundled resource directory (when running a frozen build).
    app_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    candidates = [app_dir / "Amiri-Regular.ttf"]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "Amiri-Regular.ttf")

    font_path = next((path for path in candidates if path.is_file()), None)
    if font_path is None:
        searched = "\n".join(str(path) for path in candidates)
        raise FileNotFoundError(
            "Required report font Amiri-Regular.ttf was not found. Searched:\n"
            f"{searched}"
        )

    if not pdfmetrics.getRegisteredFontNames() or "Amiri" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Amiri", str(font_path)))


def run_catalog_seed_once() -> None:
    """Run the existing Services catalog seeder once, without opening the GUI.

    A persistent marker prevents a successful seed from running again. The
    'running' state deliberately blocks silent retries after an interrupted or
    failed seed, because the current seeder skips existing SKUs and cannot
    guarantee repair of partially seeded opening stock.
    """
    # Lazy imports keep UI/reporting dependencies out of seed-only mode.
    from Services import admin_service as admin_svc
    from Services.seed_catalog import seed_print_catalog

    conn = db.connect()
    cursor = None
    lock_acquired = False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT GET_LOCK(%s, %s)",
            (SEED_LOCK_NAME, SEED_LOCK_TIMEOUT_SECONDS),
        )
        lock_row = cursor.fetchone()
        if lock_row is None or lock_row[0] != 1:
            raise RuntimeError(
                "تعذر الحصول على قفل تجهيز الكتالوج. قد تكون عملية تجهيز أخرى قيد التشغيل."
            )
        lock_acquired = True

        marker_row = cursor.execute(
            "SELECT value FROM settings WHERE `key` = %s LIMIT 1",
            (SEED_MARKER_KEY,),
        ).fetchone()
        marker_value = str(marker_row[0]) if marker_row and marker_row[0] is not None else None

        if marker_value == "completed":
            print("Catalog seed has already completed. No changes were made.")
            return
        if marker_value == "running":
            raise RuntimeError(
                "يوجد تسجيل سابق بأن تجهيز الكتالوج بدأ ولم يكتمل. "
                "لم تتم إعادة التشغيل تلقائيًا لتجنب تخطي منتجات قد تكون بلا مخزون افتتاحي. "
                "افحص المنتجات وحركات المخزون أولًا، ثم عالج المفتاح "
                f"{SEED_MARKER_KEY!r} يدويًا إذا لزم الأمر."
            )

        # The user asked to run this after the normal application has created
        # the initial administrator. The seeder writes its audit entries as admin.
        admin_id = admin_svc.get_username_id("admin")
        if admin_id is None:
            raise RuntimeError(
                "لم يتم العثور على حساب admin نشط. افتح التطبيق بصورة طبيعية "
                "وأنشئ حساب المدير قبل تشغيل ملف تجهيز الكتالوج."
            )

        # Persist 'running' before creating records so interrupted runs are
        # detectable. The DB layer uses autocommit=True for this connection.
        cursor.execute(
            """
            INSERT INTO settings (`key`, `value`)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value` = VALUES(`value`),
                                    updated_at = CURRENT_TIMESTAMP
            """,
            (SEED_MARKER_KEY, "running"),
        )

        result = seed_print_catalog(username="admin")

        cursor.execute(
            """
            INSERT INTO settings (`key`, `value`)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value` = VALUES(`value`),
                                    updated_at = CURRENT_TIMESTAMP
            """,
            (SEED_MARKER_KEY, "completed"),
        )

        print("Catalog seed completed successfully.")
        print(f"Created products: {result.get('created', 0)}")
        print(f"Skipped existing products: {result.get('skipped', 0)}")
        print(f"Products with opening stock: {result.get('with_stock', 0)}")

    finally:
        try:
            if lock_acquired and cursor is not None:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (SEED_LOCK_NAME,))
                cursor.fetchone()
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()


def _seed_log_path() -> Path:
    app_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    return app_dir / "seed_print_catalog_once.log"


def _configure_seed_logging() -> None:
    """Write seed-mode diagnostics to a file, including for --windowed EXEs."""
    log_path = _seed_log_path()
    stream = log_path.open("w", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    print(f"MyShop catalog seed log: {log_path}")


def _show_startup_error(title: str, exc: BaseException) -> None:
    if SEED_MODE:
        print(f"{title}: {exc}", file=sys.stderr, flush=True)
    else:
        messagebox.showerror(title, str(exc))

def _copy_to_clipboard(text: str) -> str | None:
    """Return None on success, otherwise a readable error."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"

def main() -> None:
    if SEED_MODE:
        try:
            _configure_seed_logging()
        except OSError as exc:
            print(f"Could not create seed log file: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    # Both normal startup and seed-only mode need the schema initialized.
    try:
        db.initialize()
    except (DatabaseError, MigrationError, KeyStoreError, RuntimeError, OSError) as exc:
        _show_startup_error("Database error", exc)
        raise SystemExit(1) from exc

    if SEED_MODE:
        try:
            run_catalog_seed_once()
        except Exception as exc:
            print(f"Catalog seed failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        return

    try:
        register_fonts()
        first_password = ensure_first_admin()
    except (DatabaseError, MigrationError, KeyStoreError, RuntimeError, OSError) as exc:
        _show_startup_error("Startup error", exc)
        raise SystemExit(1) from exc

    if first_password:
        copy_error = _copy_to_clipboard(first_password)
        clip_note = (
            "تم نسخ كلمة المرور إلى الحافظة."
            if copy_error is None
            else f"تعذر النسخ إلى الحافظة:\n{copy_error}"
        )
        messagebox.showinfo(
            "First run",
            "تم إنشاء حساب المدير بنجاح.\n\n"
            "Username: admin\n"
            f"Password: {first_password}\n\n"
            "احتفظ بكلمة المرور؛ سيُطلب منك تغييرها عند أول تسجيل دخول.",
        )
    
    from UI.basewindow import BaseWindow
    from UI.router import go_login

    root = BaseWindow("Log In")
    go_login(root)
    root.mainloop()


if __name__ == "__main__":
    main()


#pyinstaller --noconfirm --clean --onefile --windowed --name program --distpath output --workpath build --add-data "Amiri-Regular.ttf;." --add-data "UI\assets;UI\assets" --collect-all keyring main.py