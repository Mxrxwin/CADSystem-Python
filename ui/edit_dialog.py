"""
Окно редактирования выделенных объектов
"""
import sys
import os
import math

# Добавляем корневую директорию проекта в sys.path, если её там нет
# Это нужно для корректного импорта модулей widgets
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QDoubleSpinBox, QComboBox, QPushButton, QGroupBox,
                               QGridLayout, QWidget, QSpinBox, QMessageBox)
from PySide6.QtCore import QPointF, Qt, Signal
from widgets.line_segment import LineSegment
from widgets.primitives import Arc, Ellipse, Polygon, Spline


class EditDialog(QDialog):
    """Диалоговое окно для редактирования выделенных объектов"""
    
    object_changed = Signal(object)  # Сигнал при изменении объекта
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование объекта")
        self.setModal(False)  # Немодальное окно, чтобы можно было работать с канвасом
        
        self.editing_object = None
        self.canvas = None
        self.editing_mode = False  # Режим редактирования (перемещение точек)
        self.dragging_point = None  # Какая точка перемещается: 'start' или 'end'
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        
        # Заголовок
        self.title_label = QLabel("Выберите объект для редактирования")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self.title_label)
        
        # Контейнер для содержимого редактирования
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_widget.setLayout(self.content_layout)
        layout.addWidget(self.content_widget)
        
        # Кнопки
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel_changes)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        # Исходное состояние объекта для отмены изменений
        self.original_state = None
        
        self.setLayout(layout)
        self.resize(400, 300)
    
    def set_canvas(self, canvas):
        """Устанавливает канвас для редактирования"""
        self.canvas = canvas
    
    def set_object(self, obj):
        """Устанавливает объект для редактирования"""
        self.editing_object = obj
        
        # Сохраняем исходное состояние объекта для отмены изменений
        self.original_state = self._save_object_state(obj)
        
        # Очищаем предыдущее содержимое
        self.clear_content()
        
        if obj is None:
            self.title_label.setText("Выберите объект для редактирования")
            return
        
        from widgets.primitives import Circle, Rectangle, Ellipse
        if isinstance(obj, LineSegment):
            self.setup_line_editing(obj)
        elif isinstance(obj, Circle):
            self.setup_circle_editing(obj)
        elif isinstance(obj, Rectangle):
            self.setup_rectangle_editing(obj)
        elif isinstance(obj, Arc):
            self.setup_arc_editing(obj)
        elif isinstance(obj, Ellipse):
            self.setup_ellipse_editing(obj)
        elif isinstance(obj, Polygon):
            self.setup_polygon_editing(obj)
        elif isinstance(obj, Spline):
            self.setup_spline_editing(obj)
        else:
            self.title_label.setText(f"Редактирование: {type(obj).__name__}")
                # Для других типов объектов можно добавить позже
    
    def clear_content(self):
        """Очищает содержимое окна редактирования"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def setup_line_editing(self, line: LineSegment):
        """Настраивает интерфейс редактирования отрезка"""
        self.title_label.setText("Редактирование отрезка")
        
        # Группа способа задания
        method_group = QGroupBox("Способ задания")
        method_layout = QVBoxLayout()
        
        self.line_method_combo = QComboBox()
        self.line_method_combo.addItems([
            "В декартовых координатах (x₁, y₁) и (x₂, y₂)",
            "В полярных координатах (x₁, y₁) и (r₂, θ₂)"
        ])
        self.line_method_combo.currentTextChanged.connect(self.on_line_method_changed)
        method_layout.addWidget(self.line_method_combo)
        
        # Единицы углов (для полярных координат)
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("Единицы углов:"))
        self.line_angle_combo = QComboBox()
        self.line_angle_combo.addItems(["Градусы", "Радианы"])
        self.line_angle_combo.currentTextChanged.connect(self.on_line_angle_units_changed)
        angle_layout.addWidget(self.line_angle_combo)
        method_layout.addLayout(angle_layout)
        
        method_group.setLayout(method_layout)
        self.content_layout.addWidget(method_group)
        
        # Начальная точка (всегда в декартовых координатах)
        start_group = QGroupBox("Начальная точка (x₁, y₁)")
        start_layout = QGridLayout()
        
        start_layout.addWidget(QLabel("x₁:"), 0, 0)
        self.start_x_spin = QDoubleSpinBox()
        self.start_x_spin.setRange(-10000, 10000)
        self.start_x_spin.setDecimals(2)
        self.start_x_spin.setSingleStep(10)
        self.start_x_spin.valueChanged.connect(self.on_start_point_changed)
        start_layout.addWidget(self.start_x_spin, 0, 1)
        
        start_layout.addWidget(QLabel("y₁:"), 0, 2)
        self.start_y_spin = QDoubleSpinBox()
        self.start_y_spin.setRange(-10000, 10000)
        self.start_y_spin.setDecimals(2)
        self.start_y_spin.setSingleStep(10)
        self.start_y_spin.valueChanged.connect(self.on_start_point_changed)
        start_layout.addWidget(self.start_y_spin, 0, 3)
        
        start_group.setLayout(start_layout)
        self.content_layout.addWidget(start_group)
        
        # Конечная точка - декартовы координаты
        self.cartesian_group = QGroupBox("Конечная точка (x₂, y₂)")
        cartesian_layout = QGridLayout()
        
        cartesian_layout.addWidget(QLabel("x₂:"), 0, 0)
        self.end_x_spin = QDoubleSpinBox()
        self.end_x_spin.setRange(-10000, 10000)
        self.end_x_spin.setDecimals(2)
        self.end_x_spin.setSingleStep(10)
        self.end_x_spin.valueChanged.connect(self.on_cartesian_end_changed)
        cartesian_layout.addWidget(self.end_x_spin, 0, 1)
        
        cartesian_layout.addWidget(QLabel("y₂:"), 0, 2)
        self.end_y_spin = QDoubleSpinBox()
        self.end_y_spin.setRange(-10000, 10000)
        self.end_y_spin.setDecimals(2)
        self.end_y_spin.setSingleStep(10)
        self.end_y_spin.valueChanged.connect(self.on_cartesian_end_changed)
        cartesian_layout.addWidget(self.end_y_spin, 0, 3)
        
        self.cartesian_group.setLayout(cartesian_layout)
        self.content_layout.addWidget(self.cartesian_group)
        
        # Конечная точка - полярные координаты
        self.polar_group = QGroupBox("Конечная точка (r₂, θ₂)")
        polar_layout = QGridLayout()
        
        polar_layout.addWidget(QLabel("r₂:"), 0, 0)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0, 10000)
        self.radius_spin.setDecimals(2)
        self.radius_spin.setSingleStep(10)
        self.radius_spin.valueChanged.connect(self.on_polar_end_changed)
        polar_layout.addWidget(self.radius_spin, 0, 1)
        
        polar_layout.addWidget(QLabel("θ₂:"), 0, 2)
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-360, 360)
        self.angle_spin.setDecimals(2)
        self.angle_spin.setSingleStep(15)
        self.angle_spin.valueChanged.connect(self.on_polar_end_changed)
        polar_layout.addWidget(self.angle_spin, 0, 3)
        
        self.angle_label = QLabel("°")
        polar_layout.addWidget(self.angle_label, 0, 4)
        
        self.polar_group.setLayout(polar_layout)
        self.polar_group.hide()
        self.content_layout.addWidget(self.polar_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения точек\nв рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        # Загружаем данные отрезка
        self.load_line_data(line)
    
    def load_line_data(self, line: LineSegment):
        """Загружает данные отрезка в поля редактирования"""
        # Блокируем сигналы, чтобы не вызывать обработчики при загрузке
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.end_x_spin.blockSignals(True)
        self.end_y_spin.blockSignals(True)
        self.radius_spin.blockSignals(True)
        self.angle_spin.blockSignals(True)
        
        # Начальная точка
        self.start_x_spin.setValue(line.start_point.x())
        self.start_y_spin.setValue(line.start_point.y())
        
        # Конечная точка в декартовых координатах
        self.end_x_spin.setValue(line.end_point.x())
        self.end_y_spin.setValue(line.end_point.y())
        
        # Вычисляем полярные координаты относительно начальной точки
        dx = line.end_point.x() - line.start_point.x()
        dy = line.end_point.y() - line.start_point.y()
        radius = math.sqrt(dx*dx + dy*dy)
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        
        self.radius_spin.setValue(radius)
        self.angle_spin.setValue(angle_deg)
        
        # Устанавливаем способ задания по умолчанию (декартовы координаты)
        self.line_method_combo.setCurrentIndex(0)
        self.line_angle_combo.setCurrentIndex(0)  # Градусы
        
        # Разблокируем сигналы
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        self.end_x_spin.blockSignals(False)
        self.end_y_spin.blockSignals(False)
        self.radius_spin.blockSignals(False)
        self.angle_spin.blockSignals(False)
    
    def on_line_method_changed(self, method_text):
        """Обработчик изменения способа задания"""
        if "декартовых" in method_text.lower():
            self.cartesian_group.show()
            self.polar_group.hide()
        else:
            self.cartesian_group.hide()
            self.polar_group.show()
            # Обновляем полярные координаты на основе текущих декартовых
            self.update_polar_from_cartesian()
    
    def on_line_angle_units_changed(self, units_text):
        """Обработчик изменения единиц углов"""
        is_degrees = units_text == "Градусы"
        self.angle_label.setText("°" if is_degrees else "rad")
        
        # Конвертируем угол
        if self.polar_group.isVisible():
            current_angle = self.angle_spin.value()
            self.angle_spin.blockSignals(True)
            if is_degrees:
                # Были радианы, стали градусы
                self.angle_spin.setRange(-360, 360)
                self.angle_spin.setValue(math.degrees(current_angle))
            else:
                # Были градусы, стали радианы
                self.angle_spin.setRange(-2 * math.pi, 2 * math.pi)
                self.angle_spin.setValue(math.radians(current_angle))
            self.angle_spin.blockSignals(False)
    
    def update_polar_from_cartesian(self):
        """Обновляет полярные координаты на основе декартовых"""
        start_x = self.start_x_spin.value()
        start_y = self.start_y_spin.value()
        end_x = self.end_x_spin.value()
        end_y = self.end_y_spin.value()
        
        dx = end_x - start_x
        dy = end_y - start_y
        radius = math.sqrt(dx*dx + dy*dy)
        angle_rad = math.atan2(dy, dx)
        
        is_degrees = self.line_angle_combo.currentText() == "Градусы"
        angle = math.degrees(angle_rad) if is_degrees else angle_rad
        
        self.radius_spin.blockSignals(True)
        self.angle_spin.blockSignals(True)
        self.radius_spin.setValue(radius)
        self.angle_spin.setValue(angle)
        self.radius_spin.blockSignals(False)
        self.angle_spin.blockSignals(False)
    
    def update_cartesian_from_polar(self):
        """Обновляет декартовы координаты на основе полярных"""
        start_x = self.start_x_spin.value()
        start_y = self.start_y_spin.value()
        radius = self.radius_spin.value()
        angle = self.angle_spin.value()
        
        is_degrees = self.line_angle_combo.currentText() == "Градусы"
        angle_rad = math.radians(angle) if is_degrees else angle
        
        end_x = start_x + radius * math.cos(angle_rad)
        end_y = start_y + radius * math.sin(angle_rad)
        
        self.end_x_spin.blockSignals(True)
        self.end_y_spin.blockSignals(True)
        self.end_x_spin.setValue(end_x)
        self.end_y_spin.setValue(end_y)
        self.end_x_spin.blockSignals(False)
        self.end_y_spin.blockSignals(False)
    
    def on_start_point_changed(self):
        """Обработчик изменения начальной точки"""
        if not self.editing_object:
            return
        
        start_x = self.start_x_spin.value()
        start_y = self.start_y_spin.value()
        
        # Обновляем объект
        if isinstance(self.editing_object, LineSegment):
            # Обновляем только начальную точку, конечная точка остается неизменной
            self.editing_object.start_point = QPointF(start_x, start_y)
            
            # Обновляем полярные координаты, если они видны (на основе текущих значений конечной точки)
            if self.polar_group.isVisible():
                self.update_polar_from_cartesian()
            
            self.apply_changes()
    
    def on_cartesian_end_changed(self):
        """Обработчик изменения конечной точки в декартовых координатах"""
        if not self.editing_object:
            return
        
        end_x = self.end_x_spin.value()
        end_y = self.end_y_spin.value()
        
        if isinstance(self.editing_object, LineSegment):
            self.editing_object.end_point = QPointF(end_x, end_y)
            
            # Обновляем полярные координаты, если они видны
            if self.polar_group.isVisible():
                self.update_polar_from_cartesian()
            
            self.apply_changes()
    
    def on_polar_end_changed(self):
        """Обработчик изменения конечной точки в полярных координатах"""
        if not self.editing_object:
            return
        
        # Обновляем декартовы координаты на основе полярных
        self.update_cartesian_from_polar()
        
        if isinstance(self.editing_object, LineSegment):
            end_x = self.end_x_spin.value()
            end_y = self.end_y_spin.value()
            self.editing_object.end_point = QPointF(end_x, end_y)
            self.apply_changes()
    
    def toggle_edit_mode(self):
        """Переключает режим редактирования (перемещение точек)"""
        self.editing_mode = not self.editing_mode
        
        # Определяем тип объекта для правильного текста
        from widgets.primitives import Circle, Rectangle, Arc, Ellipse, Polygon
        if isinstance(self.editing_object, LineSegment):
            mode_text = "Перемещение точек"
        elif isinstance(self.editing_object, Circle):
            mode_text = "Перемещение точек"
        elif isinstance(self.editing_object, Rectangle):
            mode_text = "Перемещение углов"
        elif isinstance(self.editing_object, Arc):
            mode_text = "Перемещение точек"
        elif isinstance(self.editing_object, Ellipse):
            mode_text = "Перемещение точек"
        elif isinstance(self.editing_object, Polygon):
            mode_text = "Редактирование"
        else:
            mode_text = "Редактирование"
        
        if self.editing_mode:
            self.toggle_edit_mode_btn.setText("Отключить редактирование")
            self.edit_mode_label.setText(f"{mode_text}: Включено")
            self.edit_mode_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.toggle_edit_mode_btn.setText("Включить редактирование")
            self.edit_mode_label.setText(f"{mode_text}: Отключено")
            self.edit_mode_label.setStyleSheet("color: gray;")
            self.dragging_point = None
        
        # Уведомляем канвас о режиме редактирования
        if self.canvas:
            self.canvas.set_editing_mode(self.editing_mode, self)
    
    def is_editing_mode(self):
        """Возвращает True, если режим редактирования включен"""
        return self.editing_mode
    
    def get_dragging_point(self):
        """Возвращает, какую точку перемещают"""
        return self.dragging_point
    
    def set_dragging_point(self, point_type):
        """Устанавливает, какую точку перемещают ('start' или 'end')"""
        self.dragging_point = point_type
    
    def apply_changes(self):
        """Применяет изменения к объекту"""
        if self.editing_object and self.canvas:
            # Обновляем отображение на канвасе
            self.canvas.update()
            # Отправляем сигнал об изменении
            self.object_changed.emit(self.editing_object)
    
    def setup_circle_editing(self, circle):
        """Настраивает интерфейс редактирования окружности"""
        from widgets.primitives import Circle
        
        self.title_label.setText("Редактирование окружности")
        
        # Группа способа задания
        method_group = QGroupBox("Способ задания")
        method_layout = QVBoxLayout()
        
        self.circle_method_combo = QComboBox()
        self.circle_method_combo.addItems([
            "Центр и радиус",
            "Центр и диаметр"
        ])
        self.circle_method_combo.currentTextChanged.connect(self.on_circle_method_changed)
        method_layout.addWidget(self.circle_method_combo)
        
        method_group.setLayout(method_layout)
        self.content_layout.addWidget(method_group)
        
        # Центр окружности
        center_group = QGroupBox("Центр (x, y)")
        center_layout = QGridLayout()
        
        center_layout.addWidget(QLabel("x:"), 0, 0)
        self.circle_center_x_spin = QDoubleSpinBox()
        self.circle_center_x_spin.setRange(-10000, 10000)
        self.circle_center_x_spin.setDecimals(2)
        self.circle_center_x_spin.setSingleStep(10)
        self.circle_center_x_spin.valueChanged.connect(self.on_circle_center_changed)
        center_layout.addWidget(self.circle_center_x_spin, 0, 1)
        
        center_layout.addWidget(QLabel("y:"), 0, 2)
        self.circle_center_y_spin = QDoubleSpinBox()
        self.circle_center_y_spin.setRange(-10000, 10000)
        self.circle_center_y_spin.setDecimals(2)
        self.circle_center_y_spin.setSingleStep(10)
        self.circle_center_y_spin.valueChanged.connect(self.on_circle_center_changed)
        center_layout.addWidget(self.circle_center_y_spin, 0, 3)
        
        center_group.setLayout(center_layout)
        self.content_layout.addWidget(center_group)
        
        # Радиус
        self.circle_radius_group = QGroupBox("Радиус")
        radius_layout = QHBoxLayout()
        
        self.circle_radius_spin = QDoubleSpinBox()
        self.circle_radius_spin.setRange(0.01, 10000)
        self.circle_radius_spin.setDecimals(2)
        self.circle_radius_spin.setSingleStep(10)
        self.circle_radius_spin.valueChanged.connect(self.on_circle_radius_changed)
        radius_layout.addWidget(self.circle_radius_spin)
        
        self.circle_radius_group.setLayout(radius_layout)
        self.content_layout.addWidget(self.circle_radius_group)
        
        # Диаметр
        self.circle_diameter_group = QGroupBox("Диаметр")
        diameter_layout = QHBoxLayout()
        
        self.circle_diameter_spin = QDoubleSpinBox()
        self.circle_diameter_spin.setRange(0.02, 20000)
        self.circle_diameter_spin.setDecimals(2)
        self.circle_diameter_spin.setSingleStep(10)
        self.circle_diameter_spin.valueChanged.connect(self.on_circle_diameter_changed)
        diameter_layout.addWidget(self.circle_diameter_spin)
        
        self.circle_diameter_group.setLayout(diameter_layout)
        self.circle_diameter_group.hide()
        self.content_layout.addWidget(self.circle_diameter_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения центра (синяя точка)\nили крайней точки (оранжевая точка) для изменения радиуса в рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        # Загружаем данные окружности
        self.load_circle_data(circle)
    
    def load_circle_data(self, circle):
        """Загружает данные окружности в поля редактирования"""
        from widgets.primitives import Circle
        
        # Блокируем сигналы, чтобы не вызывать обработчики при загрузке
        self.circle_center_x_spin.blockSignals(True)
        self.circle_center_y_spin.blockSignals(True)
        self.circle_radius_spin.blockSignals(True)
        self.circle_diameter_spin.blockSignals(True)
        
        # Центр
        self.circle_center_x_spin.setValue(circle.center.x())
        self.circle_center_y_spin.setValue(circle.center.y())
        
        # Радиус и диаметр
        self.circle_radius_spin.setValue(circle.radius)
        self.circle_diameter_spin.setValue(circle.radius * 2)
        
        # Устанавливаем способ задания по умолчанию (радиус)
        self.circle_method_combo.setCurrentIndex(0)
        
        # Разблокируем сигналы
        self.circle_center_x_spin.blockSignals(False)
        self.circle_center_y_spin.blockSignals(False)
        self.circle_radius_spin.blockSignals(False)
        self.circle_diameter_spin.blockSignals(False)
    
    def on_circle_method_changed(self, method_text):
        """Обработчик изменения способа задания окружности"""
        if "радиус" in method_text.lower():
            self.circle_radius_group.show()
            self.circle_diameter_group.hide()
        else:
            self.circle_radius_group.hide()
            self.circle_diameter_group.show()
    
    def on_circle_center_changed(self):
        """Обработчик изменения центра окружности"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Circle
        if isinstance(self.editing_object, Circle):
            center_x = self.circle_center_x_spin.value()
            center_y = self.circle_center_y_spin.value()
            self.editing_object.center = QPointF(center_x, center_y)
            self.apply_changes()
    
    def on_circle_radius_changed(self):
        """Обработчик изменения радиуса окружности"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Circle
        if isinstance(self.editing_object, Circle):
            radius = self.circle_radius_spin.value()
            self.editing_object.radius = radius
            
            # Обновляем диаметр
            self.circle_diameter_spin.blockSignals(True)
            self.circle_diameter_spin.setValue(radius * 2)
            self.circle_diameter_spin.blockSignals(False)
            
            self.apply_changes()
    
    def on_circle_diameter_changed(self):
        """Обработчик изменения диаметра окружности"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Circle
        if isinstance(self.editing_object, Circle):
            diameter = self.circle_diameter_spin.value()
            radius = diameter / 2.0
            self.editing_object.radius = radius
            
            # Обновляем радиус
            self.circle_radius_spin.blockSignals(True)
            self.circle_radius_spin.setValue(radius)
            self.circle_radius_spin.blockSignals(False)
            
            self.apply_changes()
    
    def setup_rectangle_editing(self, rectangle):
        """Настраивает интерфейс редактирования прямоугольника"""
        from widgets.primitives import Rectangle
        
        self.title_label.setText("Редактирование прямоугольника")
        
        # Позиция и размеры
        position_group = QGroupBox("Позиция")
        position_layout = QGridLayout()
        
        position_layout.addWidget(QLabel("Верхний левый угол:"), 0, 0)
        self.rect_top_left_x_spin = QDoubleSpinBox()
        self.rect_top_left_x_spin.setRange(-10000, 10000)
        self.rect_top_left_x_spin.setDecimals(2)
        self.rect_top_left_x_spin.setSingleStep(10)
        self.rect_top_left_x_spin.valueChanged.connect(self.on_rectangle_position_changed)
        position_layout.addWidget(QLabel("x:"), 0, 1)
        position_layout.addWidget(self.rect_top_left_x_spin, 0, 2)
        
        self.rect_top_left_y_spin = QDoubleSpinBox()
        self.rect_top_left_y_spin.setRange(-10000, 10000)
        self.rect_top_left_y_spin.setDecimals(2)
        self.rect_top_left_y_spin.setSingleStep(10)
        self.rect_top_left_y_spin.valueChanged.connect(self.on_rectangle_position_changed)
        position_layout.addWidget(QLabel("y:"), 0, 3)
        position_layout.addWidget(self.rect_top_left_y_spin, 0, 4)
        
        position_layout.addWidget(QLabel("Нижний правый угол:"), 1, 0)
        self.rect_bottom_right_x_spin = QDoubleSpinBox()
        self.rect_bottom_right_x_spin.setRange(-10000, 10000)
        self.rect_bottom_right_x_spin.setDecimals(2)
        self.rect_bottom_right_x_spin.setSingleStep(10)
        self.rect_bottom_right_x_spin.valueChanged.connect(self.on_rectangle_position_changed)
        position_layout.addWidget(QLabel("x:"), 1, 1)
        position_layout.addWidget(self.rect_bottom_right_x_spin, 1, 2)
        
        self.rect_bottom_right_y_spin = QDoubleSpinBox()
        self.rect_bottom_right_y_spin.setRange(-10000, 10000)
        self.rect_bottom_right_y_spin.setDecimals(2)
        self.rect_bottom_right_y_spin.setSingleStep(10)
        self.rect_bottom_right_y_spin.valueChanged.connect(self.on_rectangle_position_changed)
        position_layout.addWidget(QLabel("y:"), 1, 3)
        position_layout.addWidget(self.rect_bottom_right_y_spin, 1, 4)
        
        position_group.setLayout(position_layout)
        self.content_layout.addWidget(position_group)
        
        # Размеры
        size_group = QGroupBox("Размеры")
        size_layout = QGridLayout()
        
        size_layout.addWidget(QLabel("Ширина:"), 0, 0)
        self.rect_width_spin = QDoubleSpinBox()
        self.rect_width_spin.setRange(0.01, 10000)
        self.rect_width_spin.setDecimals(2)
        self.rect_width_spin.setSingleStep(10)
        self.rect_width_spin.valueChanged.connect(self.on_rectangle_size_changed)
        size_layout.addWidget(self.rect_width_spin, 0, 1, 1, 4)
        
        size_layout.addWidget(QLabel("Высота:"), 1, 0)
        self.rect_height_spin = QDoubleSpinBox()
        self.rect_height_spin.setRange(0.01, 10000)
        self.rect_height_spin.setDecimals(2)
        self.rect_height_spin.setSingleStep(10)
        self.rect_height_spin.valueChanged.connect(self.on_rectangle_size_changed)
        size_layout.addWidget(self.rect_height_spin, 1, 1, 1, 4)
        
        size_group.setLayout(size_layout)
        self.content_layout.addWidget(size_group)
        
        # Скругления и фаски
        fillet_group = QGroupBox("Скругления и фаски")
        fillet_layout = QVBoxLayout()
        
        fillet_layout.addWidget(QLabel("Радиус скругления углов:"))
        self.rect_fillet_radius_spin = QDoubleSpinBox()
        self.rect_fillet_radius_spin.setRange(0, 10000)
        self.rect_fillet_radius_spin.setDecimals(2)
        self.rect_fillet_radius_spin.setSingleStep(1)
        self.rect_fillet_radius_spin.valueChanged.connect(self.on_rectangle_fillet_changed)
        fillet_layout.addWidget(self.rect_fillet_radius_spin)
        
        info_label = QLabel("Радиус скругления применяется ко всем углам.\nМаксимальный радиус ограничен половиной меньшей стороны.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        fillet_layout.addWidget(info_label)
        
        fillet_group.setLayout(fillet_layout)
        self.content_layout.addWidget(fillet_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.edit_mode_label = QLabel("Перемещение углов: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения центра (фиолетовая точка)\nили углов (зеленый, красный, синий, желтый) прямоугольника в рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        # Загружаем данные прямоугольника
        self.load_rectangle_data(rectangle)
    
    def load_rectangle_data(self, rectangle):
        """Загружает данные прямоугольника в поля редактирования"""
        from widgets.primitives import Rectangle
        
        # Блокируем сигналы, чтобы не вызывать обработчики при загрузке
        self.rect_top_left_x_spin.blockSignals(True)
        self.rect_top_left_y_spin.blockSignals(True)
        self.rect_bottom_right_x_spin.blockSignals(True)
        self.rect_bottom_right_y_spin.blockSignals(True)
        self.rect_width_spin.blockSignals(True)
        self.rect_height_spin.blockSignals(True)
        self.rect_fillet_radius_spin.blockSignals(True)
        
        # Позиция углов
        self.rect_top_left_x_spin.setValue(rectangle.top_left.x())
        self.rect_top_left_y_spin.setValue(rectangle.top_left.y())
        self.rect_bottom_right_x_spin.setValue(rectangle.bottom_right.x())
        self.rect_bottom_right_y_spin.setValue(rectangle.bottom_right.y())
        
        # Размеры
        bbox = rectangle.get_bounding_box()
        self.rect_width_spin.setValue(bbox.width())
        self.rect_height_spin.setValue(bbox.height())
        
        # Радиус скругления
        self.rect_fillet_radius_spin.setValue(getattr(rectangle, 'fillet_radius', 0.0))
        
        # Разблокируем сигналы
        self.rect_top_left_x_spin.blockSignals(False)
        self.rect_top_left_y_spin.blockSignals(False)
        self.rect_bottom_right_x_spin.blockSignals(False)
        self.rect_bottom_right_y_spin.blockSignals(False)
        self.rect_width_spin.blockSignals(False)
        self.rect_height_spin.blockSignals(False)
        self.rect_fillet_radius_spin.blockSignals(False)
    
    def on_rectangle_position_changed(self):
        """Обработчик изменения позиции прямоугольника"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Rectangle
        if isinstance(self.editing_object, Rectangle):
            top_left_x = self.rect_top_left_x_spin.value()
            top_left_y = self.rect_top_left_y_spin.value()
            bottom_right_x = self.rect_bottom_right_x_spin.value()
            bottom_right_y = self.rect_bottom_right_y_spin.value()
            
            self.editing_object.top_left = QPointF(top_left_x, top_left_y)
            self.editing_object.bottom_right = QPointF(bottom_right_x, bottom_right_y)
            
            # Обновляем размеры
            bbox = self.editing_object.get_bounding_box()
            self.rect_width_spin.blockSignals(True)
            self.rect_height_spin.blockSignals(True)
            self.rect_width_spin.setValue(bbox.width())
            self.rect_height_spin.setValue(bbox.height())
            self.rect_width_spin.blockSignals(False)
            self.rect_height_spin.blockSignals(False)
            
            self.apply_changes()
    
    def on_rectangle_size_changed(self):
        """Обработчик изменения размеров прямоугольника"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Rectangle
        if isinstance(self.editing_object, Rectangle):
            width = self.rect_width_spin.value()
            height = self.rect_height_spin.value()
            
            # Сохраняем верхний левый угол, изменяем нижний правый
            top_left = self.editing_object.top_left
            self.editing_object.bottom_right = QPointF(
                top_left.x() + width,
                top_left.y() + height
            )
            
            # Обновляем поля позиции
            self.rect_bottom_right_x_spin.blockSignals(True)
            self.rect_bottom_right_y_spin.blockSignals(True)
            self.rect_bottom_right_x_spin.setValue(self.editing_object.bottom_right.x())
            self.rect_bottom_right_y_spin.setValue(self.editing_object.bottom_right.y())
            self.rect_bottom_right_x_spin.blockSignals(False)
            self.rect_bottom_right_y_spin.blockSignals(False)
            
            # Проверяем радиус скругления (не должен превышать половину меньшей стороны)
            max_fillet = min(width, height) / 2.0
            current_fillet = getattr(self.editing_object, 'fillet_radius', 0.0)
            if current_fillet > max_fillet:
                self.editing_object.fillet_radius = max_fillet
                self.rect_fillet_radius_spin.blockSignals(True)
                self.rect_fillet_radius_spin.setValue(max_fillet)
                self.rect_fillet_radius_spin.blockSignals(False)
            
            self.apply_changes()
    
    def on_rectangle_fillet_changed(self):
        """Обработчик изменения радиуса скругления"""
        if not self.editing_object:
            return
        
        from widgets.primitives import Rectangle
        if isinstance(self.editing_object, Rectangle):
            fillet_radius = self.rect_fillet_radius_spin.value()
            
            # Проверяем, что радиус не превышает половину меньшей стороны
            bbox = self.editing_object.get_bounding_box()
            max_fillet = min(bbox.width(), bbox.height()) / 2.0
            if fillet_radius > max_fillet:
                fillet_radius = max_fillet
                self.rect_fillet_radius_spin.blockSignals(True)
                self.rect_fillet_radius_spin.setValue(fillet_radius)
                self.rect_fillet_radius_spin.blockSignals(False)
            
            self.editing_object.fillet_radius = fillet_radius
            self.apply_changes()
    
    def setup_arc_editing(self, arc):
        """Настройка интерфейса редактирования дуги"""
        self.title_label.setText("Редактирование дуги")
        
        # Группа для центра
        center_group = QGroupBox("Центр")
        center_layout = QGridLayout()
        
        center_layout.addWidget(QLabel("x:"), 0, 0)
        self.arc_center_x_spin = QDoubleSpinBox()
        self.arc_center_x_spin.setRange(-20000, 20000)
        self.arc_center_x_spin.setDecimals(2)
        self.arc_center_x_spin.setSingleStep(10)
        self.arc_center_x_spin.valueChanged.connect(self.on_arc_center_changed)
        center_layout.addWidget(self.arc_center_x_spin, 0, 1)
        
        center_layout.addWidget(QLabel("y:"), 0, 2)
        self.arc_center_y_spin = QDoubleSpinBox()
        self.arc_center_y_spin.setRange(-20000, 20000)
        self.arc_center_y_spin.setDecimals(2)
        self.arc_center_y_spin.setSingleStep(10)
        self.arc_center_y_spin.valueChanged.connect(self.on_arc_center_changed)
        center_layout.addWidget(self.arc_center_y_spin, 0, 3)
        
        center_group.setLayout(center_layout)
        self.content_layout.addWidget(center_group)
        
        # Группа для радиусов
        radius_group = QGroupBox("Радиусы")
        radius_layout = QGridLayout()
        
        radius_layout.addWidget(QLabel("Радиус X:"), 0, 0)
        self.arc_radius_x_spin = QDoubleSpinBox()
        self.arc_radius_x_spin.setRange(0.01, 20000)
        self.arc_radius_x_spin.setDecimals(2)
        self.arc_radius_x_spin.setSingleStep(10)
        self.arc_radius_x_spin.valueChanged.connect(self.on_arc_radius_changed)
        radius_layout.addWidget(self.arc_radius_x_spin, 0, 1)
        
        radius_layout.addWidget(QLabel("Радиус Y:"), 1, 0)
        self.arc_radius_y_spin = QDoubleSpinBox()
        self.arc_radius_y_spin.setRange(0.01, 20000)
        self.arc_radius_y_spin.setDecimals(2)
        self.arc_radius_y_spin.setSingleStep(10)
        self.arc_radius_y_spin.valueChanged.connect(self.on_arc_radius_changed)
        radius_layout.addWidget(self.arc_radius_y_spin, 1, 1)
        
        radius_group.setLayout(radius_layout)
        self.content_layout.addWidget(radius_group)
        
        # Группа для углов
        angle_group = QGroupBox("Углы")
        angle_layout = QGridLayout()
        
        angle_layout.addWidget(QLabel("Начальный угол (°):"), 0, 0)
        self.arc_start_angle_spin = QDoubleSpinBox()
        self.arc_start_angle_spin.setRange(-3600, 3600)
        self.arc_start_angle_spin.setDecimals(2)
        self.arc_start_angle_spin.setSingleStep(5)
        self.arc_start_angle_spin.valueChanged.connect(self.on_arc_angle_changed)
        angle_layout.addWidget(self.arc_start_angle_spin, 0, 1)
        
        angle_layout.addWidget(QLabel("Конечный угол (°):"), 1, 0)
        self.arc_end_angle_spin = QDoubleSpinBox()
        self.arc_end_angle_spin.setRange(-3600, 3600)
        self.arc_end_angle_spin.setDecimals(2)
        self.arc_end_angle_spin.setSingleStep(5)
        self.arc_end_angle_spin.valueChanged.connect(self.on_arc_angle_changed)
        angle_layout.addWidget(self.arc_end_angle_spin, 1, 1)
        
        angle_group.setLayout(angle_layout)
        self.content_layout.addWidget(angle_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения центра (синяя точка),\nрадиуса (оранжевая точка) или изменения углов (зеленая и красная точки) в рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        self.update_arc_input_fields()
    
    def update_arc_input_fields(self):
        """Обновляет поля ввода для дуги"""
        if not isinstance(self.editing_object, Arc):
            return
        
        arc = self.editing_object
        self.arc_center_x_spin.blockSignals(True)
        self.arc_center_y_spin.blockSignals(True)
        self.arc_radius_x_spin.blockSignals(True)
        self.arc_radius_y_spin.blockSignals(True)
        self.arc_start_angle_spin.blockSignals(True)
        self.arc_end_angle_spin.blockSignals(True)
        
        self.arc_center_x_spin.setValue(arc.center.x())
        self.arc_center_y_spin.setValue(arc.center.y())
        self.arc_radius_x_spin.setValue(arc.radius_x)
        self.arc_radius_y_spin.setValue(arc.radius_y)
        self.arc_start_angle_spin.setValue(arc.start_angle)
        self.arc_end_angle_spin.setValue(arc.end_angle)
        
        self.arc_center_x_spin.blockSignals(False)
        self.arc_center_y_spin.blockSignals(False)
        self.arc_radius_x_spin.blockSignals(False)
        self.arc_radius_y_spin.blockSignals(False)
        self.arc_start_angle_spin.blockSignals(False)
        self.arc_end_angle_spin.blockSignals(False)
        
        self.apply_changes()
    
    def on_arc_center_changed(self):
        """Обработчик изменения центра дуги"""
        if not isinstance(self.editing_object, Arc):
            return
        
        arc = self.editing_object
        arc.center = QPointF(self.arc_center_x_spin.value(), self.arc_center_y_spin.value())
        self.apply_changes()
    
    def on_arc_radius_changed(self):
        """Обработчик изменения радиуса дуги"""
        if not isinstance(self.editing_object, Arc):
            return
        
        arc = self.editing_object
        arc.radius_x = self.arc_radius_x_spin.value()
        arc.radius_y = self.arc_radius_y_spin.value()
        arc.radius = max(arc.radius_x, arc.radius_y)
        self.apply_changes()
    
    def on_arc_angle_changed(self):
        """Обработчик изменения углов дуги"""
        if not isinstance(self.editing_object, Arc):
            return
        
        arc = self.editing_object
        arc.start_angle = self.arc_start_angle_spin.value()
        arc.end_angle = self.arc_end_angle_spin.value()
        self.apply_changes()
    
    def setup_ellipse_editing(self, ellipse):
        """Настройка интерфейса редактирования эллипса"""
        self.title_label.setText("Редактирование эллипса")
        
        # Группа для центра
        center_group = QGroupBox("Центр")
        center_layout = QGridLayout()
        
        center_layout.addWidget(QLabel("x:"), 0, 0)
        self.ellipse_center_x_spin = QDoubleSpinBox()
        self.ellipse_center_x_spin.setRange(-20000, 20000)
        self.ellipse_center_x_spin.setDecimals(2)
        self.ellipse_center_x_spin.setSingleStep(10)
        self.ellipse_center_x_spin.valueChanged.connect(self.on_ellipse_center_changed)
        center_layout.addWidget(self.ellipse_center_x_spin, 0, 1)
        
        center_layout.addWidget(QLabel("y:"), 0, 2)
        self.ellipse_center_y_spin = QDoubleSpinBox()
        self.ellipse_center_y_spin.setRange(-20000, 20000)
        self.ellipse_center_y_spin.setDecimals(2)
        self.ellipse_center_y_spin.setSingleStep(10)
        self.ellipse_center_y_spin.valueChanged.connect(self.on_ellipse_center_changed)
        center_layout.addWidget(self.ellipse_center_y_spin, 0, 3)
        
        center_group.setLayout(center_layout)
        self.content_layout.addWidget(center_group)
        
        # Группа для радиусов (длин осей)
        radius_group = QGroupBox("Длины осей")
        radius_layout = QGridLayout()
        
        radius_layout.addWidget(QLabel("Радиус X (горизонтальная ось):"), 0, 0)
        self.ellipse_radius_x_spin = QDoubleSpinBox()
        self.ellipse_radius_x_spin.setRange(0.01, 20000)
        self.ellipse_radius_x_spin.setDecimals(2)
        self.ellipse_radius_x_spin.setSingleStep(10)
        self.ellipse_radius_x_spin.valueChanged.connect(self.on_ellipse_radius_changed)
        radius_layout.addWidget(self.ellipse_radius_x_spin, 0, 1)
        
        radius_layout.addWidget(QLabel("Радиус Y (вертикальная ось):"), 1, 0)
        self.ellipse_radius_y_spin = QDoubleSpinBox()
        self.ellipse_radius_y_spin.setRange(0.01, 20000)
        self.ellipse_radius_y_spin.setDecimals(2)
        self.ellipse_radius_y_spin.setSingleStep(10)
        self.ellipse_radius_y_spin.valueChanged.connect(self.on_ellipse_radius_changed)
        radius_layout.addWidget(self.ellipse_radius_y_spin, 1, 1)
        
        radius_group.setLayout(radius_layout)
        self.content_layout.addWidget(radius_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения центра (синяя точка)\nили изменения длин осей (оранжевые точки на осях) в рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        self.update_ellipse_input_fields()
    
    def update_ellipse_input_fields(self):
        """Обновляет поля ввода для эллипса"""
        if not isinstance(self.editing_object, Ellipse):
            return
        
        ellipse = self.editing_object
        self.ellipse_center_x_spin.blockSignals(True)
        self.ellipse_center_y_spin.blockSignals(True)
        self.ellipse_radius_x_spin.blockSignals(True)
        self.ellipse_radius_y_spin.blockSignals(True)
        
        self.ellipse_center_x_spin.setValue(ellipse.center.x())
        self.ellipse_center_y_spin.setValue(ellipse.center.y())
        self.ellipse_radius_x_spin.setValue(ellipse.radius_x)
        self.ellipse_radius_y_spin.setValue(ellipse.radius_y)
        
        self.ellipse_center_x_spin.blockSignals(False)
        self.ellipse_center_y_spin.blockSignals(False)
        self.ellipse_radius_x_spin.blockSignals(False)
        self.ellipse_radius_y_spin.blockSignals(False)
        
        self.apply_changes()
    
    def on_ellipse_center_changed(self):
        """Обработчик изменения центра эллипса"""
        if not isinstance(self.editing_object, Ellipse):
            return
        
        ellipse = self.editing_object
        ellipse.center = QPointF(self.ellipse_center_x_spin.value(), self.ellipse_center_y_spin.value())
        self.apply_changes()
    
    def on_ellipse_radius_changed(self):
        """Обработчик изменения радиусов эллипса"""
        if not isinstance(self.editing_object, Ellipse):
            return
        
        ellipse = self.editing_object
        ellipse.radius_x = self.ellipse_radius_x_spin.value()
        ellipse.radius_y = self.ellipse_radius_y_spin.value()
        self.apply_changes()
    
    def setup_polygon_editing(self, polygon):
        """Настройка интерфейса редактирования многоугольника"""
        self.title_label.setText("Редактирование многоугольника")
        
        # Группа для центра
        center_group = QGroupBox("Центр")
        center_layout = QGridLayout()
        
        center_layout.addWidget(QLabel("x:"), 0, 0)
        self.polygon_center_x_spin = QDoubleSpinBox()
        self.polygon_center_x_spin.setRange(-20000, 20000)
        self.polygon_center_x_spin.setDecimals(2)
        self.polygon_center_x_spin.setSingleStep(10)
        self.polygon_center_x_spin.valueChanged.connect(self.on_polygon_center_changed)
        center_layout.addWidget(self.polygon_center_x_spin, 0, 1)
        
        center_layout.addWidget(QLabel("y:"), 0, 2)
        self.polygon_center_y_spin = QDoubleSpinBox()
        self.polygon_center_y_spin.setRange(-20000, 20000)
        self.polygon_center_y_spin.setDecimals(2)
        self.polygon_center_y_spin.setSingleStep(10)
        self.polygon_center_y_spin.valueChanged.connect(self.on_polygon_center_changed)
        center_layout.addWidget(self.polygon_center_y_spin, 0, 3)
        
        center_group.setLayout(center_layout)
        self.content_layout.addWidget(center_group)
        
        # Группа для варианта построения
        construction_group = QGroupBox("Вариант построения")
        construction_layout = QVBoxLayout()
        
        self.polygon_construction_combo = QComboBox()
        self.polygon_construction_combo.addItems([
            "Вписанный (вершины на окружности)",
            "Описанный (стороны касаются окружности)"
        ])
        # Устанавливаем текущее значение (для обратной совместимости)
        if not hasattr(polygon, 'construction_type'):
            polygon.construction_type = "inscribed"
        if polygon.construction_type == "circumscribed":
            self.polygon_construction_combo.setCurrentIndex(1)
        else:
            self.polygon_construction_combo.setCurrentIndex(0)
        self.polygon_construction_combo.currentIndexChanged.connect(self.on_polygon_construction_changed)
        construction_layout.addWidget(self.polygon_construction_combo)
        
        construction_group.setLayout(construction_layout)
        self.content_layout.addWidget(construction_group)
        
        # Группа для параметров
        params_group = QGroupBox("Параметры")
        params_layout = QGridLayout()
        
        params_layout.addWidget(QLabel("Радиус:"), 0, 0)
        self.polygon_radius_spin = QDoubleSpinBox()
        self.polygon_radius_spin.setRange(0.01, 20000)
        self.polygon_radius_spin.setDecimals(2)
        self.polygon_radius_spin.setSingleStep(10)
        self.polygon_radius_spin.valueChanged.connect(self.on_polygon_radius_changed)
        params_layout.addWidget(self.polygon_radius_spin, 0, 1)
        
        params_layout.addWidget(QLabel("Количество углов:"), 1, 0)
        self.polygon_num_vertices_spin = QSpinBox()
        self.polygon_num_vertices_spin.setRange(3, 100)
        self.polygon_num_vertices_spin.setSingleStep(1)
        self.polygon_num_vertices_spin.valueChanged.connect(self.on_polygon_num_vertices_changed)
        params_layout.addWidget(self.polygon_num_vertices_spin, 1, 1)
        
        params_group.setLayout(params_layout)
        self.content_layout.addWidget(params_group)
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для перемещения центра (синяя точка)\nили изменения радиуса (оранжевая точка) в рабочей области мышью")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        self.update_polygon_input_fields()
    
    def update_polygon_input_fields(self):
        """Обновляет поля ввода для многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        polygon = self.editing_object
        # Для обратной совместимости
        if not hasattr(polygon, 'construction_type'):
            polygon.construction_type = "inscribed"
        
        self.polygon_center_x_spin.blockSignals(True)
        self.polygon_center_y_spin.blockSignals(True)
        self.polygon_radius_spin.blockSignals(True)
        self.polygon_num_vertices_spin.blockSignals(True)
        self.polygon_construction_combo.blockSignals(True)
        
        self.polygon_center_x_spin.setValue(polygon.center.x())
        self.polygon_center_y_spin.setValue(polygon.center.y())
        self.polygon_radius_spin.setValue(polygon.radius)
        self.polygon_num_vertices_spin.setValue(polygon.num_vertices)
        
        if polygon.construction_type == "circumscribed":
            self.polygon_construction_combo.setCurrentIndex(1)
        else:
            self.polygon_construction_combo.setCurrentIndex(0)
        
        self.polygon_center_x_spin.blockSignals(False)
        self.polygon_center_y_spin.blockSignals(False)
        self.polygon_center_x_spin.blockSignals(False)
        self.polygon_center_y_spin.blockSignals(False)
        self.polygon_radius_spin.blockSignals(False)
        self.polygon_num_vertices_spin.blockSignals(False)
        self.polygon_construction_combo.blockSignals(False)
        
        self.apply_changes()
    
    def on_polygon_center_changed(self):
        """Обработчик изменения центра многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        polygon = self.editing_object
        polygon.center = QPointF(self.polygon_center_x_spin.value(), self.polygon_center_y_spin.value())
        self.apply_changes()
    
    def on_polygon_center_changed(self):
        """Обработчик изменения центра многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        polygon = self.editing_object
        polygon.center = QPointF(self.polygon_center_x_spin.value(), self.polygon_center_y_spin.value())
        self.apply_changes()
    
    def on_polygon_construction_changed(self):
        """Обработчик изменения варианта построения многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        import math
        polygon = self.editing_object
        old_type = polygon.construction_type
        new_type = "circumscribed" if self.polygon_construction_combo.currentIndex() == 1 else "inscribed"
        
        if old_type != new_type:
            # Пересчитываем радиус при смене типа построения
            # Чтобы многоугольник визуально оставался примерно того же размера
            if old_type == "inscribed" and new_type == "circumscribed":
                # Было вписанный, стало описанный
                # R -> r: r = R * cos(π/n)
                if polygon.num_vertices > 2:
                    polygon.radius = polygon.radius * math.cos(math.pi / polygon.num_vertices)
            elif old_type == "circumscribed" and new_type == "inscribed":
                # Было описанный, стало вписанный
                # r -> R: R = r / cos(π/n)
                if polygon.num_vertices > 2:
                    polygon.radius = polygon.radius / math.cos(math.pi / polygon.num_vertices)
            
            polygon.construction_type = new_type
            self.update_polygon_input_fields()
    
    def on_polygon_radius_changed(self):
        """Обработчик изменения радиуса многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        polygon = self.editing_object
        polygon.radius = self.polygon_radius_spin.value()
        self.apply_changes()
    
    def on_polygon_num_vertices_changed(self):
        """Обработчик изменения количества углов многоугольника"""
        if not isinstance(self.editing_object, Polygon):
            return
        
        polygon = self.editing_object
        new_num_vertices = self.polygon_num_vertices_spin.value()
        
        # При изменении количества вершин может потребоваться пересчет радиуса
        # для описанного многоугольника, чтобы сохранить визуальный размер
        if polygon.construction_type == "circumscribed" and polygon.num_vertices != new_num_vertices:
            import math
            # Пересчитываем радиус для нового количества вершин
            # Сохраняем визуальный размер описанной окружности
            if polygon.num_vertices > 2 and new_num_vertices > 2:
                # Конвертируем в радиус описанной окружности
                R_old = polygon.radius / math.cos(math.pi / polygon.num_vertices)
                # Конвертируем обратно в радиус вписанной для нового количества вершин
                polygon.radius = R_old * math.cos(math.pi / new_num_vertices)
        
        polygon.num_vertices = new_num_vertices
        self.update_polygon_input_fields()
    
    def setup_spline_editing(self, spline):
        """Настройка интерфейса редактирования сплайна"""
        self.title_label.setText("Редактирование сплайна")
        
        # Группа для информации
        info_group = QGroupBox("Информация")
        info_layout = QVBoxLayout()
        info_label = QLabel(f"Количество контрольных точек: {len(spline.control_points)}")
        info_layout.addWidget(info_label)
        self.spline_info_label = info_label
        info_group.setLayout(info_layout)
        self.content_layout.addWidget(info_group)
        
        # Группа для управления точками
        control_group = QGroupBox("Управление точками")
        control_layout = QVBoxLayout()
        
        buttons_layout = QHBoxLayout()
        self.add_point_btn = QPushButton("Добавить точку")
        self.add_point_btn.clicked.connect(self.on_spline_add_point)
        buttons_layout.addWidget(self.add_point_btn)
        
        self.delete_point_btn = QPushButton("Удалить выбранную точку")
        self.delete_point_btn.clicked.connect(self.on_spline_delete_point)
        self.delete_point_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_point_btn)
        
        control_layout.addLayout(buttons_layout)
        
        # Информация о выбранной точке
        self.selected_point_label = QLabel("Выбранная точка: нет")
        self.selected_point_label.setStyleSheet("color: #666; font-size: 9pt;")
        control_layout.addWidget(self.selected_point_label)
        
        info_text = QLabel("Для выбора точки кликните по ней правой кнопкой мыши.\nДля добавления точки кликните по сплайну в нужном месте.")
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #666; font-size: 9pt;")
        control_layout.addWidget(info_text)
        
        control_group.setLayout(control_layout)
        self.content_layout.addWidget(control_group)
        
        # Инициализируем выбранную точку
        self.selected_point_index = None
        
        # Режим редактирования
        edit_mode_group = QGroupBox("Режим редактирования")
        edit_mode_layout = QVBoxLayout()
        
        self.toggle_edit_mode_btn = QPushButton("Включить редактирование")
        self.toggle_edit_mode_btn.clicked.connect(self.toggle_edit_mode)
        edit_mode_layout.addWidget(self.toggle_edit_mode_btn)
        
        self.edit_mode_label = QLabel("Перемещение точек: Отключено")
        self.edit_mode_label.setStyleSheet("color: gray;")
        edit_mode_layout.addWidget(self.edit_mode_label)
        
        info_label = QLabel("Включите режим редактирования для:\n• Перемещения контрольных точек (цветные точки) - левый клик и перетаскивание\n• Добавления новых точек - левый клик по сплайну в нужном месте\n• Выбора точки для удаления - правый клик по точке")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        edit_mode_layout.addWidget(info_label)
        
        edit_mode_group.setLayout(edit_mode_layout)
        self.content_layout.addWidget(edit_mode_group)
        
        # Инициализируем выбранную точку
        self.selected_point_index = None
        
        self.update_spline_info()
    
    def update_spline_info(self):
        """Обновляет информацию о сплайне"""
        if not isinstance(self.editing_object, Spline):
            return
        
        spline = self.editing_object
        if hasattr(self, 'spline_info_label'):
            self.spline_info_label.setText(f"Количество контрольных точек: {len(spline.control_points)}")
        
        # Обновляем информацию о выбранной точке
        if hasattr(self, 'selected_point_label'):
            if self.selected_point_index is not None and 0 <= self.selected_point_index < len(spline.control_points):
                point = spline.control_points[self.selected_point_index]
                self.selected_point_label.setText(f"Выбранная точка: {self.selected_point_index + 1} (x={point.x():.2f}, y={point.y():.2f})")
                if hasattr(self, 'delete_point_btn'):
                    self.delete_point_btn.setEnabled(True)
            else:
                self.selected_point_label.setText("Выбранная точка: нет")
                if hasattr(self, 'delete_point_btn'):
                    self.delete_point_btn.setEnabled(False)
                self.selected_point_index = None
    
    def set_selected_spline_point(self, point_index):
        """Устанавливает выбранную точку сплайна"""
        if not isinstance(self.editing_object, Spline):
            return
        
        spline = self.editing_object
        if 0 <= point_index < len(spline.control_points):
            self.selected_point_index = point_index
            self.update_spline_info()
    
    def on_spline_add_point(self):
        """Добавляет новую контрольную точку в конец сплайна"""
        if not isinstance(self.editing_object, Spline):
            return
        
        spline = self.editing_object
        if len(spline.control_points) > 0:
            # Добавляем точку рядом с последней точкой
            last_point = spline.control_points[-1]
            new_point = QPointF(last_point.x() + 20, last_point.y() + 20)
        else:
            # Если точек нет, добавляем в центр экрана
            new_point = QPointF(0, 0)
        
        spline.control_points.append(new_point)
        self.update_spline_info()
        self.apply_changes()
    
    def on_spline_delete_point(self):
        """Удаляет выбранную контрольную точку сплайна"""
        if not isinstance(self.editing_object, Spline):
            return
        
        spline = self.editing_object
        if len(spline.control_points) <= 2:
            QMessageBox.warning(self, "Удаление точки", 
                              "Сплайн должен содержать минимум 2 контрольные точки.")
            return
        
        if self.selected_point_index is not None and 0 <= self.selected_point_index < len(spline.control_points):
            # Удаляем выбранную точку
            spline.control_points.pop(self.selected_point_index)
            self.selected_point_index = None
            self.update_spline_info()
            self.apply_changes()
        else:
            QMessageBox.warning(self, "Удаление точки", 
                              "Пожалуйста, выберите точку для удаления (правый клик по точке).")
    
    def _save_object_state(self, obj):
        """Сохраняет исходное состояние объекта для отмены изменений"""
        if obj is None:
            return None
        
        from PySide6.QtCore import QPointF
        from widgets.primitives import Circle, Rectangle
        
        state = {}
        state['type'] = type(obj).__name__
        
        if isinstance(obj, LineSegment):
            state['start_point'] = QPointF(obj.start_point)
            state['end_point'] = QPointF(obj.end_point)
        elif isinstance(obj, Circle):
            state['center'] = QPointF(obj.center)
            state['radius'] = obj.radius
        elif isinstance(obj, Rectangle):
            state['top_left'] = QPointF(obj.top_left)
            state['bottom_right'] = QPointF(obj.bottom_right)
            state['fillet_radius'] = obj.fillet_radius
        elif isinstance(obj, Arc):
            state['center'] = QPointF(obj.center)
            state['radius'] = obj.radius
            state['start_angle'] = obj.start_angle
            state['end_angle'] = obj.end_angle
        elif isinstance(obj, Ellipse):
            state['center'] = QPointF(obj.center)
            state['radius_x'] = obj.radius_x
            state['radius_y'] = obj.radius_y
        elif isinstance(obj, Polygon):
            state['center'] = QPointF(obj.center)
            state['radius'] = obj.radius
            state['num_vertices'] = obj.num_vertices
            state['construction_type'] = obj.construction_type
        elif isinstance(obj, Spline):
            state['control_points'] = [QPointF(p) for p in obj.control_points]
        
        return state
    
    def _restore_object_state(self, obj, state):
        """Восстанавливает исходное состояние объекта"""
        if obj is None or state is None:
            return
        
        from widgets.primitives import Circle, Rectangle
        
        if isinstance(obj, LineSegment):
            obj.start_point = state['start_point']
            obj.end_point = state['end_point']
        elif isinstance(obj, Circle):
            obj.center = state['center']
            obj.radius = state['radius']
        elif isinstance(obj, Rectangle):
            obj.top_left = state['top_left']
            obj.bottom_right = state['bottom_right']
            obj.fillet_radius = state['fillet_radius']
        elif isinstance(obj, Arc):
            obj.center = state['center']
            obj.radius = state['radius']
            obj.start_angle = state['start_angle']
            obj.end_angle = state['end_angle']
        elif isinstance(obj, Ellipse):
            obj.center = state['center']
            obj.radius_x = state['radius_x']
            obj.radius_y = state['radius_y']
        elif isinstance(obj, Polygon):
            obj.center = state['center']
            obj.radius = state['radius']
            obj.num_vertices = state['num_vertices']
            obj.construction_type = state['construction_type']
        elif isinstance(obj, Spline):
            obj.control_points = [QPointF(p) for p in state['control_points']]
    
    def cancel_changes(self):
        """Отменяет все изменения и восстанавливает исходное состояние объекта"""
        if self.editing_object is None or self.original_state is None:
            return
        
        from widgets.primitives import Circle, Rectangle
        
        # Восстанавливаем исходное состояние
        self._restore_object_state(self.editing_object, self.original_state)
        
        # Обновляем поля ввода в зависимости от типа объекта
        if isinstance(self.editing_object, LineSegment):
            self.load_line_data(self.editing_object)
        elif isinstance(self.editing_object, Circle):
            self.load_circle_data(self.editing_object)
        elif isinstance(self.editing_object, Rectangle):
            self.load_rectangle_data(self.editing_object)
        elif isinstance(self.editing_object, Arc):
            self.update_arc_input_fields()
        elif isinstance(self.editing_object, Ellipse):
            self.update_ellipse_input_fields()
        elif isinstance(self.editing_object, Polygon):
            self.update_polygon_input_fields()
        elif isinstance(self.editing_object, Spline):
            self.update_spline_info()
        
        # Обновляем канвас
        if self.canvas:
            self.canvas.update()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Отключаем режим редактирования при закрытии
        if self.editing_mode and self.canvas:
            self.editing_mode = False
            self.canvas.set_editing_mode(False, None)
            self.dragging_point = None
        super().closeEvent(event)

