"""
Класс для управления выделением объектов
"""
from typing import Set, List, Optional
from PySide6.QtCore import QPointF, QRectF, Signal, QObject

from core.geometry import GeometricObject
from widgets.line_segment import LineSegment


class SelectionManager(QObject):
    """Управляет выделением объектов на сцене"""
    
    selection_changed = Signal(list)  # Сигнал при изменении выделения
    
    def __init__(self):
        super().__init__()
        self._selected_objects: Set[GeometricObject] = set()
        self._selection_mode = True
    
    def select_object(self, obj: GeometricObject, add_to_selection: bool = False):
        """Выделяет объект"""
        if not add_to_selection:
            # Если не добавляем к выделению, очищаем текущее выделение
            self.clear_selection()
        
        # Добавляем объект к выделению (если его там еще нет)
        if obj not in self._selected_objects:
            self._selected_objects.add(obj)
            self._notify_selection_changed()
    
    def select_objects_in_rect(self, rect: QRectF, objects: List[GeometricObject], 
                              add_to_selection: bool = False):
        """Выделяет объекты, попадающие в прямоугольник"""
        if not add_to_selection:
            self.clear_selection()
        
        new_selection = set()
        for obj in objects:
            if obj.intersects_rect(rect):
                new_selection.add(obj)
        
        if add_to_selection:
            self._selected_objects.update(new_selection)
        else:
            self._selected_objects = new_selection
        
        self._notify_selection_changed()
    
    def clear_selection(self):
        """Очищает выделение"""
        if self._selected_objects:
            self._selected_objects.clear()
            self._notify_selection_changed()
    
    def get_selected_objects(self) -> List[GeometricObject]:
        """Возвращает список выделенных объектов"""
        return list(self._selected_objects)
    
    def get_selected_lines(self) -> List[LineSegment]:
        """Возвращает список выделенных отрезков"""
        return [obj for obj in self._selected_objects if isinstance(obj, LineSegment)]
    
    def is_selected(self, obj: GeometricObject) -> bool:
        """Проверяет, выделен ли объект"""
        return obj in self._selected_objects
    
    def find_object_at_point(self, point: QPointF, objects: List[GeometricObject], 
                            tolerance: float = 5.0) -> Optional[GeometricObject]:
        """Находит объект в указанной точке (проверяет только контур, не площадь)"""
        closest_obj = None
        min_distance = float('inf')
        
        for obj in objects:
            if obj.contains_point(point, tolerance):
                # Для линий вычисляем точное расстояние до контура
                if isinstance(obj, LineSegment):
                    distance = self._point_to_line_distance(
                        point, obj.start_point, obj.end_point
                    )
                    if distance < tolerance and distance < min_distance:
                        min_distance = distance
                        closest_obj = obj
                else:
                    # Для других объектов используем расстояние до центра bounding box
                    # как приближение для выбора ближайшего объекта
                    # (основная проверка контура уже сделана в contains_point)
                    bbox = obj.get_bounding_box()
                    center = QPointF(bbox.center().x(), bbox.center().y())
                    import math
                    dx = point.x() - center.x()
                    dy = point.y() - center.y()
                    distance = math.sqrt(dx*dx + dy*dy)
                    if distance < min_distance:
                        min_distance = distance
                        closest_obj = obj
        
        return closest_obj
    
    def _point_to_line_distance(self, point: QPointF, line_start: QPointF, 
                                line_end: QPointF) -> float:
        """Вычисляет расстояние от точки до отрезка"""
        import math
        
        # Вектор линии
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()
        
        # Если линия - точка
        if dx == 0 and dy == 0:
            return math.sqrt((point.x() - line_start.x())**2 + 
                           (point.y() - line_start.y())**2)
        
        # Параметр t для проекции точки на линию
        t = ((point.x() - line_start.x()) * dx + 
             (point.y() - line_start.y()) * dy) / (dx*dx + dy*dy)
        
        # Ограничиваем t отрезком [0, 1]
        t = max(0, min(1, t))
        
        # Ближайшая точка на отрезке
        closest_x = line_start.x() + t * dx
        closest_y = line_start.y() + t * dy
        
        # Расстояние от точки до ближайшей точки на отрезке
        return math.sqrt((point.x() - closest_x)**2 + (point.y() - closest_y)**2)
    
    def _notify_selection_changed(self):
        """Уведомляет об изменении выделения"""
        self.selection_changed.emit(self.get_selected_objects())

