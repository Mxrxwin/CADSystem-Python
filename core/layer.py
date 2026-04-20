"""
Layer management system (ГОСТ-совместимые слои для DXF-экспорта).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor


@dataclass
class Layer:
    """Слой чертежа."""
    name: str
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    line_type: str = "Continuous"
    visible: bool = True
    locked: bool = False

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Layer) and self.name == other.name


class LayerManager(QObject):
    """Менеджер слоёв. Слой «0» всегда присутствует и не может быть удалён."""

    layer_added = Signal(object)    # Layer
    layer_removed = Signal(str)     # name
    layer_changed = Signal(object)  # Layer
    current_changed = Signal(str)   # name

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._layers: Dict[str, Layer] = {}
        self._current: str = "0"
        self._layers["0"] = Layer(name="0")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_layer(self, name: str) -> Optional[Layer]:
        return self._layers.get(name)

    def get_all_layers(self) -> List[Layer]:
        return list(self._layers.values())

    def get_layer_names(self) -> List[str]:
        return list(self._layers.keys())

    def get_current_layer(self) -> Layer:
        return self._layers.get(self._current, self._layers["0"])

    @property
    def current_layer_name(self) -> str:
        return self._current

    @current_layer_name.setter
    def current_layer_name(self, name: str) -> None:
        if name in self._layers and name != self._current:
            self._current = name
            self.current_changed.emit(name)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_layer(self, layer: Layer) -> bool:
        if layer.name in self._layers:
            return False
        self._layers[layer.name] = layer
        self.layer_added.emit(layer)
        return True

    def remove_layer(self, name: str) -> bool:
        if name == "0" or name not in self._layers:
            return False
        del self._layers[name]
        if self._current == name:
            self._current = "0"
            self.current_changed.emit("0")
        self.layer_removed.emit(name)
        return True

    def update_layer(self, name: str, **kwargs) -> None:
        layer = self._layers.get(name)
        if layer is None:
            return
        for key, value in kwargs.items():
            if hasattr(layer, key):
                setattr(layer, key, value)
        self.layer_changed.emit(layer)

    def new_layer(self, name: str, color: Optional[QColor] = None,
                  line_type: str = "Continuous") -> Optional[Layer]:
        """Создаёт и регистрирует новый слой; возвращает его или None если имя занято."""
        if name in self._layers:
            return None
        layer = Layer(
            name=name,
            color=color if color is not None else QColor(0, 0, 0),
            line_type=line_type,
        )
        self.add_layer(layer)
        return layer
