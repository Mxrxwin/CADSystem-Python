"""
Рефакторенная версия виджета системы координат
Использует разделение ответственностей согласно ООП
"""
import math
from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtCore import Qt, QPointF, QPoint, Signal, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QTransform, QKeyEvent

from core.viewport import Viewport
from core.scene import Scene
from core.selection import SelectionManager
from core.renderer import SceneRenderer
from core.snapping import SnapManager, SnapPoint
from widgets.line_segment import LineSegment
from widgets.line_style import LineStyleManager
from widgets.primitives import Arc, Ellipse, Polygon, Spline


class CoordinateSystemWidget(QWidget):
    """Виджет для отображения и взаимодействия с системой координат"""
    
    view_changed = Signal()  # сигнал при изменении вида
    context_menu_requested = Signal(QPoint)  # сигнал для запроса контекстного меню
    selection_changed = Signal(list)  # сигнал при изменении выделения
    line_finished = Signal()  # сигнал при завершении рисования отрезка
    rectangle_drawing_started = Signal(str)  # сигнал при начале рисования прямоугольника (передает метод)
    
    def __init__(self, style_manager=None):
        super().__init__()
        
        # Создаем компоненты
        self.viewport = Viewport(self.width(), self.height())
        self.scene = Scene()
        self.selection_manager = SelectionManager()
        self.renderer = SceneRenderer(self.viewport, self.scene, self.selection_manager)
        self.snap_manager = SnapManager(tolerance=15.0)  # Увеличиваем tolerance для лучшей видимости привязок
        
        # Менеджер стилей
        self.style_manager = style_manager
        
        # Текущая точка привязки для визуализации
        self.current_snap_point = None
        
        # Параметры навигации
        self.pan_mode = False
        self.last_mouse_pos = None
        
        # Параметры выделения рамкой
        self.is_selecting = False
        self.selection_start = None
        self.selection_end = None
        self.right_button_press_pos = None
        self.right_button_press_time = None
        self.right_button_click_count = 0
        self.right_button_click_timer = None
        self.last_left_click_time = 0
        self.last_left_click_pos = None
        self.last_left_click_time = 0
        self.last_left_click_pos = None
        
        # Координаты курсора
        self.cursor_world_coords = None
        
        # Точки ввода для визуализации (для окружности, дуги, эллипса, прямоугольника)
        self.input_points = []  # Список точек для отображения
        
        # Настройки отрисовки
        self.line_color = QColor(0, 0, 0)
        self.line_width = 2
        
        # Тип создаваемого примитива
        self.primitive_type = 'line'  # 'line', 'circle', 'arc', 'rectangle', 'ellipse', 'polygon', 'spline'
        # Метод создания окружности
        self.circle_creation_method = 'center_radius'  # 'center_radius', 'center_diameter', 'two_points', 'three_points'
        # Метод создания дуги
        self.arc_creation_method = 'three_points'  # 'three_points', 'center_angles'
        # Метод создания прямоугольника
        self.rectangle_creation_method = 'two_points'  # 'two_points', 'point_size', 'center_size', 'with_fillets'
        # Метод создания многоугольника
        self.polygon_creation_method = 'center_radius_vertices'  # 'center_radius_vertices'
        self.polygon_num_vertices = 3
        
        # Режим редактирования (перемещение точек)
        self.editing_mode = False
        self.edit_dialog = None  # Ссылка на окно редактирования
        self.dragging_point = None  # 'start' или 'end' - какая точка перемещается
        self.drag_start_pos = None  # Позиция начала перетаскивания
        
        # Подключаем сигналы
        self.selection_manager.selection_changed.connect(self._on_selection_changed)
        
        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setFocusPolicy(Qt.StrongFocus)  # Для получения событий клавиатуры
    
    def set_editing_mode(self, enabled, edit_dialog=None):
        """Устанавливает режим редактирования (перемещение точек)"""
        self.editing_mode = enabled
        self.edit_dialog = edit_dialog
        if not enabled:
            self.dragging_point = None
            self.drag_start_pos = None
        self.update()
    
    def _on_selection_changed(self, selected_objects):
        """Обработчик изменения выделения"""
        self.selection_changed.emit(selected_objects)
        self.update()
    
    def resizeEvent(self, event):
        """Обработчик изменения размера виджета"""
        super().resizeEvent(event)
        self.viewport.set_size(self.width(), self.height())
        self.update()
    
    def paintEvent(self, event):
        """Отрисовка виджета"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Сначала рисуем сцену через renderer
        self.renderer.draw(painter)
        
        # Затем рисуем точки ввода (поверх сцены)
        if self.input_points:
            self._draw_input_points(painter)
        
        # Рисуем точку привязки (поверх всего)
        if self.current_snap_point:
            self._draw_snap_point(painter)
        
        # Рисуем точки редактирования (в режиме редактирования)
        if self.editing_mode:
            self._draw_editing_points(painter)
        
        # В конце рисуем рамку выделения (в экранных координатах)
        if self.is_selecting and self.selection_start and self.selection_end:
            self._draw_selection_rect(painter)
    
    def _draw_selection_rect(self, painter):
        """Рисует рамку выделения"""
        if not self.selection_start or not self.selection_end:
            return
        
        # Рисуем рамку в экранных координатах (без трансформации)
        painter.save()  # Сохраняем текущее состояние
        painter.resetTransform()  # Сбрасываем трансформацию для отрисовки в экранных координатах
        
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPen, QColor
        from PySide6.QtCore import Qt
        
        # Создаем прямоугольник из экранных координат напрямую
        screen_rect = QRectF(
            min(self.selection_start.x(), self.selection_end.x()),
            min(self.selection_start.y(), self.selection_end.y()),
            abs(self.selection_end.x() - self.selection_start.x()),
            abs(self.selection_end.y() - self.selection_start.y())
        )
        
        # Рисуем рамку
        selection_pen = QPen(QColor(0, 100, 255), 1, Qt.DashLine)
        painter.setPen(selection_pen)
        painter.setBrush(QColor(0, 100, 255, 30))  # Полупрозрачная заливка
        painter.drawRect(screen_rect)
        
        painter.restore()  # Восстанавливаем состояние
    
    def _apply_snapping(self, point: QPointF, exclude_object=None) -> QPointF:
        """
        Применяет привязку к точке
        Args:
            point: Исходная точка
            exclude_object: Объект, который нужно исключить из привязки (например, редактируемый объект)
        Returns:
            Привязанная точка (или исходная, если привязка не найдена)
        """
        if not self.snap_manager.enabled:
            self.current_snap_point = None
            return point
        
        # Получаем все объекты, исключая текущий рисуемый и редактируемый
        objects = self.scene.get_objects()
        current_obj = self.scene.get_current_object()
        
        # Исключаем объект для привязки (приоритет у exclude_object)
        obj_to_exclude = exclude_object if exclude_object is not None else current_obj
        
        # Получаем статические точки привязки
        snap_points = self.snap_manager.get_snap_points(objects, exclude_object=obj_to_exclude)
        
        # Получаем начальную точку для динамических привязок
        start_point = None
        if self.scene.is_drawing():
            drawing_type = getattr(self.scene, '_drawing_type', None)
            if drawing_type == 'line':
                current_line = self.scene.get_current_line()
                if current_line:
                    start_point = current_line.start_point
            elif drawing_type == 'arc':
                start_point = getattr(self.scene, '_arc_start_point', None)
        
        # Добавляем динамические точки привязки
        if start_point:
            dynamic_points = self.snap_manager.get_dynamic_snap_points(
                point, objects, exclude_object=obj_to_exclude, start_point=start_point
            )
            snap_points.extend(dynamic_points)
        
        # Находим ближайшую точку привязки
        scale_factor = self.viewport.get_scale()
        result = self.snap_manager.find_nearest_snap(point, snap_points, scale_factor)
        
        if result:
            snapped_point, snap_point = result
            self.current_snap_point = snap_point
            return snapped_point
        else:
            self.current_snap_point = None
            return point
    
    def _draw_input_points(self, painter):
        """Рисует точки ввода для визуализации"""
        if not self.input_points:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Применяем трансформацию viewport
        # После renderer.draw() трансформация может быть сброшена, поэтому применяем заново
        transform = self.viewport.get_total_transform()
        painter.setTransform(transform)
        
        # Цвет и стиль точек
        point_color = QColor(255, 100, 0)  # Оранжевый цвет для точек ввода
        point_pen = QPen(point_color, 1.5)
        painter.setPen(point_pen)
        painter.setBrush(QColor(255, 150, 50, 220))  # Полупрозрачная оранжевая заливка
        
        # Размер точки в мировых координатах
        scale_factor = self.viewport.get_scale()
        # Размер точки в мировых координатах (примерно 4 пикселя на экране)
        point_size = max(4.0 / scale_factor, 0.5)  # Минимальный размер 0.5 в мировых координатах
        
        for point in self.input_points:
            if point is None:
                continue
            # Рисуем точку в мировых координатах
            # Используем drawEllipse с центром в точке и радиусом point_size
            from PySide6.QtCore import QRectF
            rect = QRectF(
                point.x() - point_size,
                point.y() - point_size,
                point_size * 2,
                point_size * 2
            )
            painter.drawEllipse(rect)
        
        painter.restore()
    
    def _draw_editing_points(self, painter):
        """Рисует точки редактирования для выделенных объектов"""
        selected = self.selection_manager.get_selected_objects()
        if len(selected) != 1:
            return
        
        obj = selected[0]
        painter.save()
        painter.resetTransform()  # Сбрасываем трансформацию для рисования в экранных координатах
        
        # Радиус точки в экранных координатах
        point_radius = 8.0
        
        from widgets.primitives import Circle, Rectangle
        if isinstance(obj, LineSegment):
            # Рисуем точки для отрезка
            start_screen = self.viewport.world_to_screen(obj.start_point)
            end_screen = self.viewport.world_to_screen(obj.end_point)
            
            # Рисуем начальную точку (зеленая)
            painter.setPen(QPen(QColor(0, 200, 0), 2))
            painter.setBrush(QColor(0, 255, 0, 200))
            painter.drawEllipse(start_screen, point_radius, point_radius)
            
            # Рисуем конечную точку (красная)
            painter.setPen(QPen(QColor(200, 0, 0), 2))
            painter.setBrush(QColor(255, 0, 0, 200))
            painter.drawEllipse(end_screen, point_radius, point_radius)
            
            # Если точка перемещается, подсвечиваем её
            if self.dragging_point == 'start':
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.setBrush(QColor(0, 255, 0, 150))
                painter.drawEllipse(start_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'end':
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(QColor(255, 0, 0, 150))
                painter.drawEllipse(end_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Circle):
            # Рисуем центр окружности (синий)
            center_screen = self.viewport.world_to_screen(obj.center)
            painter.setPen(QPen(QColor(0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 255, 200))
            painter.drawEllipse(center_screen, point_radius, point_radius)
            
            # Рисуем крайнюю точку на окружности для изменения радиуса (оранжевая)
            # Точка находится справа от центра (0°)
            radius_point_world = QPointF(obj.center.x() + obj.radius, obj.center.y())
            radius_point_screen = self.viewport.world_to_screen(radius_point_world)
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(QColor(255, 165, 0, 200))
            painter.drawEllipse(radius_point_screen, point_radius, point_radius)
            
            # Если центр перемещается, подсвечиваем его
            if self.dragging_point == 'center':
                painter.setPen(QPen(QColor(0, 0, 255), 3))
                painter.setBrush(QColor(0, 0, 255, 150))
                painter.drawEllipse(center_screen, point_radius + 3, point_radius + 3)
            # Если крайняя точка перемещается, подсвечиваем её
            elif self.dragging_point == 'radius':
                painter.setPen(QPen(QColor(255, 165, 0), 3))
                painter.setBrush(QColor(255, 165, 0, 150))
                painter.drawEllipse(radius_point_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Rectangle):
            # Рисуем углы прямоугольника
            top_left_screen = self.viewport.world_to_screen(obj.top_left)
            bottom_right_screen = self.viewport.world_to_screen(obj.bottom_right)
            top_right_screen = self.viewport.world_to_screen(QPointF(obj.bottom_right.x(), obj.top_left.y()))
            bottom_left_screen = self.viewport.world_to_screen(QPointF(obj.top_left.x(), obj.bottom_right.y()))
            
            # Вычисляем центр прямоугольника
            bbox = obj.get_bounding_box()
            center_world = QPointF(bbox.center().x(), bbox.center().y())
            center_screen = self.viewport.world_to_screen(center_world)
            
            # Рисуем центр прямоугольника (фиолетовый)
            painter.setPen(QPen(QColor(128, 0, 128), 2))
            painter.setBrush(QColor(128, 0, 128, 200))
            painter.drawEllipse(center_screen, point_radius, point_radius)
            
            # Верхний левый угол (зеленый)
            painter.setPen(QPen(QColor(0, 200, 0), 2))
            painter.setBrush(QColor(0, 255, 0, 200))
            painter.drawEllipse(top_left_screen, point_radius, point_radius)
            
            # Верхний правый угол (красный)
            painter.setPen(QPen(QColor(200, 0, 0), 2))
            painter.setBrush(QColor(255, 0, 0, 200))
            painter.drawEllipse(top_right_screen, point_radius, point_radius)
            
            # Нижний правый угол (синий)
            painter.setPen(QPen(QColor(0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 255, 200))
            painter.drawEllipse(bottom_right_screen, point_radius, point_radius)
            
            # Нижний левый угол (желтый)
            painter.setPen(QPen(QColor(200, 200, 0), 2))
            painter.setBrush(QColor(255, 255, 0, 200))
            painter.drawEllipse(bottom_left_screen, point_radius, point_radius)
            
            # Подсвечиваем перемещаемую точку
            if self.dragging_point == 'center':
                painter.setPen(QPen(QColor(128, 0, 128), 3))
                painter.setBrush(QColor(128, 0, 128, 150))
                painter.drawEllipse(center_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'top_left':
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.setBrush(QColor(0, 255, 0, 150))
                painter.drawEllipse(top_left_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'top_right':
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(QColor(255, 0, 0, 150))
                painter.drawEllipse(top_right_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'bottom_right':
                painter.setPen(QPen(QColor(0, 0, 255), 3))
                painter.setBrush(QColor(0, 0, 255, 150))
                painter.drawEllipse(bottom_right_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'bottom_left':
                painter.setPen(QPen(QColor(255, 255, 0), 3))
                painter.setBrush(QColor(255, 255, 0, 150))
                painter.drawEllipse(bottom_left_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Arc):
            # Рисуем точки редактирования дуги
            center_screen = self.viewport.world_to_screen(obj.center)
            
            # Вычисляем средний угол для точки радиуса
            mid_angle = (obj.start_angle + obj.end_angle) / 2.0
            if obj.start_angle > obj.end_angle:
                # Если дуга пересекает 0°, вычисляем средний угол правильно
                span = (360 - obj.start_angle) + obj.end_angle
                mid_angle = (obj.start_angle + span / 2.0) % 360
            
            # Получаем точки на дуге для начального, конечного углов и середины
            start_point = obj.get_point_at_angle(obj.start_angle)
            end_point = obj.get_point_at_angle(obj.end_angle)
            mid_point = obj.get_point_at_angle(mid_angle)
            
            start_point_screen = self.viewport.world_to_screen(start_point)
            end_point_screen = self.viewport.world_to_screen(end_point)
            mid_point_screen = self.viewport.world_to_screen(mid_point)
            
            # Центр дуги (синий)
            painter.setPen(QPen(QColor(0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 255, 200))
            painter.drawEllipse(center_screen, point_radius, point_radius)
            
            # Начальная точка дуги (зеленая)
            painter.setPen(QPen(QColor(0, 200, 0), 2))
            painter.setBrush(QColor(0, 255, 0, 200))
            painter.drawEllipse(start_point_screen, point_radius, point_radius)
            
            # Конечная точка дуги (красная)
            painter.setPen(QPen(QColor(200, 0, 0), 2))
            painter.setBrush(QColor(255, 0, 0, 200))
            painter.drawEllipse(end_point_screen, point_radius, point_radius)
            
            # Точка для изменения радиуса (оранжевая) - в середине дуги
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(QColor(255, 165, 0, 200))
            painter.drawEllipse(mid_point_screen, point_radius, point_radius)
            
            # Подсвечиваем перемещаемую точку
            if self.dragging_point == 'center':
                painter.setPen(QPen(QColor(0, 0, 255), 3))
                painter.setBrush(QColor(0, 0, 255, 150))
                painter.drawEllipse(center_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'start_angle':
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.setBrush(QColor(0, 255, 0, 150))
                painter.drawEllipse(start_point_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'end_angle':
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(QColor(255, 0, 0, 150))
                painter.drawEllipse(end_point_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'radius':
                painter.setPen(QPen(QColor(255, 165, 0), 3))
                painter.setBrush(QColor(255, 165, 0, 150))
                painter.drawEllipse(mid_point_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Ellipse):
            # Рисуем точки редактирования эллипса
            center_screen = self.viewport.world_to_screen(obj.center)
            
            # Точки на осях для изменения радиусов
            # Горизонтальная ось (X) - справа от центра
            radius_x_point = QPointF(obj.center.x() + obj.radius_x, obj.center.y())
            # Вертикальная ось (Y) - сверху от центра
            radius_y_point = QPointF(obj.center.x(), obj.center.y() - obj.radius_y)
            
            radius_x_screen = self.viewport.world_to_screen(radius_x_point)
            radius_y_screen = self.viewport.world_to_screen(radius_y_point)
            
            # Центр эллипса (синий)
            painter.setPen(QPen(QColor(0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 255, 200))
            painter.drawEllipse(center_screen, point_radius, point_radius)
            
            # Точка на горизонтальной оси (оранжевая)
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(QColor(255, 165, 0, 200))
            painter.drawEllipse(radius_x_screen, point_radius, point_radius)
            
            # Точка на вертикальной оси (оранжевая)
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(QColor(255, 165, 0, 200))
            painter.drawEllipse(radius_y_screen, point_radius, point_radius)
            
            # Подсвечиваем перемещаемую точку
            if self.dragging_point == 'center':
                painter.setPen(QPen(QColor(0, 0, 255), 3))
                painter.setBrush(QColor(0, 0, 255, 150))
                painter.drawEllipse(center_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'radius_x':
                painter.setPen(QPen(QColor(255, 165, 0), 3))
                painter.setBrush(QColor(255, 165, 0, 150))
                painter.drawEllipse(radius_x_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'radius_y':
                painter.setPen(QPen(QColor(255, 165, 0), 3))
                painter.setBrush(QColor(255, 165, 0, 150))
                painter.drawEllipse(radius_y_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Polygon):
            # Рисуем точки редактирования многоугольника
            center_screen = self.viewport.world_to_screen(obj.center)
            
            # Точка для изменения радиуса - на окружности, справа от центра (0°)
            # Для описанного многоугольника нужно учесть тип построения
            if hasattr(obj, 'construction_type') and obj.construction_type == "circumscribed":
                # Для описанного: radius - это расстояние до сторон, нужно найти радиус описанной окружности
                if obj.num_vertices > 2:
                    effective_radius = obj.radius / math.cos(math.pi / obj.num_vertices)
                else:
                    effective_radius = obj.radius
            else:
                effective_radius = obj.radius
            
            radius_point = QPointF(obj.center.x() + effective_radius, obj.center.y())
            radius_point_screen = self.viewport.world_to_screen(radius_point)
            
            # Центр многоугольника (синий)
            painter.setPen(QPen(QColor(0, 0, 200), 2))
            painter.setBrush(QColor(0, 0, 255, 200))
            painter.drawEllipse(center_screen, point_radius, point_radius)
            
            # Точка для изменения радиуса (оранжевая)
            painter.setPen(QPen(QColor(255, 165, 0), 2))
            painter.setBrush(QColor(255, 165, 0, 200))
            painter.drawEllipse(radius_point_screen, point_radius, point_radius)
            
            # Подсвечиваем перемещаемую точку
            if self.dragging_point == 'center':
                painter.setPen(QPen(QColor(0, 0, 255), 3))
                painter.setBrush(QColor(0, 0, 255, 150))
                painter.drawEllipse(center_screen, point_radius + 3, point_radius + 3)
            elif self.dragging_point == 'radius':
                painter.setPen(QPen(QColor(255, 165, 0), 3))
                painter.setBrush(QColor(255, 165, 0, 150))
                painter.drawEllipse(radius_point_screen, point_radius + 3, point_radius + 3)
        elif isinstance(obj, Spline):
            # Рисуем контрольные точки сплайна
            colors = [
                QColor(0, 255, 0),    # Зеленая
                QColor(255, 0, 0),    # Красная
                QColor(0, 0, 255),    # Синяя
                QColor(255, 165, 0),  # Оранжевая
                QColor(255, 0, 255),  # Пурпурная
                QColor(0, 255, 255),  # Голубая
                QColor(255, 255, 0),  # Желтая
                QColor(128, 128, 128) # Серая
            ]
            
            for i, point in enumerate(obj.control_points):
                point_screen = self.viewport.world_to_screen(point)
                color = colors[i % len(colors)]
                
                # Подсвечиваем перемещаемую точку
                if self.dragging_point == f'point_{i}':
                    painter.setPen(QPen(color, 3))
                    painter.setBrush(QColor(color.red(), color.green(), color.blue(), 150))
                    painter.drawEllipse(point_screen, point_radius + 3, point_radius + 3)
                else:
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(QColor(color.red(), color.green(), color.blue(), 200))
                    painter.drawEllipse(point_screen, point_radius, point_radius)
        
        painter.restore()
    
    def _find_spline_insertion_index(self, spline, point: QPointF) -> int:
        """Находит индекс для вставки новой контрольной точки сплайна"""
        if len(spline.control_points) == 0:
            return 0
        
        if len(spline.control_points) == 1:
            return 1
        
        # Находим ближайший сегмент между контрольными точками
        min_dist = float('inf')
        best_index = len(spline.control_points)
        
        for i in range(len(spline.control_points) - 1):
            p1 = spline.control_points[i]
            p2 = spline.control_points[i + 1]
            
            # Вычисляем расстояние от точки до сегмента
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            seg_len_sq = dx*dx + dy*dy
            
            if seg_len_sq < 1e-10:
                # Точки совпадают, используем расстояние до одной из них
                dist = math.sqrt((point.x() - p1.x())**2 + (point.y() - p1.y())**2)
            else:
                # Проекция точки на сегмент
                t = ((point.x() - p1.x()) * dx + (point.y() - p1.y()) * dy) / seg_len_sq
                t = max(0, min(1, t))
                
                # Ближайшая точка на сегменте
                closest_x = p1.x() + t * dx
                closest_y = p1.y() + t * dy
                
                # Расстояние до сегмента
                dist = math.sqrt((point.x() - closest_x)**2 + (point.y() - closest_y)**2)
            
            if dist < min_dist:
                min_dist = dist
                best_index = i + 1
        
        # Также проверяем расстояние до сплайна (кривой)
        # Находим ближайшую точку на сплайне
        num_samples = 100
        min_spline_dist = float('inf')
        best_spline_index = len(spline.control_points)
        
        for i in range(num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            spline_point = spline._get_point_on_spline(t)
            dist = math.sqrt((point.x() - spline_point.x())**2 + (point.y() - spline_point.y())**2)
            
            if dist < min_spline_dist:
                min_spline_dist = dist
                # Находим, между какими контрольными точками находится эта точка на сплайне
                # Для Catmull-Rom сплайна точка t находится между контрольными точками
                if len(spline.control_points) >= 2:
                    # Приблизительно определяем индекс
                    segment_index = int(t * (len(spline.control_points) - 1))
                    best_spline_index = min(segment_index + 1, len(spline.control_points))
        
        # Используем индекс, соответствующий ближайшему сегменту или точке на сплайне
        return best_index
    
    def _draw_snap_point(self, painter):
        """Рисует текущую точку привязки"""
        if not self.current_snap_point:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Применяем трансформацию viewport
        transform = self.viewport.get_total_transform()
        painter.setTransform(transform)
        
        # Цвет и стиль точки привязки
        from core.snapping import SnapType
        if self.current_snap_point.snap_type == SnapType.END:
            snap_color = QColor(255, 0, 0)  # Красный для конца
        elif self.current_snap_point.snap_type == SnapType.MIDDLE:
            snap_color = QColor(0, 255, 0)  # Зеленый для середины
        elif self.current_snap_point.snap_type == SnapType.CENTER:
            snap_color = QColor(0, 0, 255)  # Синий для центра
        elif self.current_snap_point.snap_type == SnapType.VERTEX:
            snap_color = QColor(255, 165, 0)  # Оранжевый для вершины
        elif self.current_snap_point.snap_type == SnapType.INTERSECTION:
            snap_color = QColor(255, 0, 255)  # Пурпурный для пересечения
        else:
            snap_color = QColor(128, 128, 128)  # Серый по умолчанию
        
        # Рисуем крестик для точки привязки
        scale_factor = self.viewport.get_scale()
        snap_size = max(8.0 / scale_factor, 1.0)  # Размер крестика
        
        snap_pen = QPen(snap_color, 2.0 / scale_factor)
        painter.setPen(snap_pen)
        
        point = self.current_snap_point.point
        painter.drawLine(
            point.x() - snap_size, point.y(),
            point.x() + snap_size, point.y()
        )
        painter.drawLine(
            point.x(), point.y() - snap_size,
            point.x(), point.y() + snap_size
        )
        
        # Рисуем круг вокруг точки
        painter.setBrush(Qt.NoBrush)
        circle_pen = QPen(snap_color, 1.0 / scale_factor, Qt.DashLine)
        painter.setPen(circle_pen)
        from PySide6.QtCore import QRectF
        circle_rect = QRectF(
            point.x() - snap_size * 1.5,
            point.y() - snap_size * 1.5,
            snap_size * 3,
            snap_size * 3
        )
        painter.drawEllipse(circle_rect)
        
        painter.restore()
    
    def set_input_points(self, points):
        """Устанавливает точки ввода для визуализации"""
        self.input_points = points if points else []
        self.update()
    
    def clear_input_points(self):
        """Очищает точки ввода"""
        self.input_points = []
        self.update()
    
    def show_context_menu(self, position):
        """Показывает контекстное меню"""
        menu = QMenu(self)
        
        zoom_in_action = menu.addAction("Увеличить")
        zoom_in_action.triggered.connect(self.zoom_in)
        
        zoom_out_action = menu.addAction("Уменьшить")
        zoom_out_action.triggered.connect(self.zoom_out)
        
        menu.addSeparator()
        
        show_all_action = menu.addAction("Показать всё")
        show_all_action.triggered.connect(self.show_all)
        
        reset_view_action = menu.addAction("Сбросить вид")
        reset_view_action.triggered.connect(self.reset_view)
        
        menu.addSeparator()
        
        rotate_left_action = menu.addAction("Повернуть налево")
        rotate_left_action.triggered.connect(lambda: self.rotate_left(15))
        
        rotate_right_action = menu.addAction("Повернуть направо")
        rotate_right_action.triggered.connect(lambda: self.rotate_right(15))
        
        menu.exec_(self.mapToGlobal(position))
    
    def mousePressEvent(self, event):
        """Обработчик нажатия кнопки мыши"""
        if event.button() == Qt.LeftButton:
            if self.pan_mode:
                self.last_mouse_pos = event.position()
            elif self.editing_mode:
                # Режим редактирования - проверяем, кликнули ли по редактируемым точкам
                world_pos = self.viewport.screen_to_world(event.position())
                world_pos = self._apply_snapping(world_pos)
                
                # Получаем выделенные объекты
                selected = self.selection_manager.get_selected_objects()
                if len(selected) == 1:
                    from widgets.primitives import Circle, Rectangle, Arc, Ellipse, Spline
                    obj = selected[0]
                    tolerance = 10.0 / self.viewport.get_scale()  # Толерантность в мировых координатах
                    
                    if isinstance(obj, LineSegment):
                        line = obj
                        # Проверяем, кликнули ли по начальной точке
                        dist_to_start = math.sqrt(
                            (world_pos.x() - line.start_point.x())**2 + 
                            (world_pos.y() - line.start_point.y())**2
                        )
                        
                        # Проверяем, кликнули ли по конечной точке
                        dist_to_end = math.sqrt(
                            (world_pos.x() - line.end_point.x())**2 + 
                            (world_pos.y() - line.end_point.y())**2
                        )
                        
                        if dist_to_start <= tolerance:
                            self.dragging_point = 'start'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('start')
                            return
                        elif dist_to_end <= tolerance:
                            self.dragging_point = 'end'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('end')
                            return
                    elif isinstance(obj, Circle):
                        circle = obj
                        # Проверяем, кликнули ли по центру окружности
                        dist_to_center = math.sqrt(
                            (world_pos.x() - circle.center.x())**2 + 
                            (world_pos.y() - circle.center.y())**2
                        )
                        
                        # Проверяем, кликнули ли по крайней точке окружности (для изменения радиуса)
                        # Точка находится справа от центра (0°)
                        radius_point = QPointF(circle.center.x() + circle.radius, circle.center.y())
                        dist_to_radius_point = math.sqrt(
                            (world_pos.x() - radius_point.x())**2 + 
                            (world_pos.y() - radius_point.y())**2
                        )
                        
                        if dist_to_center <= tolerance:
                            self.dragging_point = 'center'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('center')
                            return
                        elif dist_to_radius_point <= tolerance:
                            self.dragging_point = 'radius'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('radius')
                            return
                    elif isinstance(obj, Rectangle):
                        from widgets.primitives import Rectangle
                        rect = obj
                        # Вычисляем центр прямоугольника
                        bbox = rect.get_bounding_box()
                        center = QPointF(bbox.center().x(), bbox.center().y())
                        
                        # Проверяем, кликнули ли по центру прямоугольника
                        dist_to_center = math.sqrt(
                            (world_pos.x() - center.x())**2 + 
                            (world_pos.y() - center.y())**2
                        )
                        
                        if dist_to_center <= tolerance:
                            self.dragging_point = 'center'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('center')
                            return
                        
                        # Проверяем, кликнули ли по углам прямоугольника
                        top_left = rect.top_left
                        bottom_right = rect.bottom_right
                        top_right = QPointF(bottom_right.x(), top_left.y())
                        bottom_left = QPointF(top_left.x(), bottom_right.y())
                        
                        dist_to_top_left = math.sqrt(
                            (world_pos.x() - top_left.x())**2 + 
                            (world_pos.y() - top_left.y())**2
                        )
                        dist_to_top_right = math.sqrt(
                            (world_pos.x() - top_right.x())**2 + 
                            (world_pos.y() - top_right.y())**2
                        )
                        dist_to_bottom_right = math.sqrt(
                            (world_pos.x() - bottom_right.x())**2 + 
                            (world_pos.y() - bottom_right.y())**2
                        )
                        dist_to_bottom_left = math.sqrt(
                            (world_pos.x() - bottom_left.x())**2 + 
                            (world_pos.y() - bottom_left.y())**2
                        )
                        
                        # Находим ближайший угол
                        min_dist = min(dist_to_top_left, dist_to_top_right, 
                                      dist_to_bottom_right, dist_to_bottom_left)
                        
                        if min_dist <= tolerance:
                            if min_dist == dist_to_top_left:
                                self.dragging_point = 'top_left'
                            elif min_dist == dist_to_top_right:
                                self.dragging_point = 'top_right'
                            elif min_dist == dist_to_bottom_right:
                                self.dragging_point = 'bottom_right'
                            else:
                                self.dragging_point = 'bottom_left'
                            
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point(self.dragging_point)
                            return
                    elif isinstance(obj, Arc):
                        arc = obj
                        # Проверяем, кликнули ли по центру дуги
                        dist_to_center = math.sqrt(
                            (world_pos.x() - arc.center.x())**2 + 
                            (world_pos.y() - arc.center.y())**2
                        )
                        
                        if dist_to_center <= tolerance:
                            self.dragging_point = 'center'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('center')
                            return
                        
                        # Вычисляем средний угол для точки радиуса
                        mid_angle = (arc.start_angle + arc.end_angle) / 2.0
                        if arc.start_angle > arc.end_angle:
                            span = (360 - arc.start_angle) + arc.end_angle
                            mid_angle = (arc.start_angle + span / 2.0) % 360
                        
                        # Получаем точки на дуге
                        start_point = arc.get_point_at_angle(arc.start_angle)
                        end_point = arc.get_point_at_angle(arc.end_angle)
                        mid_point = arc.get_point_at_angle(mid_angle)
                        
                        # Проверяем, кликнули ли по точкам на дуге
                        dist_to_start = math.sqrt(
                            (world_pos.x() - start_point.x())**2 + 
                            (world_pos.y() - start_point.y())**2
                        )
                        dist_to_end = math.sqrt(
                            (world_pos.x() - end_point.x())**2 + 
                            (world_pos.y() - end_point.y())**2
                        )
                        dist_to_mid = math.sqrt(
                            (world_pos.x() - mid_point.x())**2 + 
                            (world_pos.y() - mid_point.y())**2
                        )
                        
                        # Находим ближайшую точку
                        min_dist = min(dist_to_start, dist_to_end, dist_to_mid)
                        
                        if min_dist <= tolerance:
                            if min_dist == dist_to_start:
                                self.dragging_point = 'start_angle'
                            elif min_dist == dist_to_end:
                                self.dragging_point = 'end_angle'
                            else:
                                self.dragging_point = 'radius'
                            
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point(self.dragging_point)
                            return
                    elif isinstance(obj, Ellipse):
                        ellipse = obj
                        # Проверяем, кликнули ли по центру эллипса
                        dist_to_center = math.sqrt(
                            (world_pos.x() - ellipse.center.x())**2 + 
                            (world_pos.y() - ellipse.center.y())**2
                        )
                        
                        if dist_to_center <= tolerance:
                            self.dragging_point = 'center'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('center')
                            return
                        
                        # Точки на осях для изменения радиусов
                        radius_x_point = QPointF(ellipse.center.x() + ellipse.radius_x, ellipse.center.y())
                        radius_y_point = QPointF(ellipse.center.x(), ellipse.center.y() - ellipse.radius_y)
                        
                        dist_to_radius_x = math.sqrt(
                            (world_pos.x() - radius_x_point.x())**2 + 
                            (world_pos.y() - radius_x_point.y())**2
                        )
                        dist_to_radius_y = math.sqrt(
                            (world_pos.x() - radius_y_point.x())**2 + 
                            (world_pos.y() - radius_y_point.y())**2
                        )
                        
                        # Находим ближайшую точку
                        min_dist = min(dist_to_radius_x, dist_to_radius_y)
                        
                        if min_dist <= tolerance:
                            if min_dist == dist_to_radius_x:
                                self.dragging_point = 'radius_x'
                            else:
                                self.dragging_point = 'radius_y'
                            
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point(self.dragging_point)
                            return
                    elif isinstance(obj, Polygon):
                        polygon = obj
                        # Проверяем, кликнули ли по центру многоугольника
                        dist_to_center = math.sqrt(
                            (world_pos.x() - polygon.center.x())**2 + 
                            (world_pos.y() - polygon.center.y())**2
                        )
                        
                        if dist_to_center <= tolerance:
                            self.dragging_point = 'center'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('center')
                            return
                        
                        # Точка для изменения радиуса - на окружности, справа от центра
                        if hasattr(polygon, 'construction_type') and polygon.construction_type == "circumscribed":
                            if polygon.num_vertices > 2:
                                effective_radius = polygon.radius / math.cos(math.pi / polygon.num_vertices)
                            else:
                                effective_radius = polygon.radius
                        else:
                            effective_radius = polygon.radius
                        
                        radius_point = QPointF(polygon.center.x() + effective_radius, polygon.center.y())
                        dist_to_radius = math.sqrt(
                            (world_pos.x() - radius_point.x())**2 + 
                            (world_pos.y() - radius_point.y())**2
                        )
                        
                        if dist_to_radius <= tolerance:
                            self.dragging_point = 'radius'
                            self.drag_start_pos = world_pos
                            if self.edit_dialog:
                                self.edit_dialog.set_dragging_point('radius')
                            return
                    elif isinstance(obj, Spline):
                        spline = obj
                        # Проверяем, кликнули ли по контрольным точкам
                        clicked_on_point = False
                        for i, point in enumerate(spline.control_points):
                            dist_to_point = math.sqrt(
                                (world_pos.x() - point.x())**2 + 
                                (world_pos.y() - point.y())**2
                            )
                            
                            if dist_to_point <= tolerance:
                                # Левый клик - начинаем перемещение
                                clicked_on_point = True
                                self.dragging_point = f'point_{i}'
                                self.drag_start_pos = world_pos
                                if self.edit_dialog:
                                    self.edit_dialog.set_dragging_point(f'point_{i}')
                                return
                        
                        # Если кликнули по сплайну (но не по точке), добавляем новую точку
                        # Проверяем расстояние до сплайна (используем больший tolerance для удобства)
                        if not clicked_on_point and spline.contains_point(world_pos, tolerance * 3):
                            # Находим ближайший сегмент между контрольными точками
                            insert_index = self._find_spline_insertion_index(spline, world_pos)
                            # Вставляем точку в найденное место
                            spline.control_points.insert(insert_index, QPointF(world_pos))
                            if self.edit_dialog:
                                self.edit_dialog.update_spline_info()
                            self.update()
                            return
                
                # В режиме редактирования не начинаем рисование нового объекта
                # Просто выходим, если клик не попал по точкам
                return
            else:
                world_pos = self.viewport.screen_to_world(event.position())
                
                # Применяем привязку
                world_pos = self._apply_snapping(world_pos)
                
                # Проверяем, есть ли активная точка привязки
                # Если есть - начинаем рисование из этой точки, не проверяя клик по объекту
                has_active_snap = self.current_snap_point is not None
                
                # Проверяем, кликнули ли по существующему объекту (для выделения)
                # Но только если мы не рисуем новый объект И нет активной точки привязки
                if not self.scene.is_drawing() and not has_active_snap:
                    clicked_obj = self.selection_manager.find_object_at_point(
                        world_pos, self.scene.get_objects()
                    )
                    if clicked_obj:
                        # Клик по объекту - выделяем его
                        # Если зажат Ctrl, добавляем к выделению, иначе просто выделяем
                        add_to_selection = bool(event.modifiers() & Qt.ControlModifier)
                        self.selection_manager.select_object(clicked_obj, add_to_selection)
                        self.update()
                        # Прерываем выполнение - не начинаем рисование нового объекта
                        return
                    else:
                        # Клик не по объекту - снимаем выделение (если не Ctrl)
                        if not (event.modifiers() & Qt.ControlModifier):
                            self.selection_manager.clear_selection()
                        self.update()
                
                # Начинаем рисование нового объекта
                # Если есть активная точка привязки, начинаем из неё
                # Если нет - начинаем из текущей позиции мыши
                if not self.scene.is_drawing():
                    # Снимаем выделение при начале рисования нового объекта
                    self.selection_manager.clear_selection()
                    # Используем стиль из менеджера, если доступен
                    style = None
                    if self.style_manager:
                        style = self.style_manager.get_current_style()
                    # Передаем метод создания окружности, дуги или прямоугольника
                    kwargs = {}
                    if self.primitive_type == 'circle':
                        kwargs['circle_method'] = self.circle_creation_method
                    elif self.primitive_type == 'arc':
                        kwargs['arc_method'] = self.arc_creation_method
                    elif self.primitive_type == 'rectangle':
                        kwargs['rectangle_method'] = self.rectangle_creation_method
                    elif self.primitive_type == 'polygon':
                        kwargs['polygon_method'] = self.polygon_creation_method
                        kwargs['num_vertices'] = self.polygon_num_vertices
                    elif self.primitive_type == 'spline':
                        # Для сплайна не нужны дополнительные параметры
                        pass
                    self.scene.start_drawing(world_pos, drawing_type=self.primitive_type,
                                            style=style, color=self.line_color, width=self.line_width, **kwargs)
                    # Устанавливаем фокус для получения событий клавиатуры (например, ESC для отмены)
                    self.setFocus()
                    # Эмитируем сигнал о начале рисования прямоугольника (после start_drawing)
                    if self.primitive_type == 'rectangle':
                        self.rectangle_drawing_started.emit(self.rectangle_creation_method)
                    # Обновляем объект для предпросмотра
                    self.scene.update_current_object(world_pos)
                    current_obj = self.scene.get_current_object()
                    if current_obj and hasattr(current_obj, '_legacy_color'):
                        current_obj._legacy_color = self.line_color
                else:
                    # Для дуги и эллипса нужны три клика, для остальных - два
                    if self.primitive_type == 'arc':
                        # Проверяем метод создания дуги
                        method = self.arc_creation_method
                        if method == 'three_points':
                            # Для трех точек нужно три клика
                            if self.scene._arc_end_point is None:
                                # Второй клик - фиксируем конечную точку
                                self.scene._arc_end_point = world_pos
                                # Очищаем временную точку
                                if hasattr(self.scene, '_temp_arc_end_point'):
                                    self.scene._temp_arc_end_point = None
                                # Обновляем объект для предпросмотра
                                self.scene.update_current_object(world_pos)
                            else:
                                # Третий клик - точка высоты, завершаем
                                self.scene.update_current_object(world_pos)
                                obj = self.scene.finish_drawing()
                                if obj:
                                    self.line_finished.emit()
                        elif method == 'center_angles':
                            # Для центра и углов - второй клик определяет радиус
                            if self.scene._arc_radius == 0.0:
                                # Второй клик - фиксируем радиус
                                dx = world_pos.x() - self.scene._arc_center.x()
                                dy = world_pos.y() - self.scene._arc_center.y()
                                self.scene._arc_radius = math.sqrt(dx*dx + dy*dy)
                                self.scene.update_current_object(world_pos)
                            else:
                                # Радиус уже установлен, завершаем (углы задаются через UI)
                                obj = self.scene.finish_drawing()
                                if obj:
                                    self.line_finished.emit()
                    elif self.primitive_type == 'circle':
                        # Проверяем метод создания окружности
                        method = self.circle_creation_method
                        if method == 'three_points':
                            # Для трех точек нужно три клика
                            if self.scene._circle_point2 is None:
                                # Второй клик - фиксируем вторую точку
                                self.scene._circle_point2 = world_pos
                                self.scene.update_current_object(world_pos)
                            else:
                                # Третий клик - завершаем
                                self.scene._circle_point3 = world_pos
                                self.scene.update_current_object(world_pos)
                                obj = self.scene.finish_drawing()
                                if obj:
                                    self.line_finished.emit()
                        else:
                            # Для остальных методов - завершаем при втором клике
                            current_obj = self.scene.get_current_object()
                            if current_obj:
                                self.scene.update_current_object(world_pos)
                            obj = self.scene.finish_drawing()
                            if obj:
                                self.line_finished.emit()
                    elif self.primitive_type == 'ellipse':
                        # Проверяем этап создания эллипса
                        if hasattr(self.scene, '_ellipse_end_point') and self.scene._ellipse_end_point is None:
                            # Второй клик - фиксируем конечную точку
                            self.scene._ellipse_end_point = world_pos
                            # Очищаем временную точку
                            if hasattr(self.scene, '_temp_ellipse_end_point'):
                                self.scene._temp_ellipse_end_point = None
                            # Не обновляем объект здесь, так как третья точка еще не установлена
                            # Обновление произойдет при движении мыши
                        else:
                            # Третий клик - точка высоты, завершаем
                            self.scene.update_current_object(world_pos)
                            obj = self.scene.finish_drawing()
                            if obj:
                                self.line_finished.emit()
                    elif self.primitive_type == 'polygon':
                        # Для многоугольника второй клик завершает создание (радиус определяется)
                        self.scene.update_current_object(world_pos)
                        obj = self.scene.finish_drawing()
                        if obj:
                            self.line_finished.emit()
                    elif self.primitive_type == 'spline':
                        # Для сплайна левый клик добавляет контрольную точку
                        # Проверяем, не был ли это двойной клик (обрабатывается в mouseDoubleClickEvent)
                        current_time = event.timestamp()
                        is_double_click = (self.last_left_click_time > 0 and 
                                         current_time - self.last_left_click_time < 300 and
                                         self.last_left_click_pos and
                                         (world_pos - self.last_left_click_pos).manhattanLength() < 5)
                        
                        if not is_double_click:
                            # Проверяем tolerance для привязки к начальной точке
                            tolerance = 10.0 / self.viewport.get_scale()
                            is_closed = self.scene.add_spline_control_point(world_pos, tolerance)
                            if is_closed:
                                # Если сплайн замкнут, завершаем создание
                                obj = self.scene.finish_drawing()
                                if obj:
                                    self.line_finished.emit()
                            self.update()
                            self.last_left_click_time = current_time
                            self.last_left_click_pos = world_pos
                        # Если это двойной клик, не добавляем точку и не обновляем время
                        # (двойной клик обработается в mouseDoubleClickEvent)
                    elif self.primitive_type == 'rectangle':
                        # Проверяем метод создания прямоугольника
                        method = self.rectangle_creation_method
                        if method == 'point_size' or method == 'center_size':
                            # Для этих методов первый клик устанавливает точку/центр
                            # Размеры должны быть установлены из UI (через сигнал rectangle_drawing_started)
                            # Проверяем размеры после небольшой задержки, чтобы дать время сигналу обработаться
                            def check_and_finish():
                                if (self.scene.is_drawing() and 
                                    self.scene._drawing_type == 'rectangle' and
                                    self.scene._rectangle_width > 0.0 and 
                                    self.scene._rectangle_height > 0.0):
                                    obj = self.scene.finish_drawing()
                                    if obj:
                                        self.line_finished.emit()
                                    self.update()
                            QTimer.singleShot(10, check_and_finish)
                            # Обновляем предпросмотр
                            self.scene.update_current_object(world_pos)
                        else:
                            # Для остальных методов (two_points, with_fillets) - завершаем при втором клике
                            current_obj = self.scene.get_current_object()
                            if current_obj:
                                self.scene.update_current_object(world_pos)
                            obj = self.scene.finish_drawing()
                            if obj:
                                self.line_finished.emit()
                    else:
                        # Для остальных примитивов - завершаем при втором клике
                        current_obj = self.scene.get_current_object()
                        if current_obj:
                            # Обновляем объект перед завершением
                            self.scene.update_current_object(world_pos)
                        obj = self.scene.finish_drawing()
                        if obj:
                            self.line_finished.emit()
                
                self.update()
        
        elif event.button() == Qt.RightButton:
            # Проверяем, находимся ли мы в режиме редактирования
            if self.editing_mode:
                world_pos = self.viewport.screen_to_world(event.position())
                world_pos = self._apply_snapping(world_pos)
                
                # Получаем выделенные объекты
                selected = self.selection_manager.get_selected_objects()
                if len(selected) == 1:
                    from widgets.primitives import Spline
                    obj = selected[0]
                    
                    if isinstance(obj, Spline):
                        spline = obj
                        tolerance = 10.0 / self.viewport.get_scale()
                        
                        # Проверяем, кликнули ли по контрольным точкам
                        for i, point in enumerate(spline.control_points):
                            dist_to_point = math.sqrt(
                                (world_pos.x() - point.x())**2 + 
                                (world_pos.y() - point.y())**2
                            )
                            
                            if dist_to_point <= tolerance:
                                # Правый клик - выбираем точку для удаления
                                if self.edit_dialog:
                                    self.edit_dialog.set_selected_spline_point(i)
                                self.update()
                                return
            
            # Правая кнопка - сохраняем позицию для определения клика/перетаскивания
            self.right_button_press_pos = event.position()
            self.right_button_press_time = event.timestamp()
            
            self.right_button_click_count += 1
            
            if self.right_button_click_count == 1:
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_timer = QTimer()
                self.right_button_click_timer.setSingleShot(True)
                self.right_button_click_timer.timeout.connect(self._handle_single_right_click)
                # Уменьшаем время таймера для более быстрой реакции
                self.right_button_click_timer.start(200)
            elif self.right_button_click_count == 2:
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
                pos_point = QPoint(int(event.position().x()), int(event.position().y()))
                self.show_context_menu(pos_point)
                return
        
        elif event.button() == Qt.MiddleButton:
            self.last_mouse_pos = event.position()
    
    def mouseMoveEvent(self, event):
        """Обработчик движения мыши"""
        world_pos = self.viewport.screen_to_world(event.position())
        self.cursor_world_coords = world_pos
        
        # Применяем привязку для отображения при наведении (даже без перетаскивания)
        # Это обновит self.current_snap_point для визуализации
        self._apply_snapping(world_pos)
        
        # Обновляем виджет для отображения точки привязки
        self.update()
        
        self.view_changed.emit()
        
        # Обработка перемещения точек в режиме редактирования
        if self.editing_mode and self.dragging_point and (event.buttons() & Qt.LeftButton):
            selected = self.selection_manager.get_selected_objects()
            if len(selected) == 1:
                from widgets.primitives import Circle, Rectangle, Arc, Ellipse, Polygon, Spline
                obj = selected[0]
                # Применяем привязку, исключая редактируемый объект
                world_pos = self._apply_snapping(world_pos, exclude_object=obj)
                
                if isinstance(obj, LineSegment):
                    line = obj
                    if self.dragging_point == 'start':
                        line.start_point = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.start_x_spin.blockSignals(True)
                            self.edit_dialog.start_y_spin.blockSignals(True)
                            self.edit_dialog.start_x_spin.setValue(world_pos.x())
                            self.edit_dialog.start_y_spin.setValue(world_pos.y())
                            self.edit_dialog.start_x_spin.blockSignals(False)
                            self.edit_dialog.start_y_spin.blockSignals(False)
                            # Обновляем полярные координаты, если они видны
                            if self.edit_dialog.polar_group.isVisible():
                                self.edit_dialog.update_polar_from_cartesian()
                    elif self.dragging_point == 'end':
                        line.end_point = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.end_x_spin.blockSignals(True)
                            self.edit_dialog.end_y_spin.blockSignals(True)
                            self.edit_dialog.end_x_spin.setValue(world_pos.x())
                            self.edit_dialog.end_y_spin.setValue(world_pos.y())
                            self.edit_dialog.end_x_spin.blockSignals(False)
                            self.edit_dialog.end_y_spin.blockSignals(False)
                            # Обновляем полярные координаты, если они видны
                            if self.edit_dialog.polar_group.isVisible():
                                self.edit_dialog.update_polar_from_cartesian()
                elif isinstance(obj, Circle):
                    circle = obj
                    if self.dragging_point == 'center':
                        circle.center = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.circle_center_x_spin.blockSignals(True)
                            self.edit_dialog.circle_center_y_spin.blockSignals(True)
                            self.edit_dialog.circle_center_x_spin.setValue(world_pos.x())
                            self.edit_dialog.circle_center_y_spin.setValue(world_pos.y())
                            self.edit_dialog.circle_center_x_spin.blockSignals(False)
                            self.edit_dialog.circle_center_y_spin.blockSignals(False)
                    elif self.dragging_point == 'radius':
                        # Вычисляем новый радиус как расстояние от центра до новой позиции
                        dx = world_pos.x() - circle.center.x()
                        dy = world_pos.y() - circle.center.y()
                        new_radius = math.sqrt(dx*dx + dy*dy)
                        # Минимальный радиус
                        if new_radius < 0.01:
                            new_radius = 0.01
                        circle.radius = new_radius
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.circle_radius_spin.blockSignals(True)
                            self.edit_dialog.circle_diameter_spin.blockSignals(True)
                            self.edit_dialog.circle_radius_spin.setValue(new_radius)
                            self.edit_dialog.circle_diameter_spin.setValue(new_radius * 2)
                            self.edit_dialog.circle_radius_spin.blockSignals(False)
                            self.edit_dialog.circle_diameter_spin.blockSignals(False)
                elif isinstance(obj, Rectangle):
                    from widgets.primitives import Rectangle
                    rect = obj
                    if self.dragging_point == 'center':
                        # Перемещаем весь прямоугольник, сохраняя размеры
                        bbox = rect.get_bounding_box()
                        old_center = QPointF(bbox.center().x(), bbox.center().y())
                        dx = world_pos.x() - old_center.x()
                        dy = world_pos.y() - old_center.y()
                        
                        # Сдвигаем оба угла на одинаковое смещение
                        rect.top_left = QPointF(rect.top_left.x() + dx, rect.top_left.y() + dy)
                        rect.bottom_right = QPointF(rect.bottom_right.x() + dx, rect.bottom_right.y() + dy)
                        
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_x_spin.setValue(rect.top_left.x())
                            self.edit_dialog.rect_top_left_y_spin.setValue(rect.top_left.y())
                            self.edit_dialog.rect_bottom_right_x_spin.setValue(rect.bottom_right.x())
                            self.edit_dialog.rect_bottom_right_y_spin.setValue(rect.bottom_right.y())
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(False)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(False)
                    elif self.dragging_point == 'top_left':
                        rect.top_left = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_x_spin.setValue(world_pos.x())
                            self.edit_dialog.rect_top_left_y_spin.setValue(world_pos.y())
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(False)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(False)
                            # Обновляем размеры
                            bbox = rect.get_bounding_box()
                            self.edit_dialog.rect_width_spin.blockSignals(True)
                            self.edit_dialog.rect_height_spin.blockSignals(True)
                            self.edit_dialog.rect_width_spin.setValue(bbox.width())
                            self.edit_dialog.rect_height_spin.setValue(bbox.height())
                            self.edit_dialog.rect_width_spin.blockSignals(False)
                            self.edit_dialog.rect_height_spin.blockSignals(False)
                    elif self.dragging_point == 'top_right':
                        rect.top_left = QPointF(rect.top_left.x(), world_pos.y())
                        rect.bottom_right = QPointF(world_pos.x(), rect.bottom_right.y())
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_x_spin.setValue(rect.top_left.x())
                            self.edit_dialog.rect_top_left_y_spin.setValue(rect.top_left.y())
                            self.edit_dialog.rect_bottom_right_x_spin.setValue(rect.bottom_right.x())
                            self.edit_dialog.rect_bottom_right_y_spin.setValue(rect.bottom_right.y())
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(False)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(False)
                            # Обновляем размеры
                            bbox = rect.get_bounding_box()
                            self.edit_dialog.rect_width_spin.blockSignals(True)
                            self.edit_dialog.rect_height_spin.blockSignals(True)
                            self.edit_dialog.rect_width_spin.setValue(bbox.width())
                            self.edit_dialog.rect_height_spin.setValue(bbox.height())
                            self.edit_dialog.rect_width_spin.blockSignals(False)
                            self.edit_dialog.rect_height_spin.blockSignals(False)
                    elif self.dragging_point == 'bottom_right':
                        rect.bottom_right = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_x_spin.setValue(world_pos.x())
                            self.edit_dialog.rect_bottom_right_y_spin.setValue(world_pos.y())
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(False)
                            # Обновляем размеры
                            bbox = rect.get_bounding_box()
                            self.edit_dialog.rect_width_spin.blockSignals(True)
                            self.edit_dialog.rect_height_spin.blockSignals(True)
                            self.edit_dialog.rect_width_spin.setValue(bbox.width())
                            self.edit_dialog.rect_height_spin.setValue(bbox.height())
                            self.edit_dialog.rect_width_spin.blockSignals(False)
                            self.edit_dialog.rect_height_spin.blockSignals(False)
                    elif self.dragging_point == 'bottom_left':
                        rect.top_left = QPointF(world_pos.x(), rect.top_left.y())
                        rect.bottom_right = QPointF(rect.bottom_right.x(), world_pos.y())
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(True)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(True)
                            self.edit_dialog.rect_top_left_x_spin.setValue(rect.top_left.x())
                            self.edit_dialog.rect_top_left_y_spin.setValue(rect.top_left.y())
                            self.edit_dialog.rect_bottom_right_x_spin.setValue(rect.bottom_right.x())
                            self.edit_dialog.rect_bottom_right_y_spin.setValue(rect.bottom_right.y())
                            self.edit_dialog.rect_top_left_x_spin.blockSignals(False)
                            self.edit_dialog.rect_top_left_y_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_x_spin.blockSignals(False)
                            self.edit_dialog.rect_bottom_right_y_spin.blockSignals(False)
                            # Обновляем размеры
                            bbox = rect.get_bounding_box()
                            self.edit_dialog.rect_width_spin.blockSignals(True)
                            self.edit_dialog.rect_height_spin.blockSignals(True)
                            self.edit_dialog.rect_width_spin.setValue(bbox.width())
                            self.edit_dialog.rect_height_spin.setValue(bbox.height())
                            self.edit_dialog.rect_width_spin.blockSignals(False)
                            self.edit_dialog.rect_height_spin.blockSignals(False)
                elif isinstance(obj, Arc):
                    arc = obj
                    if self.dragging_point == 'center':
                        # Перемещаем центр дуги
                        arc.center = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.arc_center_x_spin.blockSignals(True)
                            self.edit_dialog.arc_center_y_spin.blockSignals(True)
                            self.edit_dialog.arc_center_x_spin.setValue(world_pos.x())
                            self.edit_dialog.arc_center_y_spin.setValue(world_pos.y())
                            self.edit_dialog.arc_center_x_spin.blockSignals(False)
                            self.edit_dialog.arc_center_y_spin.blockSignals(False)
                    elif self.dragging_point == 'radius':
                        # Изменяем радиус дуги
                        # Вычисляем расстояние от центра до новой позиции
                        dx = world_pos.x() - arc.center.x()
                        dy = world_pos.y() - arc.center.y()
                        new_radius = math.sqrt(dx*dx + dy*dy)
                        # Минимальный радиус
                        if new_radius < 0.01:
                            new_radius = 0.01
                        # Сохраняем пропорции радиусов
                        ratio = arc.radius_y / arc.radius_x if arc.radius_x > 0 else 1.0
                        arc.radius_x = new_radius
                        arc.radius_y = new_radius * ratio
                        arc.radius = max(arc.radius_x, arc.radius_y)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.arc_radius_x_spin.blockSignals(True)
                            self.edit_dialog.arc_radius_y_spin.blockSignals(True)
                            self.edit_dialog.arc_radius_x_spin.setValue(arc.radius_x)
                            self.edit_dialog.arc_radius_y_spin.setValue(arc.radius_y)
                            self.edit_dialog.arc_radius_x_spin.blockSignals(False)
                            self.edit_dialog.arc_radius_y_spin.blockSignals(False)
                    elif self.dragging_point == 'start_angle':
                        # Изменяем начальный угол
                        dx = world_pos.x() - arc.center.x()
                        dy = world_pos.y() - arc.center.y()
                        # Вычисляем угол в градусах
                        angle_rad = math.atan2(dy, dx)
                        new_angle = math.degrees(angle_rad)
                        # Нормализуем угол в диапазон [0, 360)
                        if new_angle < 0:
                            new_angle += 360
                        arc.start_angle = new_angle
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.arc_start_angle_spin.blockSignals(True)
                            self.edit_dialog.arc_start_angle_spin.setValue(new_angle)
                            self.edit_dialog.arc_start_angle_spin.blockSignals(False)
                    elif self.dragging_point == 'end_angle':
                        # Изменяем конечный угол
                        dx = world_pos.x() - arc.center.x()
                        dy = world_pos.y() - arc.center.y()
                        # Вычисляем угол в градусах
                        angle_rad = math.atan2(dy, dx)
                        new_angle = math.degrees(angle_rad)
                        # Нормализуем угол в диапазон [0, 360)
                        if new_angle < 0:
                            new_angle += 360
                        arc.end_angle = new_angle
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.arc_end_angle_spin.blockSignals(True)
                            self.edit_dialog.arc_end_angle_spin.setValue(new_angle)
                            self.edit_dialog.arc_end_angle_spin.blockSignals(False)
                elif isinstance(obj, Ellipse):
                    ellipse = obj
                    if self.dragging_point == 'center':
                        # Перемещаем центр эллипса
                        ellipse.center = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.ellipse_center_x_spin.blockSignals(True)
                            self.edit_dialog.ellipse_center_y_spin.blockSignals(True)
                            self.edit_dialog.ellipse_center_x_spin.setValue(world_pos.x())
                            self.edit_dialog.ellipse_center_y_spin.setValue(world_pos.y())
                            self.edit_dialog.ellipse_center_x_spin.blockSignals(False)
                            self.edit_dialog.ellipse_center_y_spin.blockSignals(False)
                    elif self.dragging_point == 'radius_x':
                        # Изменяем горизонтальный радиус
                        dx = world_pos.x() - ellipse.center.x()
                        new_radius_x = abs(dx)
                        # Минимальный радиус
                        if new_radius_x < 0.01:
                            new_radius_x = 0.01
                        ellipse.radius_x = new_radius_x
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.ellipse_radius_x_spin.blockSignals(True)
                            self.edit_dialog.ellipse_radius_x_spin.setValue(new_radius_x)
                            self.edit_dialog.ellipse_radius_x_spin.blockSignals(False)
                    elif self.dragging_point == 'radius_y':
                        # Изменяем вертикальный радиус
                        dy = ellipse.center.y() - world_pos.y()  # Инвертируем, так как Y растет вниз
                        new_radius_y = abs(dy)
                        # Минимальный радиус
                        if new_radius_y < 0.01:
                            new_radius_y = 0.01
                        ellipse.radius_y = new_radius_y
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.ellipse_radius_y_spin.blockSignals(True)
                            self.edit_dialog.ellipse_radius_y_spin.setValue(new_radius_y)
                            self.edit_dialog.ellipse_radius_y_spin.blockSignals(False)
                elif isinstance(obj, Polygon):
                    polygon = obj
                    if self.dragging_point == 'center':
                        # Перемещаем центр многоугольника
                        polygon.center = QPointF(world_pos)
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.polygon_center_x_spin.blockSignals(True)
                            self.edit_dialog.polygon_center_y_spin.blockSignals(True)
                            self.edit_dialog.polygon_center_x_spin.setValue(world_pos.x())
                            self.edit_dialog.polygon_center_y_spin.setValue(world_pos.y())
                            self.edit_dialog.polygon_center_x_spin.blockSignals(False)
                            self.edit_dialog.polygon_center_y_spin.blockSignals(False)
                    elif self.dragging_point == 'radius':
                        # Изменяем радиус многоугольника
                        # Вычисляем расстояние от центра до новой позиции
                        dx = world_pos.x() - polygon.center.x()
                        dy = world_pos.y() - polygon.center.y()
                        new_radius = math.sqrt(dx*dx + dy*dy)
                        # Минимальный радиус
                        if new_radius < 0.01:
                            new_radius = 0.01
                        
                        # Для описанного многоугольника нужно пересчитать радиус
                        if hasattr(polygon, 'construction_type') and polygon.construction_type == "circumscribed":
                            # new_radius - это радиус описанной окружности, нужно найти радиус вписанной
                            if polygon.num_vertices > 2:
                                polygon.radius = new_radius * math.cos(math.pi / polygon.num_vertices)
                            else:
                                polygon.radius = new_radius
                        else:
                            # Для вписанного многоугольника new_radius - это и есть нужный радиус
                            polygon.radius = new_radius
                        
                        # Обновляем поля в окне редактирования
                        if self.edit_dialog:
                            self.edit_dialog.polygon_radius_spin.blockSignals(True)
                            self.edit_dialog.polygon_radius_spin.setValue(polygon.radius)
                            self.edit_dialog.polygon_radius_spin.blockSignals(False)
                elif isinstance(obj, Spline):
                    spline = obj
                    # Проверяем, какая точка перемещается
                    if self.dragging_point and self.dragging_point.startswith('point_'):
                        try:
                            point_index = int(self.dragging_point.split('_')[1])
                            if 0 <= point_index < len(spline.control_points):
                                # Перемещаем контрольную точку
                                spline.control_points[point_index] = QPointF(world_pos)
                                # Обновляем информацию в окне редактирования
                                if self.edit_dialog:
                                    self.edit_dialog.update_spline_info()
                        except (ValueError, IndexError):
                            pass
                
                self.update()
                return
        
        # Для сплайна проверяем привязку к начальной точке при создании
        if self.primitive_type == 'spline' and self.scene.is_drawing():
            if len(self.scene._spline_control_points) >= 2:
                # Проверяем расстояние до первой точки
                first_point = self.scene._spline_control_points[0]
                dx = world_pos.x() - first_point.x()
                dy = world_pos.y() - first_point.y()
                distance = math.sqrt(dx*dx + dy*dy)
                tolerance = 10.0 / self.viewport.get_scale()
                
                if distance <= tolerance:
                    # Привязываем к начальной точке для замыкания
                    world_pos = QPointF(first_point)
                    # Устанавливаем специальную точку привязки для визуализации
                    from core.snapping import SnapPoint, SnapType
                    self.current_snap_point = SnapPoint(first_point, SnapType.END, "Начало сплайна")
                    self.update()
                else:
                    # Применяем обычную привязку
                    if not (event.buttons() & Qt.RightButton) and not self.pan_mode and not (event.buttons() & Qt.MiddleButton):
                        had_snap_point = self.current_snap_point is not None
                        self._apply_snapping(world_pos)
                        has_snap_point = self.current_snap_point is not None
                        if had_snap_point != has_snap_point:
                            self.update()
            else:
                # Применяем обычную привязку
                if not (event.buttons() & Qt.RightButton) and not self.pan_mode and not (event.buttons() & Qt.MiddleButton):
                    had_snap_point = self.current_snap_point is not None
                    self._apply_snapping(world_pos)
                    has_snap_point = self.current_snap_point is not None
                    if had_snap_point != has_snap_point:
                        self.update()
        elif not (event.buttons() & Qt.RightButton) and not self.pan_mode and not (event.buttons() & Qt.MiddleButton):
            # Применяем привязку при наведении мыши (даже если не рисуем)
            # Это нужно для визуализации точек привязки
            # Сохраняем предыдущее состояние привязки
            had_snap_point = self.current_snap_point is not None
            
            # В режиме редактирования исключаем редактируемый объект из привязки
            exclude_obj = None
            if self.editing_mode:
                selected = self.selection_manager.get_selected_objects()
                if len(selected) == 1:
                    exclude_obj = selected[0]
            
            # Применяем привязку для визуализации, но не изменяем world_pos если не рисуем
            self._apply_snapping(world_pos, exclude_object=exclude_obj)
            # Обновляем виджет если состояние привязки изменилось
            has_snap_point = self.current_snap_point is not None
            if had_snap_point != has_snap_point:
                self.update()
        
        # Проверяем, началось ли перетаскивание правой кнопкой
        if (event.buttons() & Qt.RightButton and self.right_button_press_pos):
            delta = (event.position() - self.right_button_press_pos).manhattanLength()
            if delta > 3:
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
                
                # Начинаем выделение рамкой
                if not self.is_selecting:
                    if not (event.modifiers() & Qt.ControlModifier):
                        self.selection_manager.clear_selection()
                    self.is_selecting = True
                    self.selection_start = self.right_button_press_pos
                    self.selection_end = event.position()
                else:
                    self.selection_end = event.position()
                self.update()
                return
        
        # Обновляем выделение рамкой
        if self.is_selecting and self.selection_start and (event.buttons() & Qt.RightButton):
            self.selection_end = event.position()
            self.update()
            return
        
        if self.pan_mode and event.buttons() & Qt.LeftButton:
            if self.last_mouse_pos:
                delta = event.position() - self.last_mouse_pos
                self.viewport.pan(delta)
                self.last_mouse_pos = event.position()
                self.view_changed.emit()
                self.update()
        elif event.buttons() & Qt.MiddleButton:
            if self.last_mouse_pos:
                delta = event.position() - self.last_mouse_pos
                self.viewport.pan(delta)
                self.last_mouse_pos = event.position()
                self.view_changed.emit()
                self.update()
        elif self.scene.is_drawing():
            # Обновляем объект при движении мыши во время рисования
            world_pos = self.viewport.screen_to_world(event.position())
            
            # Применяем привязку
            world_pos = self._apply_snapping(world_pos)
            
            # Для дуги и эллипса во время второго этапа показываем предпросмотр конечной точки
            if self.primitive_type == 'arc':
                method = self.arc_creation_method
                if method == 'three_points':
                    # Обновляем конечную точку для предпросмотра (временно, только для отображения)
                    if self.scene._arc_end_point is None:
                        # Второй этап - обновляем предпросмотр конечной точки (точка еще не зафиксирована)
                        # Сохраняем временно для отображения
                        self.scene._temp_arc_end_point = world_pos
                        # Обновляем предпросмотр линии
                        self.scene.update_current_object(world_pos)
                    elif self.scene._arc_end_point is not None:
                        # Третий этап - обновляем высоту (крайние точки уже зафиксированы)
                        self.scene.update_current_object(world_pos)
                elif method == 'center_angles':
                    # Для метода центр+углы обновляем радиус при движении мыши
                    if self.scene._arc_radius == 0.0:
                        self.scene.update_current_object(world_pos)
            elif self.primitive_type == 'circle':
                # Обновляем окружность при движении мыши
                method = self.circle_creation_method
                if method == 'three_points':
                    if self.scene._circle_point2 is None:
                        # Второй этап - предпросмотр второй точки
                        self.scene.update_current_object(world_pos)
                    elif self.scene._circle_point2 is not None:
                        # Третий этап - предпросмотр третьей точки
                        self.scene.update_current_object(world_pos)
                else:
                    # Для остальных методов - обычное обновление
                    self.scene.update_current_object(world_pos)
            elif self.primitive_type == 'ellipse':
                # Обновляем конечную точку для предпросмотра (временно, только для отображения)
                if hasattr(self.scene, '_ellipse_end_point') and self.scene._ellipse_end_point is None:
                    # Второй этап - обновляем предпросмотр конечной точки (точка еще не зафиксирована)
                    # Сохраняем временно для отображения
                    self.scene._temp_ellipse_end_point = world_pos
                    # Обновляем предпросмотр эллипса
                    self.scene.update_current_object(world_pos)
                elif hasattr(self.scene, '_ellipse_end_point') and self.scene._ellipse_end_point is not None:
                    # Третий этап - обновляем высоту (крайние точки уже зафиксированы)
                    self.scene.update_current_object(world_pos)
            else:
                self.scene.update_current_object(world_pos)
            
            self.update()
    
    def _handle_single_right_click(self):
        """Обрабатывает одинарный клик ПКМ"""
        self.right_button_click_count = 0
        
        # Отменяем рисование, если оно активно
        if self.scene.is_drawing():
            self.scene.cancel_drawing()
            self.update()
        
        # Очищаем выделение рамкой, если оно было начато
        if self.is_selecting:
            self.is_selecting = False
            self.selection_start = None
            self.selection_end = None
            self.update()
        
        self.right_button_press_pos = None
        self.right_button_press_time = None
    
    def mouseDoubleClickEvent(self, event):
        """Обработчик двойного клика мыши"""
        if event.button() == Qt.LeftButton:
            if not self.pan_mode and self.primitive_type == 'spline' and self.scene.is_drawing():
                # Для сплайна двойной клик завершает создание
                # Удаляем последнюю точку, если она была добавлена при первом клике двойного клика
                if (self.last_left_click_time > 0 and 
                    event.timestamp() - self.last_left_click_time < 300 and
                    len(self.scene._spline_control_points) > 0):
                    # Удаляем последнюю точку, которая была добавлена при первом клике
                    self.scene._spline_control_points.pop()
                    if self.scene._current_object:
                        from widgets.primitives import Spline
                        if isinstance(self.scene._current_object, Spline):
                            self.scene._current_object.control_points = self.scene._spline_control_points.copy()
                
                world_pos = self.viewport.screen_to_world(event.position())
                # Применяем привязку
                world_pos = self._apply_snapping(world_pos)
                
                # Проверяем количество зафиксированных точек
                if len(self.scene._spline_control_points) >= 2:
                    obj = self.scene.finish_drawing()
                    if obj:
                        self.line_finished.emit()
                    self.update()
                else:
                    # Если точек меньше 2, просто отменяем рисование
                    self.scene.cancel_drawing()
                    self.update()
                # Сбрасываем счетчик для предотвращения добавления лишней точки
                self.last_left_click_time = 0
                self.last_left_click_pos = None
                return
        
        # Для остальных случаев вызываем стандартную обработку
        super().mouseDoubleClickEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработчик отпускания кнопки мыши"""
        # Завершаем перемещение точки в режиме редактирования
        if event.button() == Qt.LeftButton and self.editing_mode and self.dragging_point:
            self.dragging_point = None
            self.drag_start_pos = None
            if self.edit_dialog:
                self.edit_dialog.set_dragging_point(None)
            self.update()
            return
        """Обработчик отпускания кнопки мыши"""
        if event.button() == Qt.RightButton:
            # Вычисляем расстояние перемещения от начала нажатия
            if self.right_button_press_pos:
                delta = (event.position() - self.right_button_press_pos).manhattanLength()
            else:
                delta = 0
            
            # Проверяем, было ли движение мыши (выделение рамкой)
            if self.is_selecting and self.selection_start and self.selection_end:
                if delta > 3:  # Было движение - обрабатываем выделение
                    # Преобразуем экранные координаты в мировые
                    start_world = self.viewport.screen_to_world(self.selection_start)
                    end_world = self.viewport.screen_to_world(self.selection_end)
                    
                    from PySide6.QtCore import QRectF
                    selection_rect = QRectF(
                        min(start_world.x(), end_world.x()),
                        min(start_world.y(), end_world.y()),
                        abs(end_world.x() - start_world.x()),
                        abs(end_world.y() - start_world.y())
                    )
                    
                    if selection_rect.width() > 1 and selection_rect.height() > 1:
                        add_to_selection = bool(event.modifiers() & Qt.ControlModifier)
                        self.selection_manager.select_objects_in_rect(
                            selection_rect, self.scene.get_objects(), add_to_selection
                        )
                    
                    # Останавливаем таймер, так как это было выделение, а не клик
                    if self.right_button_click_timer:
                        self.right_button_click_timer.stop()
                    self.right_button_click_count = 0
                
                # Всегда очищаем выделение рамкой при отпускании
                self.is_selecting = False
                self.selection_start = None
                self.selection_end = None
            else:
                # Не было выделения - проверяем, был ли это клик
                if delta <= 3:
                    # Это был клик без движения - отменяем рисование сразу
                    if self.scene.is_drawing():
                        self.scene.cancel_drawing()
                        # Останавливаем таймер, так как уже обработали
                        if self.right_button_click_timer:
                            self.right_button_click_timer.stop()
                        self.right_button_click_count = 0
                    # Если таймер еще работает, пусть он тоже сработает (на случай, если рисование не было активно)
                else:
                    # Было движение, но выделение не началось - останавливаем таймер
                    if self.right_button_click_timer:
                        self.right_button_click_timer.stop()
                    self.right_button_click_count = 0
            
            # Очищаем позицию нажатия
            self.right_button_press_pos = None
            self.right_button_press_time = None
            self.update()
        
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.last_mouse_pos = None
    
    def wheelEvent(self, event):
        """Обработчик колесика мыши"""
        zoom_factor = 1.1
        if event.angleDelta().y() > 0:
            self.viewport.zoom_at_point(event.position(), zoom_factor)
        else:
            self.viewport.zoom_at_point(event.position(), 1.0 / zoom_factor)
        self.view_changed.emit()
        self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Обработчик нажатия клавиш"""
        if event.key() == Qt.Key.Key_Escape:
            # Отменяем рисование, если оно активно
            if self.scene.is_drawing():
                self.scene.cancel_drawing()
                self.update()
                return
        
        # Передаем событие базовому классу для стандартной обработки
        super().keyPressEvent(event)
    
    def set_pan_mode(self, enabled):
        """Устанавливает режим панорамирования"""
        self.pan_mode = enabled
        self.view_changed.emit()
    
    def zoom_in(self):
        """Увеличивает масштаб"""
        self.viewport.zoom_in()
        self.view_changed.emit()
        self.update()
    
    def zoom_out(self):
        """Уменьшает масштаб"""
        self.viewport.zoom_out()
        self.view_changed.emit()
        self.update()
    
    def show_all(self):
        """Показывает все отрезки"""
        points = self.scene.get_all_points()
        if not points:
            self.reset_view()
            return
        
        from PySide6.QtCore import QRectF, QPointF
        
        min_x = min(p.x() for p in points)
        max_x = max(p.x() for p in points)
        min_y = min(p.y() for p in points)
        max_y = max(p.y() for p in points)
        
        scene_center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
        scene_width = max_x - min_x
        scene_height = max_y - min_y
        
        corners = [
            QPointF(min_x, min_y),
            QPointF(max_x, min_y),
            QPointF(max_x, max_y),
            QPointF(min_x, max_y)
        ]
        
        if abs(self.viewport.rotation_angle) > 0.01:
            rotation_transform = QTransform()
            rotation_transform.rotate(self.viewport.rotation_angle)
            
            rotated_corners = []
            for corner in corners:
                relative = corner - scene_center
                rotated_relative = rotation_transform.map(relative)
                rotated_corners.append(rotated_relative + scene_center)
            
            rotated_min_x = min(p.x() for p in rotated_corners)
            rotated_max_x = max(p.x() for p in rotated_corners)
            rotated_min_y = min(p.y() for p in rotated_corners)
            rotated_max_y = max(p.y() for p in rotated_corners)
            
            rotated_width = rotated_max_x - rotated_min_x
            rotated_height = rotated_max_y - rotated_min_y
        else:
            rotated_width = scene_width
            rotated_height = scene_height
        
        padding_x = rotated_width * 0.2 if rotated_width > 0 else 10
        padding_y = rotated_height * 0.2 if rotated_height > 0 else 10
        rotated_width += 2 * padding_x
        rotated_height += 2 * padding_y
        
        widget_width = self.width()
        widget_height = self.height()
        
        if rotated_width <= 0 or rotated_height <= 0:
            new_scale = 1.0
        else:
            scale_x = widget_width / rotated_width
            scale_y = widget_height / rotated_height
            new_scale = min(scale_x, scale_y) * 0.9
            new_scale = max(self.viewport.min_scale, min(self.viewport.max_scale, new_scale))
        
        self.viewport.scale_factor = new_scale
        
        widget_center = QPointF(self.width() / 2, self.height() / 2)
        
        rotation_scale_transform = QTransform()
        rotation_scale_transform.rotate(self.viewport.rotation_angle)
        rotation_scale_transform.scale(self.viewport.scale_factor, -self.viewport.scale_factor)
        inv_rotation_scale, success = rotation_scale_transform.inverted()
        
        if success:
            rotated_scaled_center = rotation_scale_transform.map(scene_center)
            self.viewport.translation = QPointF(-rotated_scaled_center.x(), -rotated_scaled_center.y())
        else:
            self.viewport.translation = QPointF(-scene_center.x() * self.viewport.scale_factor, 
                                              scene_center.y() * self.viewport.scale_factor)
        
        self.view_changed.emit()
        self.update()
    
    def show_all_preserve_rotation(self):
        """Альтернатива show_all, которая сохраняет текущий поворот"""
        self.show_all()
    
    def reset_view(self):
        """Полностью сбрасывает вид к начальному состоянию"""
        self.viewport.reset()
        self.view_changed.emit()
        self.update()
    
    def rotate_left(self, angle=15):
        """Поворот налево на указанный угол"""
        self.viewport.rotate(angle)
        self.view_changed.emit()
        self.update()
    
    def rotate_right(self, angle=15):
        """Поворот направо на указанный угол"""
        self.viewport.rotate(-angle)
        self.view_changed.emit()
        self.update()
    
    def get_cursor_world_coords(self):
        """Возвращает координаты курсора в мировых координатах"""
        return self.cursor_world_coords
    
    def get_scale(self):
        """Возвращает текущий масштаб"""
        return self.viewport.get_scale()
    
    def get_rotation(self):
        """Возвращает текущий угол поворота"""
        return self.viewport.get_rotation()
    
    def start_new_line(self):
        """Начинает новый отрезок"""
        if self.scene.is_drawing():
            self.scene.finish_drawing()
        self.update()
    
    def delete_last_line(self):
        """Удаляет последний отрезок"""
        self.scene.delete_last_object()
        self.update()
    
    def delete_all_lines(self):
        """Удаляет все отрезки"""
        self.scene.clear()
        self.update()
    
    def set_grid_step(self, step_mm):
        """Устанавливает шаг сетки в миллиметрах"""
        self.renderer.set_grid_step(step_mm)
        self.update()
    
    def set_line_color(self, color):
        """Устанавливает цвет линии"""
        self.line_color = color
        self.update()
    
    def set_background_color(self, color):
        """Устанавливает цвет фона"""
        self.renderer.background_color = color
        self.update()
    
    def set_grid_color(self, color):
        """Устанавливает цвет сетки"""
        self.renderer.grid_color = color
        self.update()
    
    def set_line_width(self, width):
        """Устанавливает ширину линии (устаревший метод)"""
        self.line_width = width
        self.update()
    
    def get_current_points(self):
        """Возвращает текущие точки"""
        current_line = self.scene.get_current_line()
        if current_line:
            return current_line.start_point, current_line.end_point
        lines = self.scene.get_lines()
        if lines:
            last_line = lines[-1]
            return last_line.start_point, last_line.end_point
        from PySide6.QtCore import QPointF
        return QPointF(0, 0), QPointF(0, 0)
    
    def set_points_from_input(self, start_point, end_point, apply=False):
        """Устанавливает точки из ввода (для обратной совместимости с отрезками)"""
        # Создаем предпросмотр/объект только для отрезков
        if self.primitive_type != 'line':
            return
        
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
        
        if apply:
            new_line = LineSegment(start_point, end_point, style=style, 
                                  color=self.line_color, width=self.line_width)
            if hasattr(new_line, '_legacy_color'):
                new_line._legacy_color = self.line_color
            self.scene.add_object(new_line)
            self.update()
        else:
            if not self.scene.is_drawing():
                self.scene.start_drawing(start_point, drawing_type='line', style=style,
                                       color=self.line_color, width=self.line_width)
                # Устанавливаем фокус для получения событий клавиатуры (например, ESC для отмены)
                self.setFocus()
                current_obj = self.scene.get_current_object()
                if current_obj:
                    self.scene.update_current_object(end_point)
                    if hasattr(current_obj, '_legacy_color'):
                        current_obj._legacy_color = self.line_color
            else:
                current_obj = self.scene.get_current_object()
                if current_obj and isinstance(current_obj, LineSegment):
                    current_obj.start_point = start_point
                    current_obj.end_point = end_point
                    if style and not current_obj.style:
                        current_obj.style = style
                    if hasattr(current_obj, '_legacy_color'):
                        current_obj._legacy_color = self.line_color
            self.update()
    
    def set_primitive_type(self, primitive_type: str):
        """Устанавливает тип создаваемого примитива"""
        self.primitive_type = primitive_type
    
    def set_circle_creation_method(self, method: str):
        """Устанавливает метод создания окружности"""
        self.circle_creation_method = method
    
    def set_arc_creation_method(self, method: str):
        """Устанавливает метод создания дуги"""
        self.arc_creation_method = method
    
    def set_rectangle_creation_method(self, method: str):
        """Устанавливает метод создания прямоугольника"""
        self.rectangle_creation_method = method
    
    def set_ellipse_creation_method(self, method: str):
        """Устанавливает метод создания эллипса"""
        # Метод сохраняется для будущего использования
        # В данный момент эллипс создается через три точки в сцене
        pass
    
    def set_polygon_creation_method(self, method: str):
        """Устанавливает метод создания многоугольника"""
        self.polygon_creation_method = method
    
    def set_polygon_num_vertices(self, num_vertices: int):
        """Устанавливает количество вершин многоугольника"""
        if num_vertices >= 3:
            self.polygon_num_vertices = num_vertices
            # Обновляем текущий объект, если он существует
            if self.scene.is_drawing() and self.scene._drawing_type == 'polygon':
                self.scene.set_polygon_num_vertices(num_vertices)
                self.update()
    
    # Свойства для обратной совместимости
    @property
    def lines(self):
        """Свойство для обратной совместимости"""
        return self.scene.get_lines()
    
    @property
    def current_line(self):
        """Свойство для обратной совместимости"""
        return self.scene.get_current_line()
    
    @property
    def is_drawing(self):
        """Свойство для обратной совместимости"""
        return self.scene.is_drawing()
    
    @property
    def selected_lines(self):
        """Свойство для обратной совместимости"""
        return self.selection_manager.get_selected_lines()
