from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from PySide6.QtWidgets import (
    QWidget,
)


from Services.cashier_service import (

    minor_to_money,
)

class _DebtTableModel(QAbstractTableModel):
    """Source model for debtors; the proxy model handles interactive filtering."""

    HEADERS = ("الرقم", "العميل", "الهاتف", "الدين الحالي")

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._records: list[tuple[int, str, str, int]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

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
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None

        record = self._records[index.row()]
        customer_id, name, phone, debt_minor = record

        if role == Qt.ItemDataRole.UserRole:
            return customer_id
        if role == Qt.ItemDataRole.UserRole + 1:
            # Numeric sort values, should sorting be enabled by the UI later.
            return (customer_id, name.casefold(), phone.casefold(), debt_minor)[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        return (
            str(customer_id),
            name,
            phone,
            minor_to_money(debt_minor),
        )[index.column()]

    def set_records(self, records: list[tuple[int, str, str, int]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def record_at(self, row: int) -> tuple[int, str, int] | None:
        if not (0 <= row < len(self._records)):
            return None
        customer_id, name, _phone, debt_minor = self._records[row]
        return customer_id, name, debt_minor