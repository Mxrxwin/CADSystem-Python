"""
Система привязок для геометрических объектов
"""
from typing import List, Optional, Tuple
from enum import Enum
from PySide6.QtCore import QPointF
import math

from core.geometry import GeometricObject
from widgets.line_segment import LineSegment
from widgets.primitives import Circle, Arc, Rectangle, Ellipse, Polygon, Spline


class SnapType(Enum):
    """Типы точек привязки"""
    END = "end"  # Конец
    MIDDLE = "middle"  # Середина
    CENTER = "center"  # Центр
    VERTEX = "vertex"  # Вершина
    INTERSECTION = "intersection"  # Пересечение
    PERPENDICULAR = "perpendicular"  # Перпендикуляр
    TANGENT = "tangent"  # Касательная


class SnapPoint:
    """Точка привязки"""
    
    def __init__(self, point: QPointF, snap_type: SnapType, object: GeometricObject):
        self.point = point
        self.snap_type = snap_type
        self.object = object
    
    def distance_to(self, other_point: QPointF) -> float:
        """Вычисляет расстояние до другой точки"""
        dx = self.point.x() - other_point.x()
        dy = self.point.y() - other_point.y()
        return math.sqrt(dx*dx + dy*dy)


class SnapManager:
    """Менеджер системы привязок"""
    
    def __init__(self, tolerance: float = 10.0):
        """
        Инициализация менеджера привязок
        Args:
            tolerance: Радиус привязки в пикселях
        """
        self.tolerance = tolerance
        self.enabled = True
        self.snap_to_end = True
        self.snap_to_middle = True
        self.snap_to_center = True
        self.snap_to_vertex = True
        self.snap_to_intersection = True
        self.snap_to_perpendicular = True
        self.snap_to_tangent = True
    
    def set_tolerance(self, tolerance: float):
        """Устанавливает радиус привязки"""
        self.tolerance = tolerance
    
    def get_snap_points(self, objects: List[GeometricObject], 
                       exclude_object: Optional[GeometricObject] = None) -> List[SnapPoint]:
        """
        Получает все точки привязки из объектов
        Args:
            objects: Список объектов для извлечения точек привязки
            exclude_object: Объект, который нужно исключить (например, текущий рисуемый)
        Returns:
            Список точек привязки
        """
        snap_points = []
        
        for obj in objects:
            if exclude_object and obj is exclude_object:
                continue
            
            if isinstance(obj, LineSegment):
                snap_points.extend(self._get_line_snap_points(obj))
            elif isinstance(obj, Circle):
                snap_points.extend(self._get_circle_snap_points(obj))
            elif isinstance(obj, Arc):
                snap_points.extend(self._get_arc_snap_points(obj))
            elif isinstance(obj, Rectangle):
                snap_points.extend(self._get_rectangle_snap_points(obj))
            elif isinstance(obj, Ellipse):
                snap_points.extend(self._get_ellipse_snap_points(obj))
            elif isinstance(obj, Polygon):
                snap_points.extend(self._get_polygon_snap_points(obj))
            elif isinstance(obj, Spline):
                snap_points.extend(self._get_spline_snap_points(obj))
        
        # Добавляем точки пересечения между всеми парами объектов
        if self.snap_to_intersection:
            intersection_points = self._get_all_intersections(objects, exclude_object)
            snap_points.extend(intersection_points)
        
        return snap_points
    
    def _get_line_snap_points(self, line: LineSegment) -> List[SnapPoint]:
        """Получает точки привязки для отрезка"""
        points = []
        
        if self.snap_to_end:
            points.append(SnapPoint(line.start_point, SnapType.END, line))
            points.append(SnapPoint(line.end_point, SnapType.END, line))
        
        if self.snap_to_middle:
            mid_x = (line.start_point.x() + line.end_point.x()) / 2.0
            mid_y = (line.start_point.y() + line.end_point.y()) / 2.0
            points.append(SnapPoint(QPointF(mid_x, mid_y), SnapType.MIDDLE, line))
        
        return points
    
    def _get_circle_snap_points(self, circle: Circle) -> List[SnapPoint]:
        """Получает точки привязки для окружности"""
        points = []
        
        if self.snap_to_center:
            points.append(SnapPoint(circle.center, SnapType.CENTER, circle))
        
        # 4 крайние точки окружности (верхняя, нижняя, левая, правая)
        if self.snap_to_vertex or self.snap_to_end:
            extreme_points = [
                QPointF(circle.center.x(), circle.center.y() - circle.radius),  # Верхняя
                QPointF(circle.center.x(), circle.center.y() + circle.radius),  # Нижняя
                QPointF(circle.center.x() - circle.radius, circle.center.y()),  # Левая
                QPointF(circle.center.x() + circle.radius, circle.center.y())   # Правая
            ]
            
            for point in extreme_points:
                if self.snap_to_vertex:
                    points.append(SnapPoint(point, SnapType.VERTEX, circle))
                elif self.snap_to_end:
                    points.append(SnapPoint(point, SnapType.END, circle))
        
        return points
    
    def _get_arc_snap_points(self, arc: Arc) -> List[SnapPoint]:
        """Получает точки привязки для дуги - центр + 4 крайние точки (верх, низ, лево, право) + третья заданная точка"""
        points = []
        
        if self.snap_to_center:
            points.append(SnapPoint(arc.center, SnapType.CENTER, arc))
        
        # Get 4 extreme points of the ellipse (top, bottom, left, right)
        # These are calculated even if they don't fall within the arc range
        # Extreme points in local coordinates (before rotation)
        extreme_points_local = [
            (0, "right", arc.radius_x, 0),      # Right: parametric angle 0°
            (90, "bottom", 0, arc.radius_y),    # Bottom: parametric angle 90°
            (180, "left", -arc.radius_x, 0),    # Left: parametric angle 180°
            (270, "top", 0, -arc.radius_y)     # Top: parametric angle 270°
        ]
        
        # Function to check if point is duplicate
        def is_duplicate_point(new_point: QPointF, existing_points: List[SnapPoint]) -> bool:
            for existing in existing_points:
                dx = new_point.x() - existing.point.x()
                dy = new_point.y() - existing.point.y()
                distance = math.sqrt(dx*dx + dy*dy)
                if distance < 0.1:
                    return True
            return False
        
        # Apply rotation and add all 4 extreme points (even if not in arc range)
        if abs(arc.rotation_angle) > 1e-6:
            cos_r = math.cos(arc.rotation_angle)
            sin_r = math.sin(arc.rotation_angle)
            for param_angle, name, local_x, local_y in extreme_points_local:
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
                world_point = QPointF(
                    arc.center.x() + rotated_x,
                    arc.center.y() + rotated_y
                )
                if not is_duplicate_point(world_point, points):
                    if self.snap_to_vertex:
                        points.append(SnapPoint(world_point, SnapType.VERTEX, arc))
                    elif self.snap_to_end:
                        points.append(SnapPoint(world_point, SnapType.END, arc))
        else:
            # No rotation
            for param_angle, name, local_x, local_y in extreme_points_local:
                world_point = QPointF(
                    arc.center.x() + local_x,
                    arc.center.y() + local_y
                )
                if not is_duplicate_point(world_point, points):
                    if self.snap_to_vertex:
                        points.append(SnapPoint(world_point, SnapType.VERTEX, arc))
                    elif self.snap_to_end:
                        points.append(SnapPoint(world_point, SnapType.END, arc))
        
        return points
    
    def _get_arc_point_at_angle(self, arc: Arc, angle_deg: float) -> QPointF:
        """Вычисляет точку на дуге для заданного угла в градусах"""
        import math
        rad = math.radians(angle_deg)
        local_x = arc.radius_x * math.cos(rad)
        local_y = arc.radius_y * math.sin(rad)
        
        # Apply rotation if present
        if abs(arc.rotation_angle) > 1e-6:
            cos_r = math.cos(arc.rotation_angle)
            sin_r = math.sin(arc.rotation_angle)
            rotated_x = local_x * cos_r - local_y * sin_r
            rotated_y = local_x * sin_r + local_y * cos_r
        else:
            rotated_x = local_x
            rotated_y = local_y
        
        # Convert to world coordinates
        x = arc.center.x() + rotated_x
        y = arc.center.y() + rotated_y
        return QPointF(x, y)
    
    def _get_rectangle_snap_points(self, rect: Rectangle) -> List[SnapPoint]:
        """Получает точки привязки для прямоугольника"""
        points = []
        
        bbox = rect.get_bounding_box()
        top_left = QPointF(bbox.left(), bbox.top())
        top_right = QPointF(bbox.right(), bbox.top())
        bottom_left = QPointF(bbox.left(), bbox.bottom())
        bottom_right = QPointF(bbox.right(), bbox.bottom())
        center = QPointF(bbox.center().x(), bbox.center().y())
        
        if self.snap_to_end:
            # Углы прямоугольника - это "концы"
            points.append(SnapPoint(top_left, SnapType.END, rect))
            points.append(SnapPoint(top_right, SnapType.END, rect))
            points.append(SnapPoint(bottom_left, SnapType.END, rect))
            points.append(SnapPoint(bottom_right, SnapType.END, rect))
        
        if self.snap_to_center:
            points.append(SnapPoint(center, SnapType.CENTER, rect))
        
        if self.snap_to_middle:
            # Середины сторон прямоугольника
            mid_top = QPointF(bbox.center().x(), bbox.top())
            mid_bottom = QPointF(bbox.center().x(), bbox.bottom())
            mid_left = QPointF(bbox.left(), bbox.center().y())
            mid_right = QPointF(bbox.right(), bbox.center().y())
            points.append(SnapPoint(mid_top, SnapType.MIDDLE, rect))
            points.append(SnapPoint(mid_bottom, SnapType.MIDDLE, rect))
            points.append(SnapPoint(mid_left, SnapType.MIDDLE, rect))
            points.append(SnapPoint(mid_right, SnapType.MIDDLE, rect))
        
        return points
    
    def _get_ellipse_snap_points(self, ellipse: Ellipse) -> List[SnapPoint]:
        """Получает точки привязки для эллипса"""
        points = []
        
        if self.snap_to_center:
            points.append(SnapPoint(ellipse.center, SnapType.CENTER, ellipse))
        
        # 4 крайние точки эллипса (верх, низ, лево, право)
        if self.snap_to_vertex or self.snap_to_end:
            # Вычисляем крайние точки в локальной системе координат
            # Верх: (0, -radius_y)
            # Низ: (0, radius_y)
            # Лево: (-radius_x, 0)
            # Право: (radius_x, 0)
            extreme_points_local = [
                QPointF(0, -ellipse.radius_y),  # Верх
                QPointF(0, ellipse.radius_y),   # Низ
                QPointF(-ellipse.radius_x, 0),  # Лево
                QPointF(ellipse.radius_x, 0)    # Право
            ]
            
            # Применяем поворот, если он есть
            if abs(ellipse.rotation_angle) > 1e-6:
                cos_r = math.cos(ellipse.rotation_angle)
                sin_r = math.sin(ellipse.rotation_angle)
                for local_point in extreme_points_local:
                    rotated_x = local_point.x() * cos_r - local_point.y() * sin_r
                    rotated_y = local_point.x() * sin_r + local_point.y() * cos_r
                    world_point = QPointF(
                        ellipse.center.x() + rotated_x,
                        ellipse.center.y() + rotated_y
                    )
                    if self.snap_to_vertex:
                        points.append(SnapPoint(world_point, SnapType.VERTEX, ellipse))
                    elif self.snap_to_end:
                        points.append(SnapPoint(world_point, SnapType.END, ellipse))
            else:
                # Без поворота
                for local_point in extreme_points_local:
                    world_point = QPointF(
                        ellipse.center.x() + local_point.x(),
                        ellipse.center.y() + local_point.y()
                    )
                    if self.snap_to_vertex:
                        points.append(SnapPoint(world_point, SnapType.VERTEX, ellipse))
                    elif self.snap_to_end:
                        points.append(SnapPoint(world_point, SnapType.END, ellipse))
        
        return points
    
    def _get_polygon_snap_points(self, polygon: Polygon) -> List[SnapPoint]:
        """Получает точки привязки для многоугольника"""
        points = []
        
        # Центр многоугольника
        if self.snap_to_center:
            points.append(SnapPoint(polygon.center, SnapType.CENTER, polygon))
        
        # Получаем все вершины многоугольника
        vertices = polygon.get_vertices()
        
        # Вершины многоугольника
        if self.snap_to_vertex:
            for vertex in vertices:
                points.append(SnapPoint(vertex, SnapType.VERTEX, polygon))
        
        # Середины граней многоугольника
        if self.snap_to_middle:
            for i in range(len(vertices)):
                p1 = vertices[i]
                p2 = vertices[(i + 1) % len(vertices)]
                mid_x = (p1.x() + p2.x()) / 2.0
                mid_y = (p1.y() + p2.y()) / 2.0
                points.append(SnapPoint(QPointF(mid_x, mid_y), SnapType.MIDDLE, polygon))
        
        return points
    
    def _get_spline_snap_points(self, spline: Spline) -> List[SnapPoint]:
        """Получает точки привязки для сплайна"""
        points = []
        
        # Все контрольные точки сплайна
        if self.snap_to_vertex or self.snap_to_end:
            for control_point in spline.control_points:
                if self.snap_to_vertex:
                    points.append(SnapPoint(control_point, SnapType.VERTEX, spline))
                elif self.snap_to_end:
                    points.append(SnapPoint(control_point, SnapType.END, spline))
        
        return points
    
    def get_dynamic_snap_points(self, point: QPointF, objects: List[GeometricObject],
                                exclude_object: Optional[GeometricObject] = None,
                                start_point: Optional[QPointF] = None) -> List[SnapPoint]:
        """
        Получает динамические точки привязки (пересечение, перпендикуляр, касательная)
        Args:
            point: Текущая позиция курсора
            objects: Список объектов для проверки
            exclude_object: Объект, который нужно исключить
            start_point:  текущего рисования (для линии/дуги)
        Returns:
            Список динамических точек привязки
        """
        dynamic_points = []
        
        if not self.enabled:
            return dynamic_points
        
        for obj in objects:
            if exclude_object and obj is exclude_object:
                continue
            
            # Пересечения
            if self.snap_to_intersection and start_point:
                intersections = self._find_intersections(start_point, point, obj)
                for intersection in intersections:
                    # Проверяем, что точка пересечения не слишком близко к началу или концу линии
                    dist_to_start = math.sqrt((intersection.x() - start_point.x())**2 + 
                                             (intersection.y() - start_point.y())**2)
                    dist_to_end = math.sqrt((intersection.x() - point.x())**2 + 
                                           (intersection.y() - point.y())**2)
                    # Игнорируем точки, которые слишком близко к концам (меньше 1 пикселя)
                    if dist_to_start > 1.0 and dist_to_end > 1.0:
                        dynamic_points.append(SnapPoint(intersection, SnapType.INTERSECTION, obj))
            
            # Перпендикуляры
            if self.snap_to_perpendicular and start_point:
                perpendicular = self._find_perpendicular_point(start_point, point, obj)
                if perpendicular:
                    dynamic_points.append(SnapPoint(perpendicular, SnapType.PERPENDICULAR, obj))
            
            # Касательные
            if self.snap_to_tangent:
                tangents = self._find_tangent_points(point, obj)
                for tangent in tangents:
                    dynamic_points.append(SnapPoint(tangent, SnapType.TANGENT, obj))
        
        return dynamic_points
    
    def _find_intersections(self, line_start: QPointF, line_end: QPointF, 
                           obj: GeometricObject) -> List[QPointF]:
        """Находит точки пересечения линии с объектом"""
        intersections = []
        
        if isinstance(obj, LineSegment):
            intersection = self._line_line_intersection(
                line_start, line_end, obj.start_point, obj.end_point
            )
            if intersection:
                # Проверяем, что точка не совпадает с началом или концом линии
                dist_to_start = math.sqrt((intersection.x() - line_start.x())**2 + 
                                         (intersection.y() - line_start.y())**2)
                dist_to_end = math.sqrt((intersection.x() - line_end.x())**2 + 
                                       (intersection.y() - line_end.y())**2)
                if dist_to_start > 1e-6 and dist_to_end > 1e-6:
                    intersections.append(intersection)
        elif isinstance(obj, Circle):
            intersections.extend(self._line_circle_intersection(
                line_start, line_end, obj.center, obj.radius
            ))
        elif isinstance(obj, Arc):
            intersections.extend(self._line_arc_intersection(
                line_start, line_end, obj
            ))
        elif isinstance(obj, Ellipse):
            intersections.extend(self._line_ellipse_intersection(
                line_start, line_end, obj
            ))
        elif isinstance(obj, Rectangle):
            # Пересечение с прямоугольником = пересечение с его сторонами
            bbox = obj.get_bounding_box()
            corners = [
                (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
                (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
                (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
                (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
            ]
            for corner_start, corner_end in corners:
                intersection = self._line_line_intersection(
                    line_start, line_end, corner_start, corner_end
                )
                if intersection:
                    intersections.append(intersection)
        
        return intersections
    
    def _get_all_intersections(self, objects: List[GeometricObject],
                               exclude_object: Optional[GeometricObject] = None) -> List[SnapPoint]:
        """
        Вычисляет все точки пересечения между всеми парами объектов
        Args:
            objects: Список объектов
            exclude_object: Объект, который нужно исключить
        Returns:
            Список точек привязки для пересечений
        """
        intersection_snap_points = []
        seen_intersections = set()  # Для избежания дубликатов
        
        # Проверяем, что у нас есть хотя бы 2 объекта
        if len(objects) < 2:
            return intersection_snap_points
        
        total_intersections_found = 0
        
        for i, obj1 in enumerate(objects):
            if exclude_object and obj1 is exclude_object:
                continue
            
            for j, obj2 in enumerate(objects[i+1:], start=i+1):
                if exclude_object and obj2 is exclude_object:
                    continue
                
                # Вычисляем пересечения между obj1 и obj2
                obj1_type = type(obj1).__name__
                obj2_type = type(obj2).__name__
                intersections = self._find_object_intersections(obj1, obj2)
                
                if intersections:
                    total_intersections_found += len(intersections)
                
                for intersection in intersections:
                    # Проверяем, не дубликат ли это (с учетом небольшой погрешности)
                    intersection_key = (round(intersection.x(), 6), round(intersection.y(), 6))
                    if intersection_key not in seen_intersections:
                        seen_intersections.add(intersection_key)
                        # Создаем точку привязки для пересечения
                        # Используем obj1 как основной объект (можно было бы использовать оба)
                        intersection_snap_points.append(
                            SnapPoint(intersection, SnapType.INTERSECTION, obj1)
                        )
        return intersection_snap_points
    
    def _find_object_intersections(self, obj1: GeometricObject, 
                                   obj2: GeometricObject) -> List[QPointF]:
        """
        Находит точки пересечения между двумя объектами
        Args:
            obj1: Первый объект
            obj2: Второй объект
        Returns:
            Список точек пересечения
        """
        intersections = []
        
        # Отрезок с отрезком
        if isinstance(obj1, LineSegment) and isinstance(obj2, LineSegment):
            intersection = self._line_line_intersection(
                obj1.start_point, obj1.end_point,
                obj2.start_point, obj2.end_point
            )
            if intersection:
                intersections.append(intersection)
        
        # Отрезок с окружностью
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Circle):
            intersections.extend(self._line_circle_intersection(
                obj1.start_point, obj1.end_point,
                obj2.center, obj2.radius
            ))
        elif isinstance(obj1, Circle) and isinstance(obj2, LineSegment):
            intersections.extend(self._line_circle_intersection(
                obj2.start_point, obj2.end_point,
                obj1.center, obj1.radius
            ))
        
        # Отрезок с дугой
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Arc):
            intersections.extend(self._line_arc_intersection(
                obj1.start_point, obj1.end_point, obj2
            ))
        elif isinstance(obj1, Arc) and isinstance(obj2, LineSegment):
            intersections.extend(self._line_arc_intersection(
                obj2.start_point, obj2.end_point, obj1
            ))
        
        # Отрезок с эллипсом
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Ellipse):
            line_ellipse_inters = self._line_ellipse_intersection(
                obj1.start_point, obj1.end_point, obj2
            )
            intersections.extend(line_ellipse_inters)
        elif isinstance(obj1, Ellipse) and isinstance(obj2, LineSegment):
            ellipse_line_inters = self._line_ellipse_intersection(
                obj2.start_point, obj2.end_point, obj1
            )
            intersections.extend(ellipse_line_inters)
        
        # Отрезок с прямоугольником
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Rectangle):
            bbox = obj2.get_bounding_box()
            sides = [
                (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
                (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
                (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
                (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
            ]
            for side_start, side_end in sides:
                intersection = self._line_line_intersection(
                    obj1.start_point, obj1.end_point, side_start, side_end
                )
                if intersection:
                    intersections.append(intersection)
        elif isinstance(obj1, Rectangle) and isinstance(obj2, LineSegment):
            bbox = obj1.get_bounding_box()
            sides = [
                (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
                (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
                (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
                (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
            ]
            for side_start, side_end in sides:
                intersection = self._line_line_intersection(
                    obj2.start_point, obj2.end_point, side_start, side_end
                )
                if intersection:
                    intersections.append(intersection)
        
        # Отрезок с многоугольником
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Polygon):
            vertices = obj2.get_vertices()
            for i in range(len(vertices)):
                p1 = vertices[i]
                p2 = vertices[(i + 1) % len(vertices)]
                intersection = self._line_line_intersection(
                    obj1.start_point, obj1.end_point, p1, p2
                )
                if intersection:
                    intersections.append(intersection)
        elif isinstance(obj1, Polygon) and isinstance(obj2, LineSegment):
            vertices = obj1.get_vertices()
            for i in range(len(vertices)):
                p1 = vertices[i]
                p2 = vertices[(i + 1) % len(vertices)]
                intersection = self._line_line_intersection(
                    obj2.start_point, obj2.end_point, p1, p2
                )
                if intersection:
                    intersections.append(intersection)
        
        # Отрезок со сплайном (приближенно)
        elif isinstance(obj1, LineSegment) and isinstance(obj2, Spline):
            # Аппроксимируем сплайн сегментами и находим пересечения
            intersections.extend(self._line_spline_intersection(
                obj1.start_point, obj1.end_point, obj2
            ))
        elif isinstance(obj1, Spline) and isinstance(obj2, LineSegment):
            intersections.extend(self._line_spline_intersection(
                obj2.start_point, obj2.end_point, obj1
            ))
        
        # Окружность с окружностью
        elif isinstance(obj1, Circle) and isinstance(obj2, Circle):
            intersections.extend(self._circle_circle_intersection(
                obj1.center, obj1.radius, obj2.center, obj2.radius
            ))
        
        # Окружность с дугой/эллипсом
        elif isinstance(obj1, Circle) and isinstance(obj2, (Arc, Ellipse)):
            # Находим пересечения окружности с эллипсом
            ellipse_intersections = self._circle_ellipse_intersection(
                obj1.center, obj1.radius, obj2
            )
            # Если это дуга, фильтруем по диапазону
            if isinstance(obj2, Arc):
                for point in ellipse_intersections:
                    if self._point_on_arc(point, obj2):
                        intersections.append(point)
            else:
                intersections.extend(ellipse_intersections)
        elif isinstance(obj1, (Arc, Ellipse)) and isinstance(obj2, Circle):
            ellipse_intersections = self._circle_ellipse_intersection(
                obj2.center, obj2.radius, obj1
            )
            if isinstance(obj1, Arc):
                for point in ellipse_intersections:
                    if self._point_on_arc(point, obj1):
                        intersections.append(point)
            else:
                intersections.extend(ellipse_intersections)
        
        # Эллипс с эллипсом (приближенно)
        elif isinstance(obj1, (Arc, Ellipse)) and isinstance(obj2, (Arc, Ellipse)):
            # Упрощенный метод: аппроксимируем эллипсы многоугольниками
            # Метод _ellipse_ellipse_intersection уже учитывает дуги через _line_arc_intersection
            ellipse_intersections = self._ellipse_ellipse_intersection(obj1, obj2)
            # Дополнительная фильтрация для дуг (на случай, если первая дуга не была учтена)
            for point in ellipse_intersections:
                is_valid = True
                if isinstance(obj1, Arc):
                    if not self._point_on_arc(point, obj1):
                        is_valid = False
                if isinstance(obj2, Arc) and is_valid:
                    if not self._point_on_arc(point, obj2):
                        is_valid = False
                if is_valid:
                    intersections.append(point)
        
        # Прямоугольник с окружностью
        elif isinstance(obj1, Rectangle) and isinstance(obj2, Circle):
            intersections.extend(self._rectangle_circle_intersection(obj1, obj2))
        elif isinstance(obj1, Circle) and isinstance(obj2, Rectangle):
            intersections.extend(self._rectangle_circle_intersection(obj2, obj1))
        
        # Прямоугольник с дугой/эллипсом
        elif isinstance(obj1, Rectangle) and isinstance(obj2, (Arc, Ellipse)):
            intersections.extend(self._rectangle_ellipse_intersection(obj1, obj2))
        elif isinstance(obj1, (Arc, Ellipse)) and isinstance(obj2, Rectangle):
            intersections.extend(self._rectangle_ellipse_intersection(obj2, obj1))
        
        # Многоугольник с окружностью
        elif isinstance(obj1, Polygon) and isinstance(obj2, Circle):
            intersections.extend(self._polygon_circle_intersection(obj1, obj2))
        elif isinstance(obj1, Circle) and isinstance(obj2, Polygon):
            intersections.extend(self._polygon_circle_intersection(obj2, obj1))
        
        # Многоугольник с дугой/эллипсом
        elif isinstance(obj1, Polygon) and isinstance(obj2, (Arc, Ellipse)):
            intersections.extend(self._polygon_ellipse_intersection(obj1, obj2))
        elif isinstance(obj1, (Arc, Ellipse)) and isinstance(obj2, Polygon):
            intersections.extend(self._polygon_ellipse_intersection(obj2, obj1))
        
        # Многоугольник с прямоугольником
        elif isinstance(obj1, Polygon) and isinstance(obj2, Rectangle):
            intersections.extend(self._polygon_rectangle_intersection(obj1, obj2))
        elif isinstance(obj1, Rectangle) and isinstance(obj2, Polygon):
            intersections.extend(self._polygon_rectangle_intersection(obj2, obj1))
        
        # Прямоугольник с прямоугольником
        elif isinstance(obj1, Rectangle) and isinstance(obj2, Rectangle):
            intersections.extend(self._rectangle_rectangle_intersection(obj1, obj2))
        
        # Сплайн с окружностью
        elif isinstance(obj1, Spline) and isinstance(obj2, Circle):
            intersections.extend(self._spline_circle_intersection(obj1, obj2))
        elif isinstance(obj1, Circle) and isinstance(obj2, Spline):
            intersections.extend(self._spline_circle_intersection(obj2, obj1))
        
        # Сплайн с дугой/эллипсом
        elif isinstance(obj1, Spline) and isinstance(obj2, (Arc, Ellipse)):
            intersections.extend(self._spline_ellipse_intersection(obj1, obj2))
        elif isinstance(obj1, (Arc, Ellipse)) and isinstance(obj2, Spline):
            intersections.extend(self._spline_ellipse_intersection(obj2, obj1))
        
        # Сплайн с прямоугольником
        elif isinstance(obj1, Spline) and isinstance(obj2, Rectangle):
            intersections.extend(self._spline_rectangle_intersection(obj1, obj2))
        elif isinstance(obj1, Rectangle) and isinstance(obj2, Spline):
            intersections.extend(self._spline_rectangle_intersection(obj2, obj1))
        
        # Сплайн с многоугольником
        elif isinstance(obj1, Spline) and isinstance(obj2, Polygon):
            intersections.extend(self._spline_polygon_intersection(obj1, obj2))
        elif isinstance(obj1, Polygon) and isinstance(obj2, Spline):
            intersections.extend(self._spline_polygon_intersection(obj2, obj1))
        
        return intersections
    
    def _line_spline_intersection(self, line_start: QPointF, line_end: QPointF,
                                  spline: Spline) -> List[QPointF]:
        """Находит точки пересечения линии со сплайном (приближенно)"""
        intersections = []
        
        # Аппроксимируем сплайн сегментами
        num_samples = max(50, len(spline.control_points) * 10)
        prev_point = spline._get_point_on_spline(0)
        
        for i in range(1, num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            curr_point = spline._get_point_on_spline(t)
            
            # Проверяем пересечение линии с сегментом сплайна
            intersection = self._line_line_intersection(
                line_start, line_end, prev_point, curr_point
            )
            if intersection:
                intersections.append(intersection)
            
            prev_point = curr_point
        
        return intersections
    
    def _circle_circle_intersection(self, center1: QPointF, radius1: float,
                                    center2: QPointF, radius2: float) -> List[QPointF]:
        """Находит точки пересечения двух окружностей"""
        intersections = []
        
        dx = center2.x() - center1.x()
        dy = center2.y() - center1.y()
        dist_sq = dx*dx + dy*dy
        dist = math.sqrt(dist_sq)
        
        # Проверяем, пересекаются ли окружности
        if dist > radius1 + radius2 or dist < abs(radius1 - radius2):
            return intersections  # Не пересекаются
        
        if dist < 1e-10:
            return intersections  # Концентрические окружности
        
        # Вычисляем точки пересечения
        a = (radius1*radius1 - radius2*radius2 + dist_sq) / (2 * dist)
        h_sq = radius1*radius1 - a*a
        
        if h_sq < 0:
            return intersections
        
        h = math.sqrt(h_sq)
        
        # Точка на линии между центрами
        p2_x = center1.x() + a * dx / dist
        p2_y = center1.y() + a * dy / dist
        
        # Перпендикулярное направление
        perp_x = -dy / dist
        perp_y = dx / dist
        
        # Две точки пересечения
        for sign in [-1, 1]:
            x = p2_x + sign * h * perp_x
            y = p2_y + sign * h * perp_y
            intersections.append(QPointF(x, y))
        
        return intersections
    
    def _circle_ellipse_intersection(self, circle_center: QPointF, circle_radius: float,
                                     ellipse) -> List[QPointF]:
        """Находит точки пересечения окружности с эллипсом (приближенно)"""
        intersections = []
        seen_points = set()  # Для избежания дубликатов
        
        # Аппроксимируем окружность многоугольником и находим пересечения с эллипсом
        num_samples = 128  # Увеличиваем количество точек для лучшей точности
        prev_point = QPointF(
            circle_center.x() + circle_radius,
            circle_center.y()
        )
        
        for i in range(1, num_samples + 1):
            angle = 2 * math.pi * i / num_samples
            curr_point = QPointF(
                circle_center.x() + circle_radius * math.cos(angle),
                circle_center.y() + circle_radius * math.sin(angle)
            )
            
            # Проверяем пересечение сегмента окружности с эллипсом
            # Если это дуга, используем специальный метод
            if isinstance(ellipse, Arc):
                segment_intersections = self._line_arc_intersection(
                    prev_point, curr_point, ellipse
                )
            else:
                segment_intersections = self._line_ellipse_intersection(
                    prev_point, curr_point, ellipse
                )
            
            # Добавляем только уникальные точки
            for point in segment_intersections:
                point_key = (round(point.x(), 6), round(point.y(), 6))
                if point_key not in seen_points:
                    seen_points.add(point_key)
                    intersections.append(point)
            
            prev_point = curr_point
        
        return intersections
    
    def _ellipse_ellipse_intersection(self, ellipse1, ellipse2) -> List[QPointF]:
        """Находит точки пересечения двух эллипсов (приближенно)"""
        intersections = []
        seen_points = set()  # Для избежания дубликатов
        
        # Аппроксимируем первый эллипс многоугольником
        num_samples = 128  # Увеличиваем количество точек для лучшей точности
        
        # Определяем диапазон углов для первого эллипса (если это дуга)
        if isinstance(ellipse1, Arc):
            # Для дуги генерируем точки только в диапазоне дуги
            start_angle_rad = math.radians(ellipse1.start_angle)
            end_angle_rad = math.radians(ellipse1.end_angle)
            # Нормализуем углы
            if end_angle_rad < start_angle_rad:
                end_angle_rad += 2 * math.pi
            angle_range = end_angle_rad - start_angle_rad
            angles = []
            for i in range(num_samples + 1):
                t = i / num_samples
                angle = start_angle_rad + t * angle_range
                angles.append(angle)
        else:
            # Для полного эллипса генерируем точки по всему кругу
            angles = [2 * math.pi * i / num_samples for i in range(num_samples + 1)]
        
        # Генерируем точки на первом эллипсе
        ellipse1_points = []
        for angle in angles:
            local_x = ellipse1.radius_x * math.cos(angle)
            local_y = ellipse1.radius_y * math.sin(angle)
            
            # Применяем поворот
            if abs(ellipse1.rotation_angle) > 1e-6:
                cos_r = math.cos(ellipse1.rotation_angle)
                sin_r = math.sin(ellipse1.rotation_angle)
                x = ellipse1.center.x() + local_x * cos_r - local_y * sin_r
                y = ellipse1.center.y() + local_x * sin_r + local_y * cos_r
            else:
                x = ellipse1.center.x() + local_x
                y = ellipse1.center.y() + local_y
            
            ellipse1_points.append(QPointF(x, y))
        
        # Проверяем пересечения сегментов первого эллипса со вторым
        for i in range(len(ellipse1_points) - 1):
            p1 = ellipse1_points[i]
            p2 = ellipse1_points[i + 1]
            
            # Если второй объект - дуга, используем специальный метод
            if isinstance(ellipse2, Arc):
                segment_intersections = self._line_arc_intersection(
                    p1, p2, ellipse2
                )
            else:
                segment_intersections = self._line_ellipse_intersection(
                    p1, p2, ellipse2
                )
            
            # Добавляем только уникальные точки
            # Дополнительно проверяем, что точка находится на первой дуге (если это дуга)
            for point in segment_intersections:
                # Проверяем, что точка находится на первой дуге (если это дуга)
                if isinstance(ellipse1, Arc):
                    if not self._point_on_arc(point, ellipse1):
                        continue
                
                point_key = (round(point.x(), 6), round(point.y(), 6))
                if point_key not in seen_points:
                    seen_points.add(point_key)
                    intersections.append(point)
        
        return intersections
    
    def _rectangle_circle_intersection(self, rectangle: Rectangle, 
                                       circle: Circle) -> List[QPointF]:
        """Находит точки пересечения прямоугольника с окружностью"""
        intersections = []
        bbox = rectangle.get_bounding_box()
        
        # Проверяем пересечение окружности с каждой стороной прямоугольника
        sides = [
            (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
            (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
            (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
            (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
        ]
        
        for side_start, side_end in sides:
            side_intersections = self._line_circle_intersection(
                side_start, side_end, circle.center, circle.radius
            )
            intersections.extend(side_intersections)
        
        return intersections
    
    def _rectangle_ellipse_intersection(self, rectangle: Rectangle,
                                       ellipse) -> List[QPointF]:
        """Находит точки пересечения прямоугольника с эллипсом/дугой"""
        intersections = []
        bbox = rectangle.get_bounding_box()
        
        # Проверяем пересечение эллипса с каждой стороной прямоугольника
        sides = [
            (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
            (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
            (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
            (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
        ]
        
        for side_start, side_end in sides:
            # Если это дуга, используем специальный метод
            if isinstance(ellipse, Arc):
                side_intersections = self._line_arc_intersection(
                    side_start, side_end, ellipse
                )
            else:
                side_intersections = self._line_ellipse_intersection(
                    side_start, side_end, ellipse
                )
            intersections.extend(side_intersections)
        
        return intersections
    
    def _polygon_circle_intersection(self, polygon: Polygon,
                                     circle: Circle) -> List[QPointF]:
        """Находит точки пересечения многоугольника с окружностью"""
        intersections = []
        vertices = polygon.get_vertices()
        
        # Проверяем пересечение окружности с каждой стороной многоугольника
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            side_intersections = self._line_circle_intersection(
                p1, p2, circle.center, circle.radius
            )
            intersections.extend(side_intersections)
        
        return intersections
    
    def _polygon_ellipse_intersection(self, polygon: Polygon,
                                      ellipse) -> List[QPointF]:
        """Находит точки пересечения многоугольника с эллипсом/дугой"""
        intersections = []
        vertices = polygon.get_vertices()
        
        # Проверяем пересечение эллипса с каждой стороной многоугольника
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            # Если это дуга, используем специальный метод
            if isinstance(ellipse, Arc):
                side_intersections = self._line_arc_intersection(
                    p1, p2, ellipse
                )
            else:
                side_intersections = self._line_ellipse_intersection(
                    p1, p2, ellipse
                )
            intersections.extend(side_intersections)
        
        return intersections
    
    def _polygon_rectangle_intersection(self, polygon: Polygon,
                                        rectangle: Rectangle) -> List[QPointF]:
        """Находит точки пересечения многоугольника с прямоугольником"""
        intersections = []
        polygon_vertices = polygon.get_vertices()
        rect_bbox = rectangle.get_bounding_box()
        
        # Стороны прямоугольника
        rect_sides = [
            (QPointF(rect_bbox.left(), rect_bbox.top()), QPointF(rect_bbox.right(), rect_bbox.top())),  # top
            (QPointF(rect_bbox.right(), rect_bbox.top()), QPointF(rect_bbox.right(), rect_bbox.bottom())),  # right
            (QPointF(rect_bbox.right(), rect_bbox.bottom()), QPointF(rect_bbox.left(), rect_bbox.bottom())),  # bottom
            (QPointF(rect_bbox.left(), rect_bbox.bottom()), QPointF(rect_bbox.left(), rect_bbox.top()))  # left
        ]
        
        # Проверяем пересечение каждой стороны многоугольника с каждой стороной прямоугольника
        for i in range(len(polygon_vertices)):
            p1 = polygon_vertices[i]
            p2 = polygon_vertices[(i + 1) % len(polygon_vertices)]
            
            for rect_side_start, rect_side_end in rect_sides:
                intersection = self._line_line_intersection(
                    p1, p2, rect_side_start, rect_side_end
                )
                if intersection:
                    intersections.append(intersection)
        
        return intersections
    
    def _rectangle_rectangle_intersection(self, rect1: Rectangle,
                                         rect2: Rectangle) -> List[QPointF]:
        """Находит точки пересечения двух прямоугольников"""
        intersections = []
        bbox1 = rect1.get_bounding_box()
        bbox2 = rect2.get_bounding_box()
        
        # Стороны первого прямоугольника
        sides1 = [
            (QPointF(bbox1.left(), bbox1.top()), QPointF(bbox1.right(), bbox1.top())),  # top
            (QPointF(bbox1.right(), bbox1.top()), QPointF(bbox1.right(), bbox1.bottom())),  # right
            (QPointF(bbox1.right(), bbox1.bottom()), QPointF(bbox1.left(), bbox1.bottom())),  # bottom
            (QPointF(bbox1.left(), bbox1.bottom()), QPointF(bbox1.left(), bbox1.top()))  # left
        ]
        
        # Стороны второго прямоугольника
        sides2 = [
            (QPointF(bbox2.left(), bbox2.top()), QPointF(bbox2.right(), bbox2.top())),  # top
            (QPointF(bbox2.right(), bbox2.top()), QPointF(bbox2.right(), bbox2.bottom())),  # right
            (QPointF(bbox2.right(), bbox2.bottom()), QPointF(bbox2.left(), bbox2.bottom())),  # bottom
            (QPointF(bbox2.left(), bbox2.bottom()), QPointF(bbox2.left(), bbox2.top()))  # left
        ]
        
        # Проверяем пересечение каждой стороны первого прямоугольника с каждой стороной второго
        for side1_start, side1_end in sides1:
            for side2_start, side2_end in sides2:
                intersection = self._line_line_intersection(
                    side1_start, side1_end, side2_start, side2_end
                )
                if intersection:
                    intersections.append(intersection)
        
        return intersections
    
    def _spline_circle_intersection(self, spline: Spline,
                                    circle: Circle) -> List[QPointF]:
        """Находит точки пересечения сплайна с окружностью"""
        intersections = []
        
        # Аппроксимируем сплайн сегментами
        num_samples = max(50, len(spline.control_points) * 10)
        prev_point = spline._get_point_on_spline(0)
        
        for i in range(1, num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            curr_point = spline._get_point_on_spline(t)
            
            # Проверяем пересечение сегмента сплайна с окружностью
            segment_intersections = self._line_circle_intersection(
                prev_point, curr_point, circle.center, circle.radius
            )
            intersections.extend(segment_intersections)
            
            prev_point = curr_point
        
        return intersections
    
    def _spline_ellipse_intersection(self, spline: Spline,
                                      ellipse) -> List[QPointF]:
        """Находит точки пересечения сплайна с эллипсом/дугой"""
        intersections = []
        
        # Аппроксимируем сплайн сегментами
        num_samples = max(50, len(spline.control_points) * 10)
        prev_point = spline._get_point_on_spline(0)
        
        for i in range(1, num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            curr_point = spline._get_point_on_spline(t)
            
            # Проверяем пересечение сегмента сплайна с эллипсом
            # Если это дуга, используем специальный метод
            if isinstance(ellipse, Arc):
                segment_intersections = self._line_arc_intersection(
                    prev_point, curr_point, ellipse
                )
            else:
                segment_intersections = self._line_ellipse_intersection(
                    prev_point, curr_point, ellipse
                )
            intersections.extend(segment_intersections)
            
            prev_point = curr_point
        
        return intersections
    
    def _spline_rectangle_intersection(self, spline: Spline,
                                       rectangle: Rectangle) -> List[QPointF]:
        """Находит точки пересечения сплайна с прямоугольником"""
        intersections = []
        bbox = rectangle.get_bounding_box()
        
        # Стороны прямоугольника
        sides = [
            (QPointF(bbox.left(), bbox.top()), QPointF(bbox.right(), bbox.top())),  # top
            (QPointF(bbox.right(), bbox.top()), QPointF(bbox.right(), bbox.bottom())),  # right
            (QPointF(bbox.right(), bbox.bottom()), QPointF(bbox.left(), bbox.bottom())),  # bottom
            (QPointF(bbox.left(), bbox.bottom()), QPointF(bbox.left(), bbox.top()))  # left
        ]
        
        # Аппроксимируем сплайн сегментами
        num_samples = max(50, len(spline.control_points) * 10)
        prev_point = spline._get_point_on_spline(0)
        
        for i in range(1, num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            curr_point = spline._get_point_on_spline(t)
            
            # Проверяем пересечение сегмента сплайна с каждой стороной прямоугольника
            for side_start, side_end in sides:
                intersection = self._line_line_intersection(
                    prev_point, curr_point, side_start, side_end
                )
                if intersection:
                    intersections.append(intersection)
            
            prev_point = curr_point
        
        return intersections
    
    def _spline_polygon_intersection(self, spline: Spline,
                                    polygon: Polygon) -> List[QPointF]:
        """Находит точки пересечения сплайна с многоугольником"""
        intersections = []
        vertices = polygon.get_vertices()
        
        # Аппроксимируем сплайн сегментами
        num_samples = max(50, len(spline.control_points) * 10)
        prev_point = spline._get_point_on_spline(0)
        
        for i in range(1, num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            curr_point = spline._get_point_on_spline(t)
            
            # Проверяем пересечение сегмента сплайна с каждой стороной многоугольника
            for j in range(len(vertices)):
                p1 = vertices[j]
                p2 = vertices[(j + 1) % len(vertices)]
                intersection = self._line_line_intersection(
                    prev_point, curr_point, p1, p2
                )
                if intersection:
                    intersections.append(intersection)
            
            prev_point = curr_point
        
        return intersections
    
    def _find_perpendicular_point(self, line_start: QPointF, line_end: QPointF,
                                 obj: GeometricObject) -> Optional[QPointF]:
        """Находит точку на объекте, которая является основанием перпендикуляра от линии"""
        # Направление линии
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()
        line_length = math.sqrt(dx*dx + dy*dy)
        if line_length < 1e-6:
            return None
        
        # Нормализуем направление
        dx /= line_length
        dy /= line_length
        
        if isinstance(obj, LineSegment):
            return self._perpendicular_to_line(line_start, line_end, obj.start_point, obj.end_point)
        elif isinstance(obj, Circle):
            return self._perpendicular_to_circle(line_start, line_end, obj.center, obj.radius)
        elif isinstance(obj, Arc):
            return self._perpendicular_to_arc(line_start, line_end, obj)
        elif isinstance(obj, Ellipse):
            return self._perpendicular_to_ellipse(line_start, line_end, obj)
        
        return None
    
    def _find_tangent_points(self, point: QPointF, obj: GeometricObject) -> List[QPointF]:
        """Находит точки касания от точки к объекту"""
        tangents = []
        
        if isinstance(obj, Circle):
            tangents.extend(self._tangent_to_circle(point, obj.center, obj.radius))
        elif isinstance(obj, Arc):
            tangents.extend(self._tangent_to_arc(point, obj))
        elif isinstance(obj, Ellipse):
            tangents.extend(self._tangent_to_ellipse(point, obj))
        
        return tangents
    
    def find_nearest_snap(self, point: QPointF, snap_points: List[SnapPoint], 
                          scale_factor: float = 1.0) -> Optional[Tuple[QPointF, SnapPoint]]:
        """
        Находит ближайшую точку привязки
        Args:
            point: Точка для поиска привязки
            snap_points: Список точек привязки
            scale_factor: Масштаб для учета в tolerance
        Returns:
            Кортеж (привязанная точка, SnapPoint) или None, если привязка не найдена
        """
        if not self.enabled or not snap_points:
            return None
        
        # Учитываем масштаб при вычислении tolerance
        # При увеличении масштаба (scale_factor > 1) tolerance в мировых координатах должен уменьшаться
        # Но мы работаем в мировых координатах, поэтому нужно преобразовать tolerance из пикселей в мировые координаты
        scaled_tolerance = self.tolerance / scale_factor if scale_factor > 0 else self.tolerance
        # Убеждаемся, что tolerance не слишком мал, но и не слишком велик
        # Минимальный tolerance в мировых координатах
        min_tolerance = 0.5
        max_tolerance = 100.0
        if scaled_tolerance < min_tolerance:
            scaled_tolerance = min_tolerance
        elif scaled_tolerance > max_tolerance:
            scaled_tolerance = max_tolerance
        
        # Подсчитываем точки пересечения
        intersection_count = sum(1 for sp in snap_points if sp.snap_type == SnapType.INTERSECTION)
        
        nearest_snap = None
        min_distance = float('inf')
        
        for snap_point in snap_points:
            distance = snap_point.distance_to(point)
            if distance < scaled_tolerance and distance < min_distance:
                min_distance = distance
                nearest_snap = snap_point
        
        if nearest_snap:
            return (nearest_snap.point, nearest_snap)
        
        return None
    
    # ========== Геометрические вычисления для динамических привязок ==========
    
    def _line_line_intersection(self, p1: QPointF, p2: QPointF, 
                                p3: QPointF, p4: QPointF) -> Optional[QPointF]:
        """Находит точку пересечения двух отрезков"""
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        x3, y3 = p3.x(), p3.y()
        x4, y4 = p4.x(), p4.y()
        
        # Направляющие векторы
        dx1 = x2 - x1
        dy1 = y2 - y1
        dx2 = x4 - x3
        dy2 = y4 - y3
        
        # Знаменатель для параметрических уравнений
        denom = dx1 * dy2 - dy1 * dx2
        if abs(denom) < 1e-10:
            return None  # Параллельные линии
        
        # Параметры для обоих отрезков
        # t для первого отрезка: P = P1 + t * (P2 - P1)
        # u для второго отрезка: P = P3 + u * (P4 - P3)
        t = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / denom
        u = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / denom
        
        # Проверяем, что точка находится на обоих отрезках
        if 0 <= t <= 1 and 0 <= u <= 1:
            x = x1 + t * dx1
            y = y1 + t * dy1
            return QPointF(x, y)
        
        return None
    
    def _line_circle_intersection(self, line_start: QPointF, line_end: QPointF,
                                   center: QPointF, radius: float) -> List[QPointF]:
        """Находит точки пересечения линии с окружностью"""
        intersections = []
        
        # Переводим в систему координат с центром окружности в начале
        x1 = line_start.x() - center.x()
        y1 = line_start.y() - center.y()
        x2 = line_end.x() - center.x()
        y2 = line_end.y() - center.y()
        
        dx = x2 - x1
        dy = y2 - y1
        dr_sq = dx*dx + dy*dy
        
        if dr_sq < 1e-10:
            return intersections
        
        # Определитель для формулы пересечения линии и окружности
        D = x1 * y2 - x2 * y1
        discriminant = radius*radius * dr_sq - D*D
        
        if discriminant < 0:
            return intersections
        
        sqrt_disc = math.sqrt(discriminant)
        
        # Две точки пересечения (используем правильную формулу)
        for sign in [-1, 1]:
            # Формула для точки пересечения линии и окружности
            x = (D * dy + sign * (1 if dy >= 0 else -1) * dx * sqrt_disc) / dr_sq
            y = (-D * dx + sign * abs(dy) * sqrt_disc) / dr_sq
            
            # Вычисляем параметр t для точки на линии: P = P1 + t * (P2 - P1)
            # Используем более точный метод
            if abs(dr_sq) > 1e-10:
                # Проекция точки на направление линии
                t = ((x - x1) * dx + (y - y1) * dy) / dr_sq
            else:
                t = 0
            
            # Проверяем, что точка на отрезке
            if 0 <= t <= 1:
                world_x = x + center.x()
                world_y = y + center.y()
                intersections.append(QPointF(world_x, world_y))
        
        return intersections
    
    def _line_arc_intersection(self, line_start: QPointF, line_end: QPointF,
                               arc: Arc) -> List[QPointF]:
        """Находит точки пересечения линии с дугой"""
        intersections = []
        
        # Сначала находим пересечения с полным эллипсом
        ellipse_intersections = self._line_ellipse_intersection(
            line_start, line_end, arc
        )
        
        # Фильтруем только те, что попадают в диапазон дуги
        for point in ellipse_intersections:
            if self._point_on_arc(point, arc):
                intersections.append(point)
        
        return intersections
    
    def _line_ellipse_intersection(self, line_start: QPointF, line_end: QPointF,
                                   ellipse) -> List[QPointF]:
        """Находит точки пересечения линии с эллипсом (или дугой)"""
        intersections = []
        
        # Переводим в локальную систему координат эллипса
        # Сначала переносим центр в начало
        x1 = line_start.x() - ellipse.center.x()
        y1 = line_start.y() - ellipse.center.y()
        x2 = line_end.x() - ellipse.center.x()
        y2 = line_end.y() - ellipse.center.y()
        
        # Применяем обратный поворот
        if abs(ellipse.rotation_angle) > 1e-6:
            cos_r = math.cos(-ellipse.rotation_angle)
            sin_r = math.sin(-ellipse.rotation_angle)
            x1_rot = x1 * cos_r - y1 * sin_r
            y1_rot = x1 * sin_r + y1 * cos_r
            x2_rot = x2 * cos_r - y2 * sin_r
            y2_rot = x2 * sin_r + y2 * cos_r
        else:
            x1_rot, y1_rot = x1, y1
            x2_rot, y2_rot = x2, y2
        
        # Нормализуем эллипс к единичной окружности
        if ellipse.radius_x < 1e-6 or ellipse.radius_y < 1e-6:
            return intersections
        
        x1_norm = x1_rot / ellipse.radius_x
        y1_norm = y1_rot / ellipse.radius_y
        x2_norm = x2_rot / ellipse.radius_x
        y2_norm = y2_rot / ellipse.radius_y
        
        # Находим пересечение с единичной окружностью
        dx_norm = x2_norm - x1_norm
        dy_norm = y2_norm - y1_norm
        dr_sq_norm = dx_norm*dx_norm + dy_norm*dy_norm
        
        if dr_sq_norm < 1e-10:
            return intersections
        
        D = x1_norm * y2_norm - x2_norm * y1_norm
        discriminant = dr_sq_norm - D*D
        
        if discriminant < 0:
            return intersections
        
        sqrt_disc = math.sqrt(discriminant)
        
        # Две точки пересечения
        # Используем правильную формулу для пересечения линии с единичной окружностью
        # Линия: (x, y) = (x1_norm, y1_norm) + t * (dx_norm, dy_norm)
        # Окружность: x^2 + y^2 = 1
        # Подставляем: (x1_norm + t*dx_norm)^2 + (y1_norm + t*dy_norm)^2 = 1
        # t^2*dr_sq_norm + 2*t*(x1_norm*dx_norm + y1_norm*dy_norm) + (x1_norm^2 + y1_norm^2 - 1) = 0
        
        dot_product = x1_norm * dx_norm + y1_norm * dy_norm
        r1_sq = x1_norm * x1_norm + y1_norm * y1_norm
        c = r1_sq - 1.0
        
        # Квадратное уравнение: a*t^2 + b*t + c = 0
        # где a = dr_sq_norm, b = 2*dot_product, c = r1_sq - 1
        b_coeff = 2.0 * dot_product
        disc = b_coeff * b_coeff - 4.0 * dr_sq_norm * c
        
        if disc < 0:
            return intersections
        
        sqrt_disc_t = math.sqrt(disc)
        t1 = (-b_coeff + sqrt_disc_t) / (2.0 * dr_sq_norm)
        t2 = (-b_coeff - sqrt_disc_t) / (2.0 * dr_sq_norm)
        
        # Используем оба решения
        # Преобразуем t_norm в параметр t для исходной линии
        # В нормализованном пространстве: точка = (x1_norm, y1_norm) + t_norm * (dx_norm, dy_norm)
        # В локальных координатах эллипса: точка = (x1_rot, y1_rot) + t_norm * (dx_rot, dy_rot)
        # где dx_rot = dx_norm * radius_x, dy_rot = dy_norm * radius_y
        # Но нам нужно найти параметр t для исходной линии в мировых координатах
        
        # Вычисляем направление линии в локальных координатах эллипса (до нормализации)
        dx_rot = (x2_rot - x1_rot)
        dy_rot = (y2_rot - y1_rot)
        dr_rot_sq = dx_rot * dx_rot + dy_rot * dy_rot
        
        for t_norm in [t1, t2]:
            # Точка в нормализованном пространстве
            x_norm = x1_norm + t_norm * dx_norm
            y_norm = y1_norm + t_norm * dy_norm
            
            # Проверяем, что точка на единичной окружности (с небольшой погрешностью)
            # Увеличиваем допустимую погрешность из-за численных ошибок
            dist_sq = x_norm * x_norm + y_norm * y_norm
            if abs(dist_sq - 1.0) > 0.1:
                continue
            
            # Обратное преобразование к локальным координатам
            x_local = x_norm * ellipse.radius_x
            y_local = y_norm * ellipse.radius_y
            
            # Применяем поворот обратно
            if abs(ellipse.rotation_angle) > 1e-6:
                cos_r = math.cos(ellipse.rotation_angle)
                sin_r = math.sin(ellipse.rotation_angle)
                x_world = x_local * cos_r - y_local * sin_r
                y_world = x_local * sin_r + y_local * cos_r
            else:
                x_world, y_world = x_local, y_local
            
            # Переводим в мировые координаты
            x = x_world + ellipse.center.x()
            y = y_world + ellipse.center.y()
            
            # Проверяем, что точка на отрезке
            # Вычисляем параметр t для точки на исходной линии: P = P1 + t * (P2 - P1)
            dx_line = line_end.x() - line_start.x()
            dy_line = line_end.y() - line_start.y()
            line_len_sq = dx_line*dx_line + dy_line*dy_line
            
            if line_len_sq > 1e-10:
                t = ((x - line_start.x()) * dx_line + (y - line_start.y()) * dy_line) / line_len_sq
                # Проверяем, что точка находится на отрезке (с небольшой погрешностью)
                if -1e-6 <= t <= 1.0 + 1e-6:
                    # Убеждаемся, что точка действительно на эллипсе (проверка расстояния)
                    # Переводим точку обратно в локальные координаты для проверки
                    check_x = x - ellipse.center.x()
                    check_y = y - ellipse.center.y()
                    
                    if abs(ellipse.rotation_angle) > 1e-6:
                        cos_r = math.cos(-ellipse.rotation_angle)
                        sin_r = math.sin(-ellipse.rotation_angle)
                        check_x_rot = check_x * cos_r - check_y * sin_r
                        check_y_rot = check_x * sin_r + check_y * cos_r
                    else:
                        check_x_rot, check_y_rot = check_x, check_y
                    
                    # Проверяем уравнение эллипса: (x/a)^2 + (y/b)^2 = 1
                    ellipse_eq = (check_x_rot / ellipse.radius_x)**2 + (check_y_rot / ellipse.radius_y)**2
                    if abs(ellipse_eq - 1.0) < 0.1:  # Увеличиваем допустимую погрешность
                        intersections.append(QPointF(x, y))
        
        return intersections
    
    def _point_on_arc(self, point: QPointF, arc: Arc) -> bool:
        """Проверяет, находится ли точка на дуге (в её угловом диапазоне)"""
        # Переводим точку в локальные координаты
        x = point.x() - arc.center.x()
        y = point.y() - arc.center.y()
        
        # Применяем обратный поворот
        if abs(arc.rotation_angle) > 1e-6:
            cos_r = math.cos(-arc.rotation_angle)
            sin_r = math.sin(-arc.rotation_angle)
            x_rot = x * cos_r - y * sin_r
            y_rot = x * sin_r + y * cos_r
        else:
            x_rot, y_rot = x, y
        
        # Вычисляем параметрический угол
        if abs(x_rot) < 1e-6 and abs(y_rot) < 1e-6:
            return False
        
        # Нормализуем к единичному эллипсу для вычисления угла
        if arc.radius_x < 1e-6 or arc.radius_y < 1e-6:
            return False
        
        x_norm = x_rot / arc.radius_x
        y_norm = y_rot / arc.radius_y
        
        # Проверяем, что точка находится на эллипсе (с небольшой погрешностью)
        dist_sq = x_norm * x_norm + y_norm * y_norm
        
        # Нормализуем углы дуги
        # Сохраняем оригинальные значения для проверки
        orig_start = arc.start_angle
        orig_end = arc.end_angle
        
        # Определяем направление дуги: вверх или вниз
        # Дуга вверх: start_angle=180, end_angle=360
        # Дуга вниз: start_angle=180, end_angle=0
        start_angle_norm = orig_start % 360
        end_angle_norm = orig_end % 360
        
        # Определяем, является ли дуга дугой вниз
        # Дуга вниз: start_angle=180, end_angle=0 (не 360!)
        # Дуга вверх: start_angle=180, end_angle=360
        is_arc_down = False
        if abs(orig_start - 180.0) < 1.0:  # start_angle точно 180
            if abs(orig_end - 0.0) < 1.0:  # end_angle точно 0 (не 360!)
                is_arc_down = True
            # Если end_angle=360, это дуга вверх, оставляем is_arc_down=False
        elif start_angle_norm > end_angle_norm and (start_angle_norm - end_angle_norm) > 180:
            # Дуга идет от большего угла к меньшему через 0°, вероятно вниз
            # Но только если end_angle не равен 360 (дуга вверх имеет end_angle=360)
            if abs(orig_end - 360.0) > 1.0 and abs(orig_end - 0.0) < 1.0:  # end_angle точно 0, не 360
                is_arc_down = True
        
        # Вычисляем параметрический угол эллипса
        # Для эллипса: x = a*cos(t), y = b*sin(t)
        # Для дуги вверх (180-360): нужно инвертировать Y для системы с Y вниз
        # Для дуги вниз (180-0): используем обычную формулу
        if is_arc_down:
            # Дуга вниз: используем обычную формулу
            angle_rad = math.atan2(y_norm, x_norm)
        else:
            # Дуга вверх: инвертируем Y для системы с Y вниз
            angle_rad = math.atan2(-y_norm, x_norm)
        
        angle_deg = math.degrees(angle_rad)
        
        # Нормализуем угол в диапазон [0, 360)
        if angle_deg < 0:
            angle_deg += 360
        
        # Нормализуем углы в диапазон [0, 360)
        start_angle = orig_start % 360
        end_angle = orig_end % 360
        
        # Если end_angle был 360 или близок к 360, устанавливаем его в 360
        if abs(orig_end - 360.0) < 1e-6:
            end_angle = 360.0
        elif end_angle == 0 and orig_end > 180:
            end_angle = 360.0
        
        # Проверяем, попадает ли угол в диапазон
        if start_angle < end_angle:
            # Обычный случай: диапазон не пересекает 0°
            return start_angle <= angle_deg <= end_angle
        elif start_angle > end_angle:
            # Диапазон пересекает 0° (например, от 270° до 90°)
            return angle_deg >= start_angle or angle_deg <= end_angle
        else:
            # start_angle == end_angle (полный круг или точка)
            if abs(end_angle - 360.0) < 1e-6 and abs(start_angle - 0.0) < 1e-6:
                # Полный круг
                return True
            else:
                # Точка (нулевая дуга)
                return abs(angle_deg - start_angle) < 1e-6
    
    def _perpendicular_to_line(self, line_start: QPointF, line_end: QPointF,
                               obj_start: QPointF, obj_end: QPointF) -> Optional[QPointF]:
        """Находит основание перпендикуляра от линии к отрезку"""
        # Направление текущей линии
        line_dx = line_end.x() - line_start.x()
        line_dy = line_end.y() - line_start.y()
        line_len_sq = line_dx*line_dx + line_dy*line_dy
        if line_len_sq < 1e-10:
            return None
        
        # Направление объекта
        obj_dx = obj_end.x() - obj_start.x()
        obj_dy = obj_end.y() - obj_start.y()
        obj_len_sq = obj_dx*obj_dx + obj_dy*obj_dy
        if obj_len_sq < 1e-10:
            return None
        
        # Параметрическое уравнение объекта: obj_start + t * (obj_end - obj_start)
        # Ищем точку на объекте, такую что линия от этой точки перпендикулярна текущей линии
        # Условие перпендикулярности: (point - line_point) · line_dir = 0
        
        # Для каждой точки на объекте находим ближайшую точку на текущей линии
        # и проверяем перпендикулярность
        
        # Пробуем несколько точек на объекте и находим ту, которая дает перпендикуляр
        best_point = None
        best_angle_diff = float('inf')
        
        # Проверяем конечные точки объекта
        for test_point in [obj_start, obj_end]:
            # Вектор от точки объекта к ближайшей точке на линии
            # Ближайшая точка на линии: проекция test_point на линию
            t_line = ((test_point.x() - line_start.x()) * line_dx + 
                     (test_point.y() - line_start.y()) * line_dy) / line_len_sq
            t_line = max(0, min(1, t_line))  # Ограничиваем отрезком
            
            closest_on_line = QPointF(
                line_start.x() + t_line * line_dx,
                line_start.y() + t_line * line_dy
            )
            
            # Вектор от closest_on_line к test_point
            perp_dx = test_point.x() - closest_on_line.x()
            perp_dy = test_point.y() - closest_on_line.y()
            
            # Проверяем перпендикулярность (скалярное произведение должно быть близко к 0)
            dot_product = perp_dx * line_dx + perp_dy * line_dy
            angle_diff = abs(dot_product)
            
            if angle_diff < best_angle_diff:
                best_angle_diff = angle_diff
                best_point = test_point
        
        # Также проверяем точку на объекте, которая точно перпендикулярна
        # Решаем систему: точка на объекте + перпендикулярность
        # (obj_start + t*obj_dir - line_start - s*line_dir) · line_dir = 0
        
        # Упрощенный подход: находим точку на объекте, проекция которой на линию
        # дает минимальное расстояние
        
        # Пробуем точку на объекте, которая ближе всего к перпендикуляру
        # Используем аналитическое решение
        denom = line_dx * obj_dy - line_dy * obj_dx
        if abs(denom) > 1e-10:
            # Находим параметр t для объекта
            t = ((line_start.x() - obj_start.x()) * line_dy - 
                 (line_start.y() - obj_start.y()) * line_dx) / denom
            
            # Ограничиваем t отрезком [0, 1]
            t = max(0, min(1, t))
            
            perp_point = QPointF(
                obj_start.x() + t * obj_dx,
                obj_start.y() + t * obj_dy
            )
            
            # Проверяем, что это действительно перпендикуляр
            # Находим ближайшую точку на линии
            t_line = ((perp_point.x() - line_start.x()) * line_dx + 
                     (perp_point.y() - line_start.y()) * line_dy) / line_len_sq
            t_line = max(0, min(1, t_line))
            
            closest_on_line = QPointF(
                line_start.x() + t_line * line_dx,
                line_start.y() + t_line * line_dy
            )
            
            # Вектор перпендикуляра
            perp_vec_x = perp_point.x() - closest_on_line.x()
            perp_vec_y = perp_point.y() - closest_on_line.y()
            
            # Проверяем перпендикулярность
            dot = perp_vec_x * line_dx + perp_vec_y * line_dy
            if abs(dot) < 0.1:  # Допустимая погрешность
                return perp_point
        
        # Если аналитическое решение не сработало, возвращаем лучшую найденную точку
        if best_point and best_angle_diff < 0.1:
            return best_point
        
        return None
    
    def _perpendicular_to_circle(self, line_start: QPointF, line_end: QPointF,
                                 center: QPointF, radius: float) -> Optional[QPointF]:
        """Находит точку на окружности, которая является основанием перпендикуляра от линии"""
        # Направление линии
        line_dx = line_end.x() - line_start.x()
        line_dy = line_end.y() - line_start.y()
        line_len_sq = line_dx*line_dx + line_dy*line_dy
        
        if line_len_sq < 1e-10:
            return None
        
        # Находим ближайшую точку на линии к центру окружности
        t = ((center.x() - line_start.x()) * line_dx + 
             (center.y() - line_start.y()) * line_dy) / line_len_sq
        t = max(0, min(1, t))  # Ограничиваем отрезком
        
        closest_on_line = QPointF(
            line_start.x() + t * line_dx,
            line_start.y() + t * line_dy
        )
        
        # Вектор от центра к ближайшей точке на линии
        dx = closest_on_line.x() - center.x()
        dy = closest_on_line.y() - center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist < 1e-10:
            # Центр на линии - любая точка на окружности перпендикулярна
            # Возвращаем точку в направлении перпендикуляра к линии
            perp_dx = -line_dy
            perp_dy = line_dx
            perp_len = math.sqrt(perp_dx*perp_dx + perp_dy*perp_dy)
            if perp_len > 1e-10:
                perp_point = QPointF(
                    center.x() + radius * perp_dx / perp_len,
                    center.y() + radius * perp_dy / perp_len
                )
                return perp_point
            return None
        
        # Нормализуем и умножаем на радиус
        perp_point = QPointF(
            center.x() + radius * dx / dist,
            center.y() + radius * dy / dist
        )
        
        return perp_point
    
    def _perpendicular_to_arc(self, line_start: QPointF, line_end: QPointF,
                              arc: Arc) -> Optional[QPointF]:
        """Находит точку на дуге, которая является основанием перпендикуляра"""
        # Используем метод для эллипса
        return self._perpendicular_to_ellipse(line_start, line_end, arc)
    
    def _perpendicular_to_ellipse(self, line_start: QPointF, line_end: QPointF,
                                  ellipse) -> Optional[QPointF]:
        """Находит точку на эллипсе, которая является основанием перпендикуляра от линии"""
        # Направление линии
        line_dx = line_end.x() - line_start.x()
        line_dy = line_end.y() - line_start.y()
        line_len_sq = line_dx*line_dx + line_dy*line_dy
        
        if line_len_sq < 1e-10:
            return None
        
        # Находим ближайшую точку на линии к центру эллипса
        t_line = ((ellipse.center.x() - line_start.x()) * line_dx + 
                  (ellipse.center.y() - line_start.y()) * line_dy) / line_len_sq
        t_line = max(0, min(1, t_line))  # Ограничиваем отрезком
        
        closest_on_line = QPointF(
            line_start.x() + t_line * line_dx,
            line_start.y() + t_line * line_dy
        )
        
        # Переводим closest_on_line в локальные координаты эллипса
        x = closest_on_line.x() - ellipse.center.x()
        y = closest_on_line.y() - ellipse.center.y()
        
        # Применяем обратный поворот
        if abs(ellipse.rotation_angle) > 1e-6:
            cos_r = math.cos(-ellipse.rotation_angle)
            sin_r = math.sin(-ellipse.rotation_angle)
            x_rot = x * cos_r - y * sin_r
            y_rot = x * sin_r + y * cos_r
        else:
            x_rot, y_rot = x, y
        
        # Нормализуем к единичному эллипсу
        if ellipse.radius_x < 1e-6 or ellipse.radius_y < 1e-6:
            return None
        
        x_norm = x_rot / ellipse.radius_x
        y_norm = y_rot / ellipse.radius_y
        
        # Находим ближайшую точку на единичной окружности
        dist = math.sqrt(x_norm*x_norm + y_norm*y_norm)
        if dist < 1e-10:
            return None
        
        x_unit = x_norm / dist
        y_unit = y_norm / dist
        
        # Обратное преобразование
        x_local = x_unit * ellipse.radius_x
        y_local = y_unit * ellipse.radius_y
        
        # Применяем поворот
        if abs(ellipse.rotation_angle) > 1e-6:
            cos_r = math.cos(ellipse.rotation_angle)
            sin_r = math.sin(ellipse.rotation_angle)
            x_world = x_local * cos_r - y_local * sin_r
            y_world = x_local * sin_r + y_local * cos_r
        else:
            x_world, y_world = x_local, y_local
        
        perp_point = QPointF(
            ellipse.center.x() + x_world,
            ellipse.center.y() + y_world
        )
        
        # Для дуги проверяем, что точка в диапазоне
        if isinstance(ellipse, Arc):
            if not self._point_on_arc(perp_point, ellipse):
                return None
        
        return perp_point
    
    def _tangent_to_circle(self, point: QPointF, center: QPointF, 
                          radius: float) -> List[QPointF]:
        """Находит точки касания от точки к окружности"""
        tangents = []
        
        # Расстояние от точки до центра
        dx = center.x() - point.x()
        dy = center.y() - point.y()
        dist_sq = dx*dx + dy*dy
        
        if dist_sq < radius*radius - 1e-6:
            return tangents  # Точка внутри окружности
        
        if dist_sq < 1e-10:
            return tangents  # Точка совпадает с центром
        
        # Расстояние от точки до центра
        dist = math.sqrt(dist_sq)
        
        # Угол от точки к центру
        angle_to_center = math.atan2(dy, dx)
        
        # Угол между линией центр-точка и касательной
        if dist < radius + 1e-6:
            # Точка на окружности - одна касательная
            tangents.append(QPointF(point.x(), point.y()))
        else:
            # Две касательные
            sin_alpha = radius / dist
            alpha = math.asin(sin_alpha)
            
            for sign in [-1, 1]:
                angle = angle_to_center + sign * alpha
                tangent_point = QPointF(
                    center.x() + radius * math.cos(angle),
                    center.y() + radius * math.sin(angle)
                )
                tangents.append(tangent_point)
        
        return tangents
    
    def _tangent_to_arc(self, point: QPointF, arc: Arc) -> List[QPointF]:
        """Находит точки касания от точки к дуге"""
        tangents = []
        
        # Используем метод для эллипса, затем фильтруем по диапазону дуги
        ellipse_tangents = self._tangent_to_ellipse(point, arc)
        
        for tangent in ellipse_tangents:
            if self._point_on_arc(tangent, arc):
                tangents.append(tangent)
        
        return tangents
    
    def _tangent_to_ellipse(self, point: QPointF, ellipse) -> List[QPointF]:
        """Находит точки касания от точки к эллипсу"""
        tangents = []
        
        # Переводим точку в локальные координаты
        x = point.x() - ellipse.center.x()
        y = point.y() - ellipse.center.y()
        
        # Применяем обратный поворот
        if abs(ellipse.rotation_angle) > 1e-6:
            cos_r = math.cos(-ellipse.rotation_angle)
            sin_r = math.sin(-ellipse.rotation_angle)
            x_rot = x * cos_r - y * sin_r
            y_rot = x * sin_r + y * cos_r
        else:
            x_rot, y_rot = x, y
        
        # Нормализуем к единичной окружности
        if ellipse.radius_x < 1e-6 or ellipse.radius_y < 1e-6:
            return tangents
        
        x_norm = x_rot / ellipse.radius_x
        y_norm = y_rot / ellipse.radius_y
        
        # Находим касательные к единичной окружности
        dist_sq = x_norm*x_norm + y_norm*y_norm
        
        if dist_sq < 1.0 - 1e-6:
            return tangents  # Точка внутри эллипса
        
        if dist_sq < 1e-10:
            return tangents  # Точка в центре
        
        # Для эллипса используем приближенный метод
        # Находим ближайшую точку на эллипсе
        dist = math.sqrt(dist_sq)
        if dist < 1.0 + 1e-6:
            # Точка на эллипсе - одна касательная
            x_unit = x_norm / dist
            y_unit = y_norm / dist
        else:
            # Две касательные (упрощенный метод)
            # Используем итеративный поиск или аналитическое решение
            # Для простоты используем метод ближайшей точки
            x_unit = x_norm / dist
            y_unit = y_norm / dist
        
        # Обратное преобразование
        x_local = x_unit * ellipse.radius_x
        y_local = y_unit * ellipse.radius_y
        
        # Применяем поворот
        if abs(ellipse.rotation_angle) > 1e-6:
            cos_r = math.cos(ellipse.rotation_angle)
            sin_r = math.sin(ellipse.rotation_angle)
            x_world = x_local * cos_r - y_local * sin_r
            y_world = x_local * sin_r + y_local * cos_r
        else:
            x_world, y_world = x_local, y_local
        
        tangent_point = QPointF(
            ellipse.center.x() + x_world,
            ellipse.center.y() + y_world
        )
        tangents.append(tangent_point)
        
        return tangents

