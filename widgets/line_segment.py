from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

from core.geometry import GeometricObject, Drawable

class LineSegment(GeometricObject, Drawable):
    """Класс для хранения информации об отрезке"""
    def __init__(self, start_point, end_point, style=None, color=None, width=None):
        """
        Инициализация отрезка
        Args:
            start_point: Начальная точка
            end_point: Конечная точка
            style: Стиль линии (LineStyle)
            color: Цвет (для обратной совместимости)
            width: Толщина (для обратной совместимости)
        """
        super().__init__()
        self.start_point = QPointF(start_point) if not isinstance(start_point, QPointF) else start_point
        self.end_point = QPointF(end_point) if not isinstance(end_point, QPointF) else end_point
        self._style = None
        self._style_name = None
        
        # Устанавливаем стиль через setter для правильной регистрации
        if style:
            self.style = style
        
        # Для обратной совместимости
        if color is not None:
            self._legacy_color = color
        else:
            self._legacy_color = QColor(255, 0, 0)
        
        if width is not None:
            self._legacy_width = width
        else:
            self._legacy_width = 2
    
    @property
    def style(self):
        return self._style
    
    @style.setter
    def style(self, value):
        if self._style:
            self._style.unregister_object(self)
        self._style = value
        self._style_name = value.name if value else None
        if value:
            value.register_object(self)
    
    @property
    def style_name(self):
        return self._style_name
    
    @property
    def color(self):
        """Возвращает цвет из стиля или legacy цвет"""
        if self._style:
            return self._style.color
        return self._legacy_color
    
    @color.setter
    def color(self, value):
        """Устанавливает цвет (обновляет стиль или legacy)"""
        if self._style:
            self._style.color = value
        else:
            self._legacy_color = value
    
    @property
    def width(self):
        """Возвращает ширину из стиля или legacy ширину"""
        if self._style:
            # Конвертируем мм в пиксели для обратной совместимости
            return (self._style.thickness_mm * 96) / 25.4
        return self._legacy_width
    
    @width.setter
    def width(self, value):
        """Устанавливает ширину (обновляет стиль или legacy)"""
        if self._style:
            # Конвертируем пиксели в мм
            thickness_mm = (value * 25.4) / 96
            self._style.thickness_mm = thickness_mm
        else:
            self._legacy_width = value
    
    def on_style_changed(self):
        """Вызывается при изменении стиля"""
        pass  # Может быть использовано для обновления отображения
    
    def get_bounding_box(self) -> QRectF:
        """Возвращает ограничивающий прямоугольник отрезка"""
        min_x = min(self.start_point.x(), self.end_point.x())
        max_x = max(self.start_point.x(), self.end_point.x())
        min_y = min(self.start_point.y(), self.end_point.y())
        max_y = max(self.start_point.y(), self.end_point.y())
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def contains_point(self, point: QPointF, tolerance: float = 5.0) -> bool:
        """Проверяет, содержит ли отрезок точку"""
        import math
        # Вычисляем расстояние от точки до отрезка
        distance = self._point_to_line_distance(point, self.start_point, self.end_point)
        return distance <= tolerance
    
    def _point_to_line_distance(self, point: QPointF, line_start: QPointF, line_end: QPointF) -> float:
        """Вычисляет расстояние от точки до отрезка"""
        import math
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()
        
        if dx == 0 and dy == 0:
            return math.sqrt((point.x() - line_start.x())**2 + (point.y() - line_start.y())**2)
        
        t = ((point.x() - line_start.x()) * dx + (point.y() - line_start.y()) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        
        closest_x = line_start.x() + t * dx
        closest_y = line_start.y() + t * dy
        
        return math.sqrt((point.x() - closest_x)**2 + (point.y() - closest_y)**2)
    
    def intersects_rect(self, rect: QRectF) -> bool:
        """Проверяет, пересекается ли отрезок с прямоугольником"""
        # Проверяем, находятся ли обе точки внутри прямоугольника
        if (rect.contains(self.start_point) and rect.contains(self.end_point)):
            return True
        
        # Проверяем пересечение с каждой стороной прямоугольника
        return (self._line_segment_intersection(
            self.start_point.x(), self.start_point.y(),
            self.end_point.x(), self.end_point.y(),
            rect.left(), rect.top(), rect.left(), rect.bottom()
        ) or self._line_segment_intersection(
            self.start_point.x(), self.start_point.y(),
            self.end_point.x(), self.end_point.y(),
            rect.right(), rect.top(), rect.right(), rect.bottom()
        ) or self._line_segment_intersection(
            self.start_point.x(), self.start_point.y(),
            self.end_point.x(), self.end_point.y(),
            rect.left(), rect.top(), rect.right(), rect.top()
        ) or self._line_segment_intersection(
            self.start_point.x(), self.start_point.y(),
            self.end_point.x(), self.end_point.y(),
            rect.left(), rect.bottom(), rect.right(), rect.bottom()
        ))
    
    def _line_segment_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4) -> bool:
        """Проверяет пересечение двух отрезков"""
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return False
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        return 0 <= t <= 1 and 0 <= u <= 1
    
    def draw(self, painter, scale_factor: float = 1.0):
        """Отрисовывает отрезок (реализация интерфейса Drawable)"""
        from core.renderer import LineRenderer
        LineRenderer.draw_line(painter, self, scale_factor, self.selected)