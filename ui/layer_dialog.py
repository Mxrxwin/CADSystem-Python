"""
Диалог управления слоями чертежа.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QColorDialog, QComboBox, QCheckBox, QWidget,
)

from core.layer import Layer, LayerManager


_LINETYPES = [
    "Continuous",
    "CAD_DASHED",
    "CAD_CENTER",
    "CAD_DASHDOT",
    "CAD_PHANTOM",
]

_LINETYPE_LABELS = {
    "Continuous":  "Сплошная",
    "CAD_DASHED":  "Штриховая",
    "CAD_CENTER":  "Штрих-пунктирная (утолщённая)",
    "CAD_DASHDOT": "Штрих-пунктирная (тонкая)",
    "CAD_PHANTOM": "Штрих-пунктирная (2 точки)",
}


def _color_icon(color: QColor, size: int = 20) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(color)
    return QIcon(pm)


class LayerDialog(QDialog):
    """Диалог создания и редактирования слоёв."""

    COL_CURRENT = 0
    COL_NAME    = 1
    COL_COLOR   = 2
    COL_LINETYPE = 3
    COL_VISIBLE = 4
    COL_LOCKED  = 5

    def __init__(self, layer_manager: LayerManager, parent=None) -> None:
        super().__init__(parent)
        self._lm = layer_manager
        self.setWindowTitle("Менеджер слоёв")
        self.setMinimumSize(720, 400)
        self._build_ui()
        self._populate()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Таблица
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "●", "Имя", "Цвет", "Тип линии", "Видим.", "Заблок."
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_CURRENT,  QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NAME,     QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_COLOR,    QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_LINETYPE, QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_VISIBLE,  QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_LOCKED,   QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # Кнопки управления слоями
        btn_row = QHBoxLayout()
        self._btn_add    = QPushButton("Добавить")
        self._btn_remove = QPushButton("Удалить")
        self._btn_rename = QPushButton("Переименовать")
        self._btn_color  = QPushButton("Цвет…")
        self._btn_set    = QPushButton("Сделать текущим")
        for b in (self._btn_add, self._btn_remove, self._btn_rename,
                  self._btn_color, self._btn_set):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._add_layer)
        self._btn_remove.clicked.connect(self._remove_layer)
        self._btn_rename.clicked.connect(self._rename_layer)
        self._btn_color.clicked.connect(self._pick_color)
        self._btn_set.clicked.connect(self._set_current)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        self._table.setRowCount(0)
        current = self._lm.current_layer_name
        for layer in self._lm.get_all_layers():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._set_row(row, layer, is_current=(layer.name == current))

    def _set_row(self, row: int, layer: Layer, is_current: bool) -> None:
        # Текущий слой
        cur_item = QTableWidgetItem("●" if is_current else "")
        cur_item.setTextAlignment(Qt.AlignCenter)
        cur_item.setData(Qt.UserRole, layer.name)
        self._table.setItem(row, self.COL_CURRENT, cur_item)

        # Имя
        name_item = QTableWidgetItem(layer.name)
        if layer.name == "0":
            f = name_item.font()
            f.setBold(True)
            name_item.setFont(f)
        self._table.setItem(row, self.COL_NAME, name_item)

        # Цвет
        pm = QPixmap(24, 16)
        pm.fill(layer.color)
        color_item = QTableWidgetItem()
        color_item.setIcon(QIcon(pm))
        color_item.setText(layer.color.name().upper())
        self._table.setItem(row, self.COL_COLOR, color_item)

        # Тип линии
        lt_label = _LINETYPE_LABELS.get(layer.line_type, layer.line_type)
        lt_combo = QComboBox()
        for lt in _LINETYPES:
            lt_combo.addItem(_LINETYPE_LABELS.get(lt, lt), lt)
        idx = _LINETYPES.index(layer.line_type) if layer.line_type in _LINETYPES else 0
        lt_combo.setCurrentIndex(idx)
        lt_combo.currentIndexChanged.connect(
            lambda i, n=layer.name, cb=lt_combo: self._on_linetype_changed(n, cb)
        )
        self._table.setCellWidget(row, self.COL_LINETYPE, lt_combo)

        # Видимость
        vis_cb = QCheckBox()
        vis_cb.setChecked(layer.visible)
        vis_cb.toggled.connect(
            lambda checked, n=layer.name: self._lm.update_layer(n, visible=checked)
        )
        self._center_widget(row, self.COL_VISIBLE, vis_cb)

        # Блокировка
        lock_cb = QCheckBox()
        lock_cb.setChecked(layer.locked)
        lock_cb.toggled.connect(
            lambda checked, n=layer.name: self._lm.update_layer(n, locked=checked)
        )
        self._center_widget(row, self.COL_LOCKED, lock_cb)

    def _center_widget(self, row: int, col: int, widget) -> None:
        container = QWidget()
        hl = QHBoxLayout(container)
        hl.addStretch()
        hl.addWidget(widget)
        hl.addStretch()
        hl.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, col, container)

    def _selected_layer_name(self) -> Optional[str]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, self.COL_CURRENT)
        return item.data(Qt.UserRole) if item else None

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------

    def _on_double_click(self, index) -> None:
        if index.column() == self.COL_COLOR:
            self._pick_color()

    def _on_linetype_changed(self, name: str, combo: QComboBox) -> None:
        lt = combo.currentData()
        self._lm.update_layer(name, line_type=lt)

    def _add_layer(self) -> None:
        text, ok = QInputDialog.getText(self, "Новый слой", "Имя слоя:")
        if not ok or not text.strip():
            return
        name = text.strip()
        if not self._lm.new_layer(name):
            QMessageBox.warning(self, "Ошибка", f"Слой «{name}» уже существует.")
            return
        self._populate()

    def _remove_layer(self) -> None:
        name = self._selected_layer_name()
        if name is None:
            return
        if name == "0":
            QMessageBox.information(self, "Нельзя", "Слой «0» нельзя удалить.")
            return
        if not self._lm.remove_layer(name):
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить слой «{name}».")
            return
        self._populate()

    def _rename_layer(self) -> None:
        name = self._selected_layer_name()
        if name is None:
            return
        if name == "0":
            QMessageBox.information(self, "Нельзя", "Слой «0» нельзя переименовать.")
            return
        new_name, ok = QInputDialog.getText(
            self, "Переименовать слой", "Новое имя:", text=name
        )
        if not ok or not new_name.strip() or new_name.strip() == name:
            return
        new_name = new_name.strip()
        if self._lm.get_layer(new_name):
            QMessageBox.warning(self, "Ошибка", f"Слой «{new_name}» уже существует.")
            return
        # Переименование через remove + add с сохранением свойств
        old = self._lm.get_layer(name)
        was_current = (self._lm.current_layer_name == name)
        new_layer = Layer(
            name=new_name,
            color=QColor(old.color),
            line_type=old.line_type,
            visible=old.visible,
            locked=old.locked,
        )
        self._lm.remove_layer(name)
        self._lm.add_layer(new_layer)
        if was_current:
            self._lm.current_layer_name = new_name
        self._populate()

    def _pick_color(self) -> None:
        name = self._selected_layer_name()
        if name is None:
            return
        layer = self._lm.get_layer(name)
        if layer is None:
            return
        color = QColorDialog.getColor(layer.color, self, "Выберите цвет слоя")
        if color.isValid():
            self._lm.update_layer(name, color=color)
            self._populate()

    def _set_current(self) -> None:
        name = self._selected_layer_name()
        if name:
            self._lm.current_layer_name = name
            self._populate()
