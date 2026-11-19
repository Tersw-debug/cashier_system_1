from __future__ import annotations

from typing import Any
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from PySide6.QtWidgets import (
    QWidget,
)

from UI.common import is_dark
from Services.cashier_service import (

    minor_to_money,
)


def _qty_text(value: Any) -> str:
    return f"{value.normalize():f}" if isinstance(value, Decimal) else str(value)


def _line_totals(product: tuple, quantity: Decimal) -> tuple[int, int, int]:
    """Return base, tax, and total using integer minor currency units."""
    price_minor = int(product[4])
    tax_bp = int(product[9] or 0)
    base = int((quantity * Decimal(price_minor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    tax = int((Decimal(base) * Decimal(tax_bp) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return base, tax, base + tax


class _CartTableModel(QAbstractTableModel):
    """Model for the sale cart; row identity is the product ID, not row number."""

    HEADERS = ("الصنف", "الباركود", "سعر الوحدة", "الكمية", "الإجمالي", "المتاح")

    def __init__(self, cart: dict[int, dict[str, Any]], parent: QWidget | None = None):
        super().__init__(parent)
        self._cart = cart
        self._product_ids: list[int] = list(cart)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._product_ids)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and orientation == Qt.Orientation.Horizontal:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._product_ids)):
            return None

        product_id = self._product_ids[index.row()]
        entry = self._cart.get(product_id)
        if entry is None:
            return None

        if role == Qt.ItemDataRole.UserRole:
            return product_id

        if role == Qt.ItemDataRole.TextAlignmentRole:
            alignment = (
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                if index.column() == 0 else
                Qt.AlignmentFlag.AlignCenter
            )
            return int(alignment)

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        product = entry["product"]
        quantity = entry["quantity"]
        _base, _tax, line_total = _line_totals(product, quantity)
        stock_text = f"{float(product[5]):g}" if bool(product[7]) else "—"
        values = (
            str(product[1]),
            str(product[3] or ""),
            minor_to_money(product[4]),
            _qty_text(quantity),
            minor_to_money(line_total),
            stock_text,
        )
        return values[index.column()]

    def refresh(self) -> None:
        self.beginResetModel()
        self._product_ids = list(self._cart)
        self.endResetModel()

    def product_id_at(self, row: int) -> int | None:
        if 0 <= row < len(self._product_ids):
            return self._product_ids[row]
        return None

    def row_for_product(self, product_id: int) -> int:
        try:
            return self._product_ids.index(int(product_id))
        except ValueError:
            return -1