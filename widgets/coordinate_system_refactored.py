"""
Рефакторенная версия виджета системы координат
Использует разделение ответственностей согласно ООП
"""
import math
from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtCore import Qt, QPointF, QPoint, Signal, QTimer
from PySide6.QtGui import QPainter, QColor

from core.viewport import Viewport
from core.scene import Scene
from core.selection import SelectionManager
from core.renderer import SceneRenderer
from widgets.line_segment import LineSegment
from widgets.line_style import LineStyleManager


class CoordinateSystemWidget(QWidget):
    """Виджет для отображения и взаимодействия с системой координат"""
    
    view_changed = Signal()  # сигнал при изменении вида
    context_menu_requested = Signal(QPoint)  # сигнал для запроса контекстного меню
    selection_changed = Signal(list)  # сигнал при изменении выделения
    line_finished = Signal()  # сигнал при завершении рисования отрезка
    
    def __init__(self, style_manager=None):
        super().__init__()
        
        # Создаем компоненты
        self.viewport = Viewport(self.width(), self.height())
        self.scene = Scene()
        self.selection_manager = SelectionManager()
        self.renderer = SceneRenderer(self.viewport, self.scene, self.selection_manager)
        
        # Менеджер стилей
        self.style_manager = style_manager
        
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
        
        # Координаты курсора
        self.cursor_world_coords = None
        
        # Настройки отрисовки
        self.line_color = QColor(0, 0, 0)
        self.line_width = 2
        
        # Подключаем сигналы
        self.selection_manager.selection_changed.connect(self._on_selection_changed)
        
        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
    
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
        self.renderer.draw(painter)
        
        # Рисуем рамку выделения
        if self.is_selecting and self.selection_start and self.selection_end:
            self._draw_selection_rect(painter)
    
    def _draw_selection_rect(self, painter):
        """Рисует рамку выделения"""
        if not self.selection_start or not self.selection_end:
            return
        
        # Преобразуем экранные координаты в мировые
        start_world = self.viewport.screen_to_world(self.selection_start)
        end_world = self.viewport.screen_to_world(self.selection_end)
        
        # Создаем прямоугольник
        from PySide6.QtCore import QRectF
        rect = QRectF(
            min(start_world.x(), end_world.x()),
            min(start_world.y(), end_world.y()),
            abs(end_world.x() - start_world.x()),
            abs(end_world.y() - start_world.y())
        )
        
        # Рисуем рамку в экранных координатах
        painter.resetTransform()
        from PySide6.QtGui import QPen
        selection_pen = QPen(QColor(0, 100, 255), 1, Qt.DashLine)
        painter.setPen(selection_pen)
        painter.setBrush(QColor(0, 100, 255, 30))
        
        # Преобразуем обратно в экранные координаты для отрисовки
        start_screen = self.viewport.world_to_screen(start_world)
        end_screen = self.viewport.world_to_screen(end_world)
        
        screen_rect = QRectF(
            min(start_screen.x(), end_screen.x()),
            min(start_screen.y(), end_screen.y()),
            abs(end_screen.x() - start_screen.x()),
            abs(end_screen.y() - end_screen.y())
        )
        painter.drawRect(screen_rect)
    
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
            else:
                world_pos = self.viewport.screen_to_world(event.position())
                
                # Проверяем, кликнули ли по существующей линии (для выделения)
                if not self.scene.is_drawing():
                    clicked_line = self.selection_manager.find_object_at_point(
                        world_pos, self.scene.get_lines()
                    )
                    if clicked_line:
                        # Выделение линии
                        add_to_selection = bool(event.modifiers() & Qt.ControlModifier)
                        self.selection_manager.select_object(clicked_line, add_to_selection)
                        self.update()
                        return
                    else:
                        # Клик не по линии - снимаем выделение (если не Ctrl)
                        if not (event.modifiers() & Qt.ControlModifier):
                            self.selection_manager.clear_selection()
                        # Продолжаем выполнение для начала рисования линии
                
                if not self.scene.is_drawing():
                    # Снимаем выделение при начале рисования новой линии
                    self.selection_manager.clear_selection()
                    # Используем стиль из менеджера, если доступен
                    style = None
                    if self.style_manager:
                        style = self.style_manager.get_current_style()
                    self.scene.start_drawing(world_pos, style=style, 
                                            color=self.line_color, width=self.line_width)
                else:
                    # Завершаем рисование
                    line = self.scene.finish_drawing()
                    if line:
                        self.line_finished.emit()
                
                self.update()
        
        elif event.button() == Qt.RightButton:
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
                self.right_button_click_timer.start(300)
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
        self.cursor_world_coords = self.viewport.screen_to_world(event.position())
        self.view_changed.emit()
        
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
        elif self.scene.is_drawing() and event.buttons() & Qt.LeftButton:
            world_pos = self.viewport.screen_to_world(event.position())
            self.scene.update_current_line(world_pos)
            self.update()
    
    def _handle_single_right_click(self):
        """Обрабатывает одинарный клик ПКМ"""
        self.right_button_click_count = 0
        
        if self.scene.is_drawing():
            self.scene.cancel_drawing()
            self.update()
        
        self.right_button_press_pos = None
        self.right_button_press_time = None
    
    def mouseReleaseEvent(self, event):
        """Обработчик отпускания кнопки мыши"""
        if event.button() == Qt.RightButton:
            if self.is_selecting:
                if self.selection_start and self.selection_end:
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
                
                self.is_selecting = False
                self.selection_start = None
                self.selection_end = None
                self.right_button_press_pos = None
                self.right_button_press_time = None
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
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
        from PySide6.QtGui import QTransform
        
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
        """Устанавливает точки из ввода"""
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
                self.scene.start_drawing(start_point, style=style,
                                       color=self.line_color, width=self.line_width)
                current_line = self.scene.get_current_line()
                if current_line:
                    current_line._legacy_color = self.line_color
            else:
                current_line = self.scene.get_current_line()
                if current_line:
                    current_line.start_point = start_point
                    current_line.end_point = end_point
                    if style and not current_line.style:
                        current_line.style = style
                    current_line._legacy_color = self.line_color
            self.update()
    
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

