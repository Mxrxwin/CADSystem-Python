"""
Базовые классы для геометрических объектов
"""
from abc import ABC, abstractmethod
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor


class GeometricObject(ABC):
    """Базовый класс для всех геометрических объектов"""
    
    def __init__(self):
        self._selected = False
    
    @property
    def selected(self):
        """Возвращает состояние выделения объекта"""
        return self._selected
    
    @selected.setter
    def selected(self, value):
        """Устанавливает состояние выделения"""
        self._selected = value
    
    @abstractmethod
    def get_bounding_box(self) -> QRectF:
        """Возвращает ограничивающий прямоугольник объекта"""
        pass
    
    @abstractmethod
    def contains_point(self, point: QPointF, tolerance: float = 5.0) -> bool:
        """Проверяет, содержит ли объект точку"""
        pass
    
    @abstractmethod
    def intersects_rect(self, rect: QRectF) -> bool:
        """Проверяет, пересекается ли объект с прямоугольником"""
        pass


class Drawable(ABC):
    """Интерфейс для объектов, которые можно отрисовать"""
    
    @abstractmethod
    def draw(self, painter, scale_factor: float = 1.0):
        """Отрисовывает объект"""
        pass


class Point(GeometricObject):
    """Класс для представления точки"""
    
    def __init__(self, x: float = 0.0, y: float = 0.0, point: QPointF = None):
        super().__init__()
        if point is not None:
            self._point = QPointF(point)
        else:
            self._point = QPointF(x, y)
    
    @property
    def point(self) -> QPointF:
        """Возвращает точку"""
        return self._point
    
    @point.setter
    def point(self, value: QPointF):
        """Устанавливает точку"""
        self._point = QPointF(value)
    
    @property
    def x(self) -> float:
        return self._point.x()
    
    @x.setter
    def x(self, value: float):
        self._point.setX(value)
    
    @property
    def y(self) -> float:
        return self._point.y()
    
    @y.setter
    def y(self, value: float):
        self._point.setY(value)
    
    def get_bounding_box(self) -> QRectF:
        """Возвращает ограничивающий прямоугольник точки"""
        size = 1.0
        return QRectF(
            self._point.x() - size / 2,
            self._point.y() - size / 2,
            size,
            size
        )
    
    def contains_point(self, point: QPointF, tolerance: float = 5.0) -> bool:
        """Проверяет, содержит ли точка указанную точку"""
        dx = point.x() - self._point.x()
        dy = point.y() - self._point.y()
        distance = (dx * dx + dy * dy) ** 0.5
        return distance <= tolerance
    
    def intersects_rect(self, rect: QRectF) -> bool:
        """Проверяет, пересекается ли точка с прямоугольником"""
        return rect.contains(self._point)

