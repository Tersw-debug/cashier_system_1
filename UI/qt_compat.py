"""Small PySide6 compatibility layer for the former Tk/CustomTkinter UI modules.

All rendered controls are native Qt widgets.  The pack/grid helpers exist only
so the large ERP pages can be migrated without rewriting their business logic
and every layout call in one risky pass.  New screens should use Qt layouts
(QVBoxLayout/QHBoxLayout/QGridLayout) directly.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QHeaderView,
    QSizePolicy,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Geometry constants retained as strings for the small number of old call sites.
BOTH, CENTER, END, LEFT, RIGHT, X, Y = "both", "center", "end", "left", "right", "x", "y"


class Variable:
    """Tiny observable variable used to bind old form state to Qt controls."""
    def __init__(self, value: Any = ""):
        self._value = value
        self._bindings: list[Callable[[Any], None]] = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for callback in tuple(self._bindings):
            callback(value)

    def _set_from_widget(self, value):
        self._value = value

    def _bind(self, callback):
        self._bindings.append(callback)
        callback(self._value)


class StringVar(Variable):
    def __init__(self, value: str = ""):
        super().__init__(value)


class BooleanVar(Variable):
    def __init__(self, value: bool = False):
        super().__init__(bool(value))


def _qparent(master):
    """Scrollable-frame children belong to its internal content widget."""
    if isinstance(master, QtScrollableFrame):
        return master._content
    return master


def _margins(value):
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            return int(value[0]), int(value[1]), int(value[0]), int(value[1])
        if len(value) == 4:
            return tuple(map(int, value))
    if value is None:
        return 0, 0, 0, 0
    n = int(value)
    return n, n, n, n


def _alignment(value):
    value = str(value or "").lower()
    if value in {"e", "right"}:
        return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    if value in {"w", "left"}:
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    if value in {"n", "top"}:
        return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
    if value in {"s", "bottom"}:
        return Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter
    if value in {"center", "c"}:
        return Qt.AlignmentFlag.AlignCenter
    return Qt.Alignment()


def _font(value):
    if isinstance(value, QFont):
        return value
    if not value:
        return None
    try:
        family, size, *style = value
        result = QFont(str(family), int(size))
        if style:
            result.setBold("bold" in [str(x).lower() for x in style])
        return result
    except Exception:
        return None


class _LayoutMixin:
    """Former pack/grid surface backed by Qt box and grid layouts."""
    def _layout_host(self):
        return self

    def _ensure_layout(self, kind: str, side: str = "top"):
        host = self._layout_host()
        layout = host.layout()
        if layout is None:
            if kind == "grid":
                layout = QGridLayout()
            else:
                horizontal = side in {"left", "right"}
                layout = QHBoxLayout() if horizontal else QVBoxLayout()
                if horizontal:
                    layout.setDirection(QBoxDirection.RightToLeft if side == "right" else QBoxDirection.LeftToRight)
                else:
                    layout.setDirection(QBoxDirection.BottomToTop if side == "bottom" else QBoxDirection.TopToBottom)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            host.setLayout(layout)
        elif kind == "grid" and not isinstance(layout, QGridLayout):
            raise RuntimeError("Cannot mix grid() with pack() in the same Qt container")
        elif kind == "box" and isinstance(layout, QGridLayout):
            raise RuntimeError("Cannot mix pack() with grid() in the same Qt container")
        return layout

    def pack(self, **kwargs):
        side = str(kwargs.get("side", "top")).lower()
        layout = self._ensure_layout("box", side)
        widget = self
        # A widget can be removed and packed again (pack_forget/show patterns).
        index = layout.indexOf(widget)
        if index >= 0:
            layout.removeWidget(widget)
        before = kwargs.get("before")
        # Horizontal Tk pack() uses side=LEFT/RIGHT to reserve opposite edges;
        # preserving call order in Qt gives the intended left-center-right panels.
        # The one vertical before= case is used to reveal an optional form before
        # the payment controls, so preserve it there.
        horizontal = isinstance(layout, QHBoxLayout)
        insert_at = layout.indexOf(before) if (before is not None and not horizontal) else -1
        if insert_at < 0:
            insert_at = layout.count()
        fill = str(kwargs.get("fill", "")).lower()
        expand = bool(kwargs.get("expand", False))
        if fill in {"x", "both"} or expand:
            policy = QSizePolicy.Policy.Expanding
            widget.setSizePolicy(policy, policy if fill == "both" else QSizePolicy.Policy.Preferred)
        elif fill == "y":
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        anchor = kwargs.get("anchor")
        alignment = _alignment(anchor) if anchor else Qt.Alignment()
        stretch = 1 if expand else 0
        horizontal = isinstance(layout, QHBoxLayout)
        raw_padding = kwargs.get("padx" if horizontal else "pady", 0)
        if isinstance(raw_padding, (tuple, list)):
            pad = sum(int(value) for value in raw_padding)
        else:
            pad = 2 * int(raw_padding or 0)
        if pad:
            layout.insertSpacing(insert_at, pad)
            insert_at += 1
        layout.insertWidget(insert_at, widget, stretch, alignment)
        if pad:
            layout.insertSpacing(insert_at + 1, pad)
        widget.show()
        return None

    def pack_forget(self):
        layout = self.parentWidget().layout() if self.parentWidget() else None
        if layout:
            layout.removeWidget(self)
        self.hide()

    def pack_propagate(self, _flag=True):
        # Qt sizes are governed by size policies/minimum sizes, not propagation.
        return None

    def grid(self, **kwargs):
        layout = self._ensure_layout("grid")
        row = int(kwargs.get("row", 0))
        column = int(kwargs.get("column", 0))
        rowspan = int(kwargs.get("rowspan", 1))
        colspan = int(kwargs.get("columnspan", 1))
        sticky = str(kwargs.get("sticky", "")).lower()
        alignment = Qt.Alignment()
        if sticky in {"ew", "nsew", "ns", "we"}:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            alignment = _alignment(sticky)
        layout.addWidget(self, row, column, rowspan, colspan, alignment)
        self.show()

    def grid_columnconfigure(self, column, weight=0, **_kwargs):
        layout = self._ensure_layout("grid")
        layout.setColumnStretch(int(column), int(weight))

    def grid_rowconfigure(self, row, weight=0, **_kwargs):
        layout = self._ensure_layout("grid")
        layout.setRowStretch(int(row), int(weight))

    # tkinter naming compatibility for the two existing table-holder calls.
    rowconfigure = grid_rowconfigure
    columnconfigure = grid_columnconfigure

    def grid_propagate(self, _flag=True):
        return None

    def place(self, **kwargs):
        # Kept for legacy one-off placement. Prefer a Qt layout in new screens.
        parent = self.parentWidget()
        if parent is None:
            return
        if parent.layout() is None:
            layout = QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            parent.setLayout(layout)
        parent.layout().addWidget(self, 0, Qt.AlignmentFlag.AlignCenter)

    def winfo_children(self):
        return [child for child in self._layout_host().findChildren(QWidget, Qt.FindChildOption.FindDirectChildrenOnly)]

    def winfo_toplevel(self):
        return self.window()

    def winfo_exists(self):
        return not getattr(self, "_compat_destroyed", False)

    def destroy(self):
        self._compat_destroyed = True
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().removeWidget(self)
        self.setParent(None)
        self.deleteLater()

    def after(self, milliseconds, callback):
        QTimer.singleShot(int(milliseconds), callback)

    def focus_set(self):
        self.setFocus()

    def focus_force(self):
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def bind(self, sequence, callback):
        """Bind the handful of former Tk event names used by these ERP pages."""
        seq = str(sequence).lower()
        if isinstance(self, QLineEdit):
            if seq == "<return>":
                self.returnPressed.connect(lambda: callback(None))
            elif seq == "<keyrelease>":
                self.textChanged.connect(lambda _text: callback(None))
        elif isinstance(self, QComboBox):
            if seq == "<return>":
                self.activated.connect(lambda _index: callback(None))
        elif isinstance(self, QtTreeWidget):
            if seq in {"<double-1>", "<doubleclick>"}:
                self.itemDoubleClicked.connect(lambda *_args: callback(None))
            elif seq == "<delete>":
                self._delete_callback = callback
        elif isinstance(self, QDialog):
            key = {"<escape>": "Escape", "<return>": "Return"}.get(seq)
            if key:
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(lambda: callback(None))
                self._compat_shortcuts = getattr(self, "_compat_shortcuts", []) + [shortcut]
        return None


# QBoxLayout direction is accessed via this small alias to keep type hints clear.
from PySide6.QtWidgets import QBoxLayout as _QBoxLayout
QBoxDirection = _QBoxLayout.Direction


class QtFrame(QWidget, _LayoutMixin):
    def __init__(self, master=None, **kwargs):
        super().__init__(_qparent(master))
        self._apply_frame_options(kwargs)

    def _apply_frame_options(self, kwargs):
        color = kwargs.get("fg_color", kwargs.get("bg", kwargs.get("bg_color")))
        border_color = kwargs.get("border_color")
        border_width = int(kwargs.get("border_width", 0) or 0)
        radius = int(kwargs.get("corner_radius", 0) or 0)
        if color and color != "transparent":
            self.setStyleSheet(f"background-color: {color}; border: {border_width}px solid {border_color or color}; border-radius: {radius}px;")
        elif border_width and border_color:
            self.setStyleSheet(f"background: transparent; border: {border_width}px solid {border_color}; border-radius: {radius}px;")
        else:
            self.setStyleSheet("background: transparent; border: none;")
        if kwargs.get("width"):
            self.setMinimumWidth(int(kwargs["width"]))
        if kwargs.get("height"):
            self.setMinimumHeight(int(kwargs["height"]))

    def configure(self, **kwargs):
        self._apply_frame_options(kwargs)

    config = configure


class QtLabel(QLabel, _LayoutMixin):
    def __init__(self, master=None, text="", **kwargs):
        super().__init__(str(text), _qparent(master))
        self._wraplength = kwargs.get("wraplength")
        self.setWordWrap(bool(self._wraplength))
        self.setAlignment(_alignment(kwargs.get("anchor")) or Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if kwargs.get("justify") == "right":
            self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        f = _font(kwargs.get("font"))
        if f:
            self.setFont(f)
        if kwargs.get("width"):
            self.setMinimumWidth(int(kwargs["width"]))
        if kwargs.get("height"):
            self.setMinimumHeight(int(kwargs["height"]))
        self.configure(**kwargs)

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.setText(str(kwargs["text"]))
        if "font" in kwargs and (f := _font(kwargs["font"])):
            self.setFont(f)
        if "text_color" in kwargs:
            self.setStyleSheet(f"color: {kwargs['text_color']}; background: transparent;")
        if "fg_color" in kwargs and kwargs["fg_color"] != "transparent":
            self.setStyleSheet(f"color: {kwargs.get('text_color', 'palette(window-text)')}; background: {kwargs['fg_color']};")
        if "anchor" in kwargs:
            self.setAlignment(_alignment(kwargs["anchor"]))
        if "wraplength" in kwargs:
            self.setWordWrap(True)

    config = configure


class QtButton(QPushButton, _LayoutMixin):
    def __init__(self, master=None, text="", command=None, **kwargs):
        super().__init__(str(text), _qparent(master))
        self._command = command
        self.clicked.connect(self._invoke)
        self.configure(**kwargs)
        f = _font(kwargs.get("font"))
        if f:
            self.setFont(f)

    def _invoke(self, *_args):
        if callable(self._command):
            self._command()

    def invoke(self):
        self.click()

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.setText(str(kwargs["text"]))
        if "command" in kwargs:
            self._command = kwargs["command"]
        if "state" in kwargs:
            self.setEnabled(str(kwargs["state"]).lower() not in {"disabled", "disable"})
        if "width" in kwargs:
            self.setMinimumWidth(int(kwargs["width"]))
        if "height" in kwargs:
            self.setMinimumHeight(int(kwargs["height"]))
        if "font" in kwargs and (f := _font(kwargs["font"])):
            self.setFont(f)
        bg = kwargs.get("fg_color")
        hover = kwargs.get("hover_color", bg)
        fg = kwargs.get("text_color", "#ffffff")
        radius = int(kwargs.get("corner_radius", 6) or 0)
        if bg:
            self.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: {fg}; border: none; border-radius: {radius}px; padding: 6px 10px; }}"
                f"QPushButton:hover {{ background: {hover}; }} QPushButton:disabled {{ opacity: 0.5; }}"
            )
        if "anchor" in kwargs:
            anchor = {"e": "right", "w": "left", "center": "center"}.get(str(kwargs["anchor"]), str(kwargs["anchor"]))
            self.setStyleSheet(self.styleSheet() + f" QPushButton {{ text-align: {anchor}; }}")

    config = configure


class QtLineEdit(QLineEdit, _LayoutMixin):
    def __init__(self, master=None, textvariable=None, placeholder_text="", **kwargs):
        super().__init__(_qparent(master))
        if placeholder_text:
            self.setPlaceholderText(str(placeholder_text))
        if kwargs.get("justify"):
            self.setAlignment(_alignment(kwargs["justify"]))
        if kwargs.get("show"):
            self.setEchoMode(QLineEdit.EchoMode.Password)
        if kwargs.get("height"):
            self.setMinimumHeight(int(kwargs["height"]))
        if kwargs.get("width"):
            self.setMinimumWidth(int(kwargs["width"]))
        if textvariable is not None:
            textvariable._bind(self.setText)
            self.textChanged.connect(textvariable._set_from_widget)
        self.configure(**kwargs)

    def get(self):
        return self.text()

    def insert(self, index, text):
        if index in ("end", END):
            self.setText(self.text() + str(text))
        else:
            try:
                pos = int(index)
            except (TypeError, ValueError):
                pos = self.cursorPosition()
            self.setCursorPosition(max(0, min(pos, len(self.text()))))
            QLineEdit.insert(self, str(text))

    def delete(self, first=0, last=None):
        if last in ("end", END) or first in ("1.0", "0"):
            self.clear()
        else:
            try:
                start = int(first)
                end = int(last) if last is not None else start + 1
                self.setText(self.text()[:start] + self.text()[end:])
            except (TypeError, ValueError):
                self.clear()

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.setReadOnly(str(kwargs["state"]).lower() in {"disabled", "readonly"})
            self.setEnabled(str(kwargs["state"]).lower() != "disabled")
        if "show" in kwargs:
            self.setEchoMode(QLineEdit.EchoMode.Password if kwargs["show"] else QLineEdit.EchoMode.Normal)
        if "placeholder_text" in kwargs:
            self.setPlaceholderText(str(kwargs["placeholder_text"]))
        if "height" in kwargs:
            self.setMinimumHeight(int(kwargs["height"]))

    config = configure


class QtComboBox(QComboBox, _LayoutMixin):
    def __init__(self, master=None, values=None, variable=None, state="normal", command=None, **kwargs):
        super().__init__(_qparent(master))
        self._command = command
        self.currentTextChanged.connect(self._run_command)
        if values:
            self.addItems([str(x) for x in values])
        if variable is not None:
            variable._bind(self.setCurrentText)
            self.currentTextChanged.connect(variable._set_from_widget)
        if state == "readonly":
            self.setEditable(False)
        self.configure(**kwargs)
        if kwargs.get("width"):
            self.setMinimumWidth(int(kwargs["width"]))
        if kwargs.get("height"):
            self.setMinimumHeight(int(kwargs["height"]))

    def _run_command(self, value):
        if callable(self._command):
            self._command(value)

    def get(self):
        return self.currentText()

    def set(self, value):
        self.setCurrentText(str(value))

    def configure(self, **kwargs):
        if "values" in kwargs:
            current = self.currentText()
            self.clear()
            self.addItems([str(x) for x in (kwargs["values"] or [])])
            if current:
                self.setCurrentText(current)
        if "state" in kwargs:
            self.setEnabled(str(kwargs["state"]).lower() != "disabled")
            self.setEditable(str(kwargs["state"]).lower() not in {"readonly", "disabled"})
        if "command" in kwargs:
            self._command = kwargs["command"]
        if "height" in kwargs:
            self.setMinimumHeight(int(kwargs["height"]))

    config = configure


class QtCheckBox(QCheckBox, _LayoutMixin):
    def __init__(self, master=None, text="", variable=None, command=None, **kwargs):
        super().__init__(str(text), _qparent(master))
        self._command = command
        self.toggled.connect(self._on_change)
        if variable is not None:
            variable._bind(self.setChecked)
            self.toggled.connect(variable._set_from_widget)
        self.configure(**kwargs)

    def _on_change(self, *_args):
        if callable(self._command):
            self._command()

    def get(self):
        return self.isChecked()

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.setText(str(kwargs["text"]))
        if "command" in kwargs:
            self._command = kwargs["command"]
        if "state" in kwargs:
            self.setEnabled(str(kwargs["state"]).lower() != "disabled")

    config = configure


class QtScrollableFrame(QScrollArea, _LayoutMixin):
    def __init__(self, master=None, **kwargs):
        super().__init__(_qparent(master))
        self._content = QWidget()
        self._content.setObjectName("scrollContent")
        self.setWidget(self._content)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.configure(**kwargs)
        if kwargs.get("width"):
            self.setMinimumWidth(int(kwargs["width"]))
        if kwargs.get("height"):
            self.setMinimumHeight(int(kwargs["height"]))

    def _layout_host(self):
        return self._content

    def configure(self, **kwargs):
        color = kwargs.get("fg_color")
        if color and color != "transparent":
            self._content.setStyleSheet(f"background-color: {color};")
            self.setStyleSheet(f"QScrollArea {{ background: {color}; border: none; }}")

    config = configure


class QtTextEdit(QTextEdit, _LayoutMixin):
    def __init__(self, master=None, **kwargs):
        super().__init__(_qparent(master))
        if kwargs.get("wrap") == "word":
            self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        f = _font(kwargs.get("font"))
        if f:
            self.setFont(f)

    def insert(self, index, text):
        if index in {"1.0", "0"}:
            self.setPlainText(str(text))
        else:
            self.insertPlainText(str(text))

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.setReadOnly(str(kwargs["state"]).lower() == "disabled")

    config = configure


class QtDialog(QDialog, _LayoutMixin):
    def __init__(self, master=None, **kwargs):
        super().__init__(_qparent(master))
        self.setWindowFlag(Qt.WindowType.Dialog, True)
        self._compat_destroyed = False
        # Tk Toplevels were visible immediately after construction.
        self.show()

    def geometry(self, value):
        try:
            w, h = str(value).split("x", 1)
            self.resize(int(w), int(h))
        except Exception:
            pass

    def minsize(self, width, height):
        self.setMinimumSize(int(width), int(height))

    def resizable(self, width, height):
        if not width and not height:
            self.setFixedSize(self.size())
        elif not width:
            self.setMinimumWidth(self.width()); self.setMaximumWidth(self.width())
        elif not height:
            self.setMinimumHeight(self.height()); self.setMaximumHeight(self.height())

    def transient(self, parent):
        self.setParent(parent, Qt.WindowType.Dialog)
        self.show()

    def grab_set(self):
        self.setModal(True)
        self.show()
        self.raise_()
        self.activateWindow()

    def grab_release(self):
        self.setModal(False)

    def configure(self, **kwargs):
        color = kwargs.get("fg_color", kwargs.get("bg"))
        if color:
            self.setStyleSheet(f"QDialog {{ background-color: {color}; }}")

    config = configure

    def destroy(self):
        self._compat_destroyed = True
        self.close()
        self.deleteLater()

    def closeEvent(self, event):
        self._compat_destroyed = True
        super().closeEvent(event)


class QtTreeWidget(QTreeWidget, _LayoutMixin):
    def __init__(self, master=None, columns=(), displaycolumns=None, show="headings", selectmode="browse", **kwargs):
        super().__init__(_qparent(master))
        self._column_names = list(columns)
        self._column_index = {name: i for i, name in enumerate(self._column_names)}
        self._id_to_item: dict[str, QTreeWidgetItem] = {}
        self._delete_callback = None
        self.setColumnCount(len(self._column_names))
        self.setHeaderLabels([str(x) for x in self._column_names])
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setUniformRowHeights(True)
        self.header().setStretchLastSection(False)
        if displaycolumns:
            for visual, name in enumerate(displaycolumns):
                if name in self._column_index:
                    self.header().moveSection(self.header().visualIndex(self._column_index[name]), visual)

    def heading(self, column, text="", **_kwargs):
        idx = self._column_index.get(column, int(column) if str(column).isdigit() else None)
        if idx is not None:
            self.headerItem().setText(idx, str(text))

    def column(self, column, width=None, anchor="center", stretch=True, **_kwargs):
        idx = self._column_index.get(column, int(column) if str(column).isdigit() else None)
        if idx is None:
            return
        if width:
            self.setColumnWidth(idx, int(width))
        mode = QHeaderView.ResizeMode.Stretch if stretch else QHeaderView.ResizeMode.Interactive
        self.header().setSectionResizeMode(idx, mode)
        alignment = _alignment(anchor)
        # Store alignment for newly-created cells.
        self._column_alignments = getattr(self, "_column_alignments", {})
        self._column_alignments[idx] = alignment

    def insert(self, parent, index, iid=None, values=(), **_kwargs):
        item = QTreeWidgetItem([str(v) for v in values])
        key = str(iid if iid is not None else id(item))
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        if parent in ("", None):
            self.addTopLevelItem(item)
        else:
            p = self._id_to_item.get(str(parent))
            (p or self.invisibleRootItem()).addChild(item)
        self._id_to_item[key] = item
        for col, alignment in getattr(self, "_column_alignments", {}).items():
            if alignment:
                item.setTextAlignment(col, alignment)
        return key

    def get_children(self, item=""):
        if item in ("", None):
            return [str(self.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)) for i in range(self.topLevelItemCount())]
        node = self._id_to_item.get(str(item))
        if node is None:
            return []
        return [str(node.child(i).data(0, Qt.ItemDataRole.UserRole)) for i in range(node.childCount())]

    def delete(self, *items):
        for key in items:
            item = self._id_to_item.pop(str(key), None)
            if item is None:
                continue
            parent = item.parent()
            if parent is None:
                index = self.indexOfTopLevelItem(item)
                if index >= 0:
                    self.takeTopLevelItem(index)
            else:
                parent.removeChild(item)

    def selection(self):
        return [str(item.data(0, Qt.ItemDataRole.UserRole)) for item in self.selectedItems()]

    def selection_set(self, iid):
        item = self._id_to_item.get(str(iid))
        if item is not None:
            self.setCurrentItem(item)

    def focus(self, iid=None):
        if iid is None:
            current = self.currentItem()
            return str(current.data(0, Qt.ItemDataRole.UserRole)) if current else ""
        item = self._id_to_item.get(str(iid))
        if item is not None:
            self.setCurrentItem(item)

    def item(self, iid):
        item = self._id_to_item.get(str(iid))
        if item is None:
            return {"values": []}
        return {"values": [item.text(i) for i in range(self.columnCount())]}

    def xview_moveto(self, fraction):
        bar = self.horizontalScrollBar()
        bar.setValue(int(float(fraction) * bar.maximum()))

    def xview(self, *args):
        return self._scroll_view(self.horizontalScrollBar(), *args)

    def yview(self, *args):
        return self._scroll_view(self.verticalScrollBar(), *args)

    @staticmethod
    def _scroll_view(bar, *args):
        if not args:
            maximum = max(1, bar.maximum())
            return bar.value() / maximum, min(1.0, (bar.value() + bar.pageStep()) / maximum)
        if args[0] == "moveto" and len(args) > 1:
            bar.setValue(int(float(args[1]) * bar.maximum()))
        elif args[0] == "scroll" and len(args) > 2:
            delta = int(args[1]) * (bar.singleStep() if args[2] == "units" else bar.pageStep())
            bar.setValue(bar.value() + delta)

    def configure(self, **kwargs):
        ycmd = kwargs.get("yscrollcommand")
        xcmd = kwargs.get("xscrollcommand")
        if ycmd:
            self.verticalScrollBar().valueChanged.connect(lambda _v: ycmd(*self.yview()))
        if xcmd:
            self.horizontalScrollBar().valueChanged.connect(lambda _v: xcmd(*self.xview()))

    config = configure

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self._delete_callback:
            self._delete_callback(None)
            event.accept()
            return
        super().keyPressEvent(event)


class QtScrollBar(QScrollBar, _LayoutMixin):
    def __init__(self, master=None, orient="vertical", command=None, **kwargs):
        orientation = Qt.Orientation.Vertical if orient == "vertical" else Qt.Orientation.Horizontal
        super().__init__(orientation, _qparent(master))
        self._command = command
        self.valueChanged.connect(self._send_command)

    def _send_command(self, value):
        if self._command:
            self._command("moveto", str(value / max(1, self.maximum())))

    def set(self, first, last):
        self.setRange(0, 10000)
        self.setValue(int(float(first) * 10000))
        self.setPageStep(max(1, int((float(last) - float(first)) * 10000)))


class QtStyle:
    def theme_use(self, *_args, **_kwargs):
        return None

    def configure(self, *_args, **_kwargs):
        return None

    def map(self, *_args, **_kwargs):
        return None


class _MessageBox:
    @staticmethod
    def showinfo(title, message, parent=None):
        return QMessageBox.information(parent, str(title), str(message))

    @staticmethod
    def showerror(title, message, parent=None):
        return QMessageBox.critical(parent, str(title), str(message))

    @staticmethod
    def showwarning(title, message, parent=None):
        return QMessageBox.warning(parent, str(title), str(message))

    @staticmethod
    def askyesno(title, message, parent=None):
        return QMessageBox.question(
            parent, str(title), str(message),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes


class _ColorChooser:
    @staticmethod
    def askcolor(color=None, parent=None, title="Choose color"):
        initial = QColor(color) if color else QColor()
        chosen = QColorDialog.getColor(initial, parent, title)
        if not chosen.isValid():
            return None, None
        return (chosen.red(), chosen.green(), chosen.blue()), chosen.name().upper()


TclError = RuntimeError
messagebox = _MessageBox()
colorchooser = _ColorChooser()
