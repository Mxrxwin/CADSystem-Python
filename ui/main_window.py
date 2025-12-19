import sys
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QComboBox, QDoubleSpinBox, QGroupBox,
                               QGridLayout, QSpinBox, QColorDialog, QMessageBox, QToolBar,
                               QStatusBar, QMenu, QSizePolicy, QSplitter, QScrollArea,
                               QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import QPointF, Qt, QSize, QRectF
from PySide6.QtGui import QColor, QAction, QIcon, QKeySequence, QPixmap, QPainter, QPen

from widgets.coordinate_system import CoordinateSystemWidget
from widgets.line_style import LineStyleManager
from ui.style_panels import ObjectPropertiesPanel, StyleManagementPanel, StyleComboBox
from ui.edit_dialog import EditDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Построение отрезков в различных системах координат")
        self.setGeometry(100, 100, 1200, 800)
        
        self.coordinate_system = "cartesian"  # "cartesian" или "polar" (для обратной совместимости)
        self.angle_units = "degrees"  # "degrees" или "radians" (для обратной совместимости)
        
        # Система координат и единицы углов для отрезка
        self.line_coordinate_system = "cartesian"  # "cartesian" или "polar"
        self.line_angle_units = "degrees"  # "degrees" или "radians"
        
        # Создаем менеджер стилей
        self.style_manager = LineStyleManager()
        
        # сначала создаем canvas
        self.canvas = CoordinateSystemWidget(style_manager=self.style_manager)
        
        # Выделенные объекты
        self.selected_objects = []
        
        self.init_ui()
        
        # Окно редактирования (создаем после init_ui, чтобы canvas был готов)
        self.edit_dialog = EditDialog(self)
        self.edit_dialog.set_canvas(self.canvas)
        # Подключаем сигнал об изменении объекта для обновления панели информации
        self.edit_dialog.object_changed.connect(self.on_object_edited)
        # Отслеживаем закрытие диалога для обновления информации
        self.edit_dialog.finished.connect(self.on_edit_dialog_closed)
        
        # Явно вызываем change_primitive_type для показа виджета способа задания отрезка
        # (поскольку "Отрезок" выбран по умолчанию, сигнал currentTextChanged не сработает)
        if hasattr(self, 'primitive_combo'):
            self.change_primitive_type(self.primitive_combo.currentText())
        self.update_info()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # меню
        self.create_menus()
        
        # панель инструментов
        self.create_toolbar()
        
        # панель инструментов стилей
        self.create_style_toolbar()
        
        # строка состояния
        self.create_statusbar()
        
        # Используем Splitter для разделения панелей
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель с настройками
        left_widget = QWidget()
        left_panel = QVBoxLayout(left_widget)
        left_panel.setSpacing(10)
        
        # Обёртка в скролл для левой панели
        scroll_area = QScrollArea()
        scroll_area.setWidget(left_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # панель инструментов
        tools_group = QGroupBox("Инструменты")
        tools_layout = QVBoxLayout()
        
        # Выбор типа примитива
        primitive_layout = QHBoxLayout()
        primitive_layout.addWidget(QLabel("Тип примитива:"))
        self.primitive_combo = QComboBox()
        
        # Добавляем примитивы с иконками
        primitives = ["Отрезок", "Окружность", "Дуга", "Прямоугольник", "Эллипс", "Многоугольник", "Сплайн"]
        for primitive in primitives:
            icon = self._create_primitive_icon(primitive)
            self.primitive_combo.addItem(icon, primitive)
        
        self.primitive_combo.currentTextChanged.connect(self.change_primitive_type)
        primitive_layout.addWidget(self.primitive_combo)
        tools_layout.addLayout(primitive_layout)
        
        # Выбор способа задания отрезка (скрыто по умолчанию)
        line_method_layout = QVBoxLayout()
        line_method_layout.addWidget(QLabel("Способ задания:"))
        self.line_method_combo = QComboBox()
        self.line_method_combo.addItems([
            "В декартовых координатах (x₁, y₁) и (x₂, y₂)",
            "В полярных координатах (x₁, y₁) и (r₂, θ₂)"
        ])
        self.line_method_combo.currentTextChanged.connect(self.change_line_method)
        line_method_layout.addWidget(self.line_method_combo)
        
        # Система координат и единицы углов для отрезка
        line_coord_layout = QHBoxLayout()
        line_coord_layout.addWidget(QLabel("Система координат:"))
        self.line_coord_combo = QComboBox()
        self.line_coord_combo.addItems(["Декартова", "Полярная"])
        self.line_coord_combo.currentTextChanged.connect(self.change_line_coordinate_system)
        line_coord_layout.addWidget(self.line_coord_combo)
        line_method_layout.addLayout(line_coord_layout)
        
        line_angle_layout = QHBoxLayout()
        line_angle_layout.addWidget(QLabel("Единицы углов:"))
        self.line_angle_combo = QComboBox()
        self.line_angle_combo.addItems(["Градусы", "Радианы"])
        self.line_angle_combo.currentTextChanged.connect(self.change_line_angle_units)
        line_angle_layout.addWidget(self.line_angle_combo)
        line_method_layout.addLayout(line_angle_layout)
        
        self.line_method_widget = QWidget()
        self.line_method_widget.setLayout(line_method_layout)
        self.line_method_widget.hide()
        tools_layout.addWidget(self.line_method_widget)
        
        # Выбор метода создания окружности (скрыто по умолчанию)
        circle_method_layout = QHBoxLayout()
        circle_method_layout.addWidget(QLabel("Способ создания:"))
        self.circle_method_combo = QComboBox()
        self.circle_method_combo.addItems([
            "Центр и радиус",
            "Центр и диаметр",
            "Две точки",
            "Три точки на окружности"
        ])
        self.circle_method_combo.currentTextChanged.connect(self.change_circle_method)
        circle_method_layout.addWidget(self.circle_method_combo)
        self.circle_method_widget = QWidget()
        self.circle_method_widget.setLayout(circle_method_layout)
        self.circle_method_widget.hide()
        tools_layout.addWidget(self.circle_method_widget)
        
        # Выбор метода создания дуги (скрыто по умолчанию)
        arc_method_layout = QHBoxLayout()
        arc_method_layout.addWidget(QLabel("Способ создания:"))
        self.arc_method_combo = QComboBox()
        self.arc_method_combo.addItems([
            "Три точки (начало, вторая точка, конец)",
            "Центр, начальный угол, конечный угол"
        ])
        self.arc_method_combo.currentTextChanged.connect(self.change_arc_method)
        arc_method_layout.addWidget(self.arc_method_combo)
        self.arc_method_widget = QWidget()
        self.arc_method_widget.setLayout(arc_method_layout)
        self.arc_method_widget.hide()
        tools_layout.addWidget(self.arc_method_widget)
        
        # Выбор метода создания прямоугольника (скрыто по умолчанию)
        rectangle_method_layout = QHBoxLayout()
        rectangle_method_layout.addWidget(QLabel("Способ создания:"))
        self.rectangle_method_combo = QComboBox()
        self.rectangle_method_combo.addItems([
            "Две противоположные точки",
            "Одна точка, ширина и высота",
            "Центр, ширина и высота",
            "С фасками/скруглениями при создании"
        ])
        self.rectangle_method_combo.currentTextChanged.connect(self.change_rectangle_method)
        rectangle_method_layout.addWidget(self.rectangle_method_combo)
        self.rectangle_method_widget = QWidget()
        self.rectangle_method_widget.setLayout(rectangle_method_layout)
        self.rectangle_method_widget.hide()
        tools_layout.addWidget(self.rectangle_method_widget)
        
        # Выбор метода создания эллипса (скрыто по умолчанию)
        ellipse_method_layout = QHBoxLayout()
        ellipse_method_layout.addWidget(QLabel("Способ создания:"))
        self.ellipse_method_combo = QComboBox()
        self.ellipse_method_combo.addItems([
            "Центр и радиусы",
            "Три точки на эллипсе"
        ])
        self.ellipse_method_combo.currentTextChanged.connect(self.change_ellipse_method)
        ellipse_method_layout.addWidget(self.ellipse_method_combo)
        self.ellipse_method_widget = QWidget()
        self.ellipse_method_widget.setLayout(ellipse_method_layout)
        self.ellipse_method_widget.hide()
        tools_layout.addWidget(self.ellipse_method_widget)

        self.delete_last_btn = QPushButton("Удалить последний")
        self.delete_last_btn.clicked.connect(self.delete_last_line)

        self.delete_all_btn = QPushButton("Удалить все")
        self.delete_all_btn.clicked.connect(self.delete_all_lines)
        
        self.delete_selected_btn = QPushButton("Удалить выбранное")
        self.delete_selected_btn.clicked.connect(self.delete_selected_objects)
        self.delete_selected_btn.setEnabled(False)  # По умолчанию отключена, пока нет выделения

        tools_layout.addWidget(self.delete_last_btn)
        tools_layout.addWidget(self.delete_all_btn)
        tools_layout.addWidget(self.delete_selected_btn)
        
        # Группы для сплайна (добавляем в tools_group, чтобы не скрывалась с input_group)
        self.spline_control_points_group = QWidget()
        spline_cp_layout = QVBoxLayout()
        spline_info_label = QLabel("Кликните левой кнопкой мыши для добавления контрольных точек.\nДвойной клик завершает создание сплайна.")
        spline_info_label.setWordWrap(True)
        spline_cp_layout.addWidget(spline_info_label)
        self.spline_control_points_group.setLayout(spline_cp_layout)
        self.spline_control_points_group.hide()
        tools_layout.addWidget(self.spline_control_points_group)
        
        tools_group.setLayout(tools_layout)
        left_panel.addWidget(tools_group)
        
        # панель ввода координат
        self.input_group = QGroupBox("Ввод координат")
        input_layout = QGridLayout()
        
        # начальная точка (всегда в декартовых координатах)
        self.start_point_label_widget = QLabel("Начальная точка (x, y):")
        input_layout.addWidget(self.start_point_label_widget, 0, 0)
        self.start_x_spin = QDoubleSpinBox()
        self.start_x_spin.setRange(-1000, 1000)
        self.start_x_spin.setDecimals(2)
        self.start_x_spin.setSingleStep(10)
        self.start_x_spin.valueChanged.connect(self.on_start_coordinates_changed)
        
        self.start_y_spin = QDoubleSpinBox()
        self.start_y_spin.setRange(-1000, 1000)
        self.start_y_spin.setDecimals(2)
        self.start_y_spin.setSingleStep(10)
        self.start_y_spin.valueChanged.connect(self.on_start_coordinates_changed)
        
        input_layout.addWidget(QLabel("x:"), 0, 1)
        input_layout.addWidget(self.start_x_spin, 0, 2)
        input_layout.addWidget(QLabel("y:"), 0, 3)
        input_layout.addWidget(self.start_y_spin, 0, 4)
        
        # конечная точка (зависит от системы координат)
        self.end_point_label_widget = QLabel("Конечная точка:")
        input_layout.addWidget(self.end_point_label_widget, 1, 0)
        
        # декартовы координаты
        self.cartesian_group = QWidget()
        cartesian_layout = QHBoxLayout()
        self.end_x_spin = QDoubleSpinBox()
        self.end_x_spin.setRange(-1000, 1000)
        self.end_x_spin.setDecimals(2)
        self.end_x_spin.setSingleStep(10)
        self.end_x_spin.valueChanged.connect(self.on_coordinates_changed)
        
        self.end_y_spin = QDoubleSpinBox()
        self.end_y_spin.setRange(-1000, 1000)
        self.end_y_spin.setDecimals(2)
        self.end_y_spin.setSingleStep(10)
        self.end_y_spin.valueChanged.connect(self.on_coordinates_changed)
        
        cartesian_layout.addWidget(QLabel("x:"))
        cartesian_layout.addWidget(self.end_x_spin)
        cartesian_layout.addWidget(QLabel("y:"))
        cartesian_layout.addWidget(self.end_y_spin)
        self.cartesian_group.setLayout(cartesian_layout)
        
        # полярные координаты
        self.polar_group = QWidget()
        polar_layout = QHBoxLayout()
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0, 1000)
        self.radius_spin.setDecimals(2)
        self.radius_spin.setSingleStep(10)
        self.radius_spin.valueChanged.connect(self.on_polar_changed)
        
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-360, 360)
        self.angle_spin.setDecimals(2)
        self.angle_spin.setSingleStep(15)
        self.angle_spin.valueChanged.connect(self.on_polar_changed)
        
        self.angle_label = QLabel("°" if self.line_angle_units == "degrees" else "rad")
        
        polar_layout.addWidget(QLabel("r:"))
        polar_layout.addWidget(self.radius_spin)
        polar_layout.addWidget(QLabel("θ:"))
        polar_layout.addWidget(self.angle_spin)
        polar_layout.addWidget(self.angle_label)
        self.polar_group.setLayout(polar_layout)
        self.polar_group.hide()
        
        # Группы для окружности
        # Центр и радиус
        self.circle_center_radius_group = QWidget()
        circle_cr_layout = QHBoxLayout()
        circle_cr_layout.addWidget(QLabel("Радиус:"))
        self.circle_radius_spin = QDoubleSpinBox()
        self.circle_radius_spin.setRange(0, 1000)
        self.circle_radius_spin.setDecimals(2)
        self.circle_radius_spin.setSingleStep(10)
        self.circle_radius_spin.setValue(50)
        self.circle_radius_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        circle_cr_layout.addWidget(self.circle_radius_spin)
        self.circle_center_radius_group.setLayout(circle_cr_layout)
        self.circle_center_radius_group.hide()
        
        # Центр и диаметр
        self.circle_center_diameter_group = QWidget()
        circle_cd_layout = QHBoxLayout()
        circle_cd_layout.addWidget(QLabel("Диаметр:"))
        self.circle_diameter_spin = QDoubleSpinBox()
        self.circle_diameter_spin.setRange(0, 1000)
        self.circle_diameter_spin.setDecimals(2)
        self.circle_diameter_spin.setSingleStep(10)
        self.circle_diameter_spin.setValue(100)
        self.circle_diameter_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        circle_cd_layout.addWidget(self.circle_diameter_spin)
        self.circle_center_diameter_group.setLayout(circle_cd_layout)
        self.circle_center_diameter_group.hide()
        
        # Две точки
        self.circle_two_points_group = QWidget()
        circle_2p_layout = QGridLayout()
        circle_2p_layout.addWidget(QLabel("Вторая точка:"), 0, 0)
        self.circle_point2_x_spin = QDoubleSpinBox()
        self.circle_point2_x_spin.setRange(-1000, 1000)
        self.circle_point2_x_spin.setDecimals(2)
        self.circle_point2_x_spin.setSingleStep(10)
        self.circle_point2_x_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        self.circle_point2_y_spin = QDoubleSpinBox()
        self.circle_point2_y_spin.setRange(-1000, 1000)
        self.circle_point2_y_spin.setDecimals(2)
        self.circle_point2_y_spin.setSingleStep(10)
        self.circle_point2_y_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        circle_2p_layout.addWidget(QLabel("x:"), 0, 1)
        circle_2p_layout.addWidget(self.circle_point2_x_spin, 0, 2)
        circle_2p_layout.addWidget(QLabel("y:"), 0, 3)
        circle_2p_layout.addWidget(self.circle_point2_y_spin, 0, 4)
        self.circle_two_points_group.setLayout(circle_2p_layout)
        self.circle_two_points_group.hide()
        
        # Три точки
        self.circle_three_points_group = QWidget()
        circle_3p_layout = QGridLayout()
        circle_3p_layout.addWidget(QLabel("Вторая точка:"), 0, 0)
        self.circle_point2_x_spin_3p = QDoubleSpinBox()
        self.circle_point2_x_spin_3p.setRange(-1000, 1000)
        self.circle_point2_x_spin_3p.setDecimals(2)
        self.circle_point2_x_spin_3p.setSingleStep(10)
        self.circle_point2_x_spin_3p.valueChanged.connect(self.on_circle_coordinates_changed)
        self.circle_point2_y_spin_3p = QDoubleSpinBox()
        self.circle_point2_y_spin_3p.setRange(-1000, 1000)
        self.circle_point2_y_spin_3p.setDecimals(2)
        self.circle_point2_y_spin_3p.setSingleStep(10)
        self.circle_point2_y_spin_3p.valueChanged.connect(self.on_circle_coordinates_changed)
        circle_3p_layout.addWidget(QLabel("x:"), 0, 1)
        circle_3p_layout.addWidget(self.circle_point2_x_spin_3p, 0, 2)
        circle_3p_layout.addWidget(QLabel("y:"), 0, 3)
        circle_3p_layout.addWidget(self.circle_point2_y_spin_3p, 0, 4)
        
        circle_3p_layout.addWidget(QLabel("Третья точка:"), 1, 0)
        self.circle_point3_x_spin = QDoubleSpinBox()
        self.circle_point3_x_spin.setRange(-1000, 1000)
        self.circle_point3_x_spin.setDecimals(2)
        self.circle_point3_x_spin.setSingleStep(10)
        self.circle_point3_x_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        self.circle_point3_y_spin = QDoubleSpinBox()
        self.circle_point3_y_spin.setRange(-1000, 1000)
        self.circle_point3_y_spin.setDecimals(2)
        self.circle_point3_y_spin.setSingleStep(10)
        self.circle_point3_y_spin.valueChanged.connect(self.on_circle_coordinates_changed)
        circle_3p_layout.addWidget(QLabel("x:"), 1, 1)
        circle_3p_layout.addWidget(self.circle_point3_x_spin, 1, 2)
        circle_3p_layout.addWidget(QLabel("y:"), 1, 3)
        circle_3p_layout.addWidget(self.circle_point3_y_spin, 1, 4)
        self.circle_three_points_group.setLayout(circle_3p_layout)
        self.circle_three_points_group.hide()
        
        # Группы для дуги
        # Три точки
        self.arc_three_points_group = QWidget()
        arc_3p_layout = QGridLayout()
        arc_3p_layout.addWidget(QLabel("Вторая точка:"), 0, 0)
        self.arc_point2_x_spin = QDoubleSpinBox()
        self.arc_point2_x_spin.setRange(-1000, 1000)
        self.arc_point2_x_spin.setDecimals(2)
        self.arc_point2_x_spin.setSingleStep(10)
        self.arc_point2_x_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        self.arc_point2_y_spin = QDoubleSpinBox()
        self.arc_point2_y_spin.setRange(-1000, 1000)
        self.arc_point2_y_spin.setDecimals(2)
        self.arc_point2_y_spin.setSingleStep(10)
        self.arc_point2_y_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        arc_3p_layout.addWidget(QLabel("x:"), 0, 1)
        arc_3p_layout.addWidget(self.arc_point2_x_spin, 0, 2)
        arc_3p_layout.addWidget(QLabel("y:"), 0, 3)
        arc_3p_layout.addWidget(self.arc_point2_y_spin, 0, 4)
        
        arc_3p_layout.addWidget(QLabel("Третья точка:"), 1, 0)
        self.arc_point3_x_spin = QDoubleSpinBox()
        self.arc_point3_x_spin.setRange(-1000, 1000)
        self.arc_point3_x_spin.setDecimals(2)
        self.arc_point3_x_spin.setSingleStep(10)
        self.arc_point3_x_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        self.arc_point3_y_spin = QDoubleSpinBox()
        self.arc_point3_y_spin.setRange(-1000, 1000)
        self.arc_point3_y_spin.setDecimals(2)
        self.arc_point3_y_spin.setSingleStep(10)
        self.arc_point3_y_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        arc_3p_layout.addWidget(QLabel("x:"), 1, 1)
        arc_3p_layout.addWidget(self.arc_point3_x_spin, 1, 2)
        arc_3p_layout.addWidget(QLabel("y:"), 1, 3)
        arc_3p_layout.addWidget(self.arc_point3_y_spin, 1, 4)
        self.arc_three_points_group.setLayout(arc_3p_layout)
        self.arc_three_points_group.hide()
        
        # Центр, начальный угол, конечный угол
        self.arc_center_angles_group = QWidget()
        arc_ca_layout = QGridLayout()
        arc_ca_layout.addWidget(QLabel("Радиус:"), 0, 0)
        self.arc_radius_spin = QDoubleSpinBox()
        self.arc_radius_spin.setRange(0, 1000)
        self.arc_radius_spin.setDecimals(2)
        self.arc_radius_spin.setSingleStep(10)
        self.arc_radius_spin.setValue(50)
        self.arc_radius_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        arc_ca_layout.addWidget(self.arc_radius_spin, 0, 1, 1, 4)
        
        arc_ca_layout.addWidget(QLabel("Начальный угол:"), 1, 0)
        self.arc_start_angle_spin = QDoubleSpinBox()
        self.arc_start_angle_spin.setRange(-360, 360)
        self.arc_start_angle_spin.setDecimals(2)
        self.arc_start_angle_spin.setSingleStep(15)
        self.arc_start_angle_spin.setValue(0)
        self.arc_start_angle_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        arc_ca_layout.addWidget(self.arc_start_angle_spin, 1, 1, 1, 2)
        arc_ca_layout.addWidget(QLabel("°"), 1, 3)
        
        arc_ca_layout.addWidget(QLabel("Конечный угол:"), 2, 0)
        self.arc_end_angle_spin = QDoubleSpinBox()
        self.arc_end_angle_spin.setRange(-360, 360)
        self.arc_end_angle_spin.setDecimals(2)
        self.arc_end_angle_spin.setSingleStep(15)
        self.arc_end_angle_spin.setValue(90)
        self.arc_end_angle_spin.valueChanged.connect(self.on_arc_coordinates_changed)
        arc_ca_layout.addWidget(self.arc_end_angle_spin, 2, 1, 1, 2)
        arc_ca_layout.addWidget(QLabel("°"), 2, 3)
        self.arc_center_angles_group.setLayout(arc_ca_layout)
        self.arc_center_angles_group.hide()
        
        # Добавляем все виджеты в одну ячейку GridLayout
        # Они будут показываться/скрываться по необходимости
        input_layout.addWidget(self.cartesian_group, 1, 1, 1, 4)
        input_layout.addWidget(self.polar_group, 1, 1, 1, 4)
        input_layout.addWidget(self.circle_center_radius_group, 1, 1, 1, 4)
        input_layout.addWidget(self.circle_center_diameter_group, 1, 1, 1, 4)
        input_layout.addWidget(self.circle_two_points_group, 1, 1, 1, 4)
        input_layout.addWidget(self.circle_three_points_group, 1, 1, 2, 4)
        input_layout.addWidget(self.arc_three_points_group, 1, 1, 2, 4)
        input_layout.addWidget(self.arc_center_angles_group, 1, 1, 3, 4)
        
        # Группы для прямоугольника
        # Две противоположные точки (используем существующие поля end_x_spin и end_y_spin)
        # Одна точка, ширина и высота
        self.rectangle_point_size_group = QWidget()
        rect_ps_layout = QGridLayout()
        rect_ps_layout.addWidget(QLabel("Ширина:"), 0, 0)
        self.rectangle_width_spin = QDoubleSpinBox()
        self.rectangle_width_spin.setRange(0, 1000)
        self.rectangle_width_spin.setDecimals(2)
        self.rectangle_width_spin.setSingleStep(10)
        self.rectangle_width_spin.setValue(100)
        self.rectangle_width_spin.valueChanged.connect(self.on_rectangle_coordinates_changed)
        rect_ps_layout.addWidget(self.rectangle_width_spin, 0, 1, 1, 4)
        
        rect_ps_layout.addWidget(QLabel("Высота:"), 1, 0)
        self.rectangle_height_spin = QDoubleSpinBox()
        self.rectangle_height_spin.setRange(0, 1000)
        self.rectangle_height_spin.setDecimals(2)
        self.rectangle_height_spin.setSingleStep(10)
        self.rectangle_height_spin.setValue(100)
        self.rectangle_height_spin.valueChanged.connect(self.on_rectangle_coordinates_changed)
        rect_ps_layout.addWidget(self.rectangle_height_spin, 1, 1, 1, 4)
        self.rectangle_point_size_group.setLayout(rect_ps_layout)
        self.rectangle_point_size_group.hide()
        
        # Центр, ширина и высота
        self.rectangle_center_size_group = QWidget()
        rect_cs_layout = QGridLayout()
        rect_cs_layout.addWidget(QLabel("Ширина:"), 0, 0)
        self.rectangle_center_width_spin = QDoubleSpinBox()
        self.rectangle_center_width_spin.setRange(0, 1000)
        self.rectangle_center_width_spin.setDecimals(2)
        self.rectangle_center_width_spin.setSingleStep(10)
        self.rectangle_center_width_spin.setValue(100)
        self.rectangle_center_width_spin.valueChanged.connect(self.on_rectangle_coordinates_changed)
        rect_cs_layout.addWidget(self.rectangle_center_width_spin, 0, 1, 1, 4)
        
        rect_cs_layout.addWidget(QLabel("Высота:"), 1, 0)
        self.rectangle_center_height_spin = QDoubleSpinBox()
        self.rectangle_center_height_spin.setRange(0, 1000)
        self.rectangle_center_height_spin.setDecimals(2)
        self.rectangle_center_height_spin.setSingleStep(10)
        self.rectangle_center_height_spin.setValue(100)
        self.rectangle_center_height_spin.valueChanged.connect(self.on_rectangle_coordinates_changed)
        rect_cs_layout.addWidget(self.rectangle_center_height_spin, 1, 1, 1, 4)
        self.rectangle_center_size_group.setLayout(rect_cs_layout)
        self.rectangle_center_size_group.hide()
        
        # С фасками/скруглениями (только радиус, вторая точка вводится через cartesian_group/polar_group)
        self.rectangle_fillets_group = QWidget()
        rect_fill_layout = QHBoxLayout()
        rect_fill_layout.addWidget(QLabel("Радиус скругления:"))
        self.rectangle_fillet_radius_spin = QDoubleSpinBox()
        self.rectangle_fillet_radius_spin.setRange(0, 1000)
        self.rectangle_fillet_radius_spin.setDecimals(2)
        self.rectangle_fillet_radius_spin.setSingleStep(5)
        self.rectangle_fillet_radius_spin.setValue(10)
        self.rectangle_fillet_radius_spin.valueChanged.connect(self.on_rectangle_coordinates_changed)
        rect_fill_layout.addWidget(self.rectangle_fillet_radius_spin)
        self.rectangle_fillets_group.setLayout(rect_fill_layout)
        self.rectangle_fillets_group.hide()
        
        # Добавляем группы прямоугольника в GridLayout
        input_layout.addWidget(self.rectangle_point_size_group, 1, 1, 2, 4)
        input_layout.addWidget(self.rectangle_center_size_group, 1, 1, 2, 4)
        # rectangle_fillets_group размещаем на следующей строке после cartesian_group/polar_group
        input_layout.addWidget(self.rectangle_fillets_group, 2, 1, 1, 4)
        
        # Группы для эллипса
        # Центр и радиусы
        self.ellipse_center_radii_group = QWidget()
        ellipse_cr_layout = QGridLayout()
        ellipse_cr_layout.addWidget(QLabel("Радиус X:"), 0, 0)
        self.ellipse_radius_x_spin = QDoubleSpinBox()
        self.ellipse_radius_x_spin.setRange(0, 1000)
        self.ellipse_radius_x_spin.setDecimals(2)
        self.ellipse_radius_x_spin.setSingleStep(10)
        self.ellipse_radius_x_spin.setValue(50)
        self.ellipse_radius_x_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        ellipse_cr_layout.addWidget(self.ellipse_radius_x_spin, 0, 1, 1, 4)
        
        ellipse_cr_layout.addWidget(QLabel("Радиус Y:"), 1, 0)
        self.ellipse_radius_y_spin = QDoubleSpinBox()
        self.ellipse_radius_y_spin.setRange(0, 1000)
        self.ellipse_radius_y_spin.setDecimals(2)
        self.ellipse_radius_y_spin.setSingleStep(10)
        self.ellipse_radius_y_spin.setValue(30)
        self.ellipse_radius_y_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        ellipse_cr_layout.addWidget(self.ellipse_radius_y_spin, 1, 1, 1, 4)
        self.ellipse_center_radii_group.setLayout(ellipse_cr_layout)
        self.ellipse_center_radii_group.hide()
        
        # Три точки
        self.ellipse_three_points_group = QWidget()
        ellipse_3p_layout = QGridLayout()
        ellipse_3p_layout.addWidget(QLabel("Вторая точка:"), 0, 0)
        self.ellipse_point2_x_spin = QDoubleSpinBox()
        self.ellipse_point2_x_spin.setRange(-1000, 1000)
        self.ellipse_point2_x_spin.setDecimals(2)
        self.ellipse_point2_x_spin.setSingleStep(10)
        self.ellipse_point2_x_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        self.ellipse_point2_y_spin = QDoubleSpinBox()
        self.ellipse_point2_y_spin.setRange(-1000, 1000)
        self.ellipse_point2_y_spin.setDecimals(2)
        self.ellipse_point2_y_spin.setSingleStep(10)
        self.ellipse_point2_y_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        ellipse_3p_layout.addWidget(QLabel("x:"), 0, 1)
        ellipse_3p_layout.addWidget(self.ellipse_point2_x_spin, 0, 2)
        ellipse_3p_layout.addWidget(QLabel("y:"), 0, 3)
        ellipse_3p_layout.addWidget(self.ellipse_point2_y_spin, 0, 4)
        
        ellipse_3p_layout.addWidget(QLabel("Третья точка:"), 1, 0)
        self.ellipse_point3_x_spin = QDoubleSpinBox()
        self.ellipse_point3_x_spin.setRange(-1000, 1000)
        self.ellipse_point3_x_spin.setDecimals(2)
        self.ellipse_point3_x_spin.setSingleStep(10)
        self.ellipse_point3_x_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        self.ellipse_point3_y_spin = QDoubleSpinBox()
        self.ellipse_point3_y_spin.setRange(-1000, 1000)
        self.ellipse_point3_y_spin.setDecimals(2)
        self.ellipse_point3_y_spin.setSingleStep(10)
        self.ellipse_point3_y_spin.valueChanged.connect(self.on_ellipse_coordinates_changed)
        ellipse_3p_layout.addWidget(QLabel("x:"), 1, 1)
        ellipse_3p_layout.addWidget(self.ellipse_point3_x_spin, 1, 2)
        ellipse_3p_layout.addWidget(QLabel("y:"), 1, 3)
        ellipse_3p_layout.addWidget(self.ellipse_point3_y_spin, 1, 4)
        self.ellipse_three_points_group.setLayout(ellipse_3p_layout)
        self.ellipse_three_points_group.hide()
        
        input_layout.addWidget(self.ellipse_center_radii_group, 1, 1, 2, 4)
        input_layout.addWidget(self.ellipse_three_points_group, 1, 1, 2, 4)
        
        # Группы для многоугольника
        # Способ создания
        self.polygon_method_group = QGroupBox("Способ создания")
        polygon_method_layout = QVBoxLayout()
        self.polygon_method_combo = QComboBox()
        self.polygon_method_combo.addItems([
            "Центр и радиус (курсором)",
            "Вписанная окружность (ручной ввод)",
            "Описанная окружность (ручной ввод)"
        ])
        self.polygon_method_combo.currentIndexChanged.connect(self.on_polygon_method_changed)
        polygon_method_layout.addWidget(self.polygon_method_combo)
        self.polygon_method_group.setLayout(polygon_method_layout)
        self.polygon_method_group.hide()
        input_layout.addWidget(self.polygon_method_group, 1, 0, 1, 5)
        
        # Центр, радиус и количество углов
        self.polygon_center_radius_vertices_group = QWidget()
        polygon_crv_layout = QGridLayout()
        polygon_crv_layout.addWidget(QLabel("Радиус:"), 0, 0)
        self.polygon_radius_spin = QDoubleSpinBox()
        self.polygon_radius_spin.setRange(0, 1000)
        self.polygon_radius_spin.setDecimals(2)
        self.polygon_radius_spin.setSingleStep(10)
        self.polygon_radius_spin.setValue(50)
        self.polygon_radius_spin.valueChanged.connect(self.on_polygon_coordinates_changed)
        polygon_crv_layout.addWidget(self.polygon_radius_spin, 0, 1, 1, 4)
        
        polygon_crv_layout.addWidget(QLabel("Количество углов:"), 1, 0)
        self.polygon_num_vertices_spin = QSpinBox()
        self.polygon_num_vertices_spin.setRange(3, 100)
        self.polygon_num_vertices_spin.setValue(3)
        self.polygon_num_vertices_spin.valueChanged.connect(self.on_polygon_coordinates_changed)
        polygon_crv_layout.addWidget(self.polygon_num_vertices_spin, 1, 1, 1, 4)
        self.polygon_center_radius_vertices_group.setLayout(polygon_crv_layout)
        self.polygon_center_radius_vertices_group.hide()
        
        input_layout.addWidget(self.polygon_center_radius_vertices_group, 2, 0, 1, 5)
        
        # кнопка применения координат
        # Размещаем кнопку после всех возможных виджетов (строка 4 или больше)
        # Максимальный rowSpan = 3 (arc_center_angles_group), поэтому кнопка на строке 4
        self.apply_coords_btn = QPushButton("Применить координаты")
        self.apply_coords_btn.clicked.connect(self.apply_coordinates)
        input_layout.addWidget(self.apply_coords_btn, 5, 0, 1, 5)
        
        self.input_group.setLayout(input_layout)
        left_panel.addWidget(self.input_group)
        
        # панель настроек
        settings_group = QGroupBox("Настройки")
        settings_layout = QVBoxLayout()
        
        # шаг сетки (в миллиметрах)
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel("Шаг сетки:"))
        self.grid_spin = QDoubleSpinBox()
        self.grid_spin.setRange(0.1, 100.0)
        self.grid_spin.setDecimals(1)
        self.grid_spin.setSingleStep(1.0)
        self.grid_spin.setValue(20.0)  # 20 мм по умолчанию
        self.grid_spin.valueChanged.connect(self.change_grid_step)
        grid_layout.addWidget(self.grid_spin)
        settings_layout.addLayout(grid_layout)
        
        # цвета
        color_layout = QVBoxLayout()
        self.line_color_btn = QPushButton("Цвет отрезка")
        self.line_color_btn.clicked.connect(self.change_line_color)
        
        self.bg_color_btn = QPushButton("Цвет фона")
        self.bg_color_btn.clicked.connect(self.change_background_color)
        
        self.grid_color_btn = QPushButton("Цвет сетки")
        self.grid_color_btn.clicked.connect(self.change_grid_color)
        
        color_layout.addWidget(self.line_color_btn)
        color_layout.addWidget(self.bg_color_btn)
        color_layout.addWidget(self.grid_color_btn)
        settings_layout.addLayout(color_layout)
        
        settings_group.setLayout(settings_layout)
        left_panel.addWidget(settings_group)
        
        # информация о количестве объектов
        self.lines_count_label = QLabel("Объектов на экране: 0")
        left_panel.addWidget(self.lines_count_label)
        
        # Добавляем панели стилей
        # Панель свойств объекта
        self.object_properties_panel = ObjectPropertiesPanel(self.style_manager)
        self.object_properties_panel.style_changed.connect(self.on_object_style_changed)
        # Устанавливаем ссылку на canvas для доступа к линиям
        self.object_properties_panel.canvas = self.canvas
        # Подключаем сигнал изменения выделения
        self.canvas.selection_changed.connect(self.on_selection_changed)
        # Скрываем панель по умолчанию (пока нет выделенных объектов)
        self.object_properties_panel.hide()
        left_panel.addWidget(self.object_properties_panel)
        
        # Панель управления стилями
        self.style_management_panel = StyleManagementPanel(self.style_manager)
        left_panel.addWidget(self.style_management_panel)
        
        left_panel.addStretch()
        
        # правая часть с рабочей областью и информацией
        right_widget = QWidget()
        right_panel = QVBoxLayout(right_widget)
        
        # рабочая область
        right_panel.addWidget(self.canvas)
        
        # информационная панель
        info_group = QGroupBox("Информация об объекте")
        info_layout = QGridLayout()
        
        # Метки для информации (будут обновляться в зависимости от типа объекта)
        self.info_label1 = QLabel("")
        self.info_value1 = QLabel("")
        info_layout.addWidget(self.info_label1, 0, 0)
        info_layout.addWidget(self.info_value1, 0, 1)
        
        self.info_label2 = QLabel("")
        self.info_value2 = QLabel("")
        info_layout.addWidget(self.info_label2, 1, 0)
        info_layout.addWidget(self.info_value2, 1, 1)
        
        self.info_label3 = QLabel("")
        self.info_value3 = QLabel("")
        info_layout.addWidget(self.info_label3, 2, 0)
        info_layout.addWidget(self.info_value3, 2, 1)
        
        self.info_label4 = QLabel("")
        self.info_value4 = QLabel("")
        info_layout.addWidget(self.info_label4, 3, 0)
        info_layout.addWidget(self.info_value4, 3, 1)
        
        info_group.setLayout(info_layout)
        right_panel.addWidget(info_group)
        
        # Добавляем виджеты в splitter
        main_splitter.addWidget(scroll_area)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(main_splitter)
        
        # инициализация значений
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.end_x_spin.blockSignals(True)
        self.end_y_spin.blockSignals(True)
        self.radius_spin.blockSignals(True)
        self.angle_spin.blockSignals(True)
        
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.end_x_spin.setValue(100)
        self.end_y_spin.setValue(100)
        self.radius_spin.setValue(100)
        self.angle_spin.setValue(45)
        
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        self.end_x_spin.blockSignals(False)
        self.end_y_spin.blockSignals(False)
        self.radius_spin.blockSignals(False)
        self.angle_spin.blockSignals(False)
        
        # подключаем сигналы от canvas для обновления статусбара
        self.canvas.view_changed.connect(self.update_statusbar)
        # подключаем сигнал завершения рисования отрезка для обновления информации
        self.canvas.line_finished.connect(self.update_info)
        # подключаем сигнал начала рисования прямоугольника для установки размеров
        self.canvas.rectangle_drawing_started.connect(self.update_rectangle_on_drawing_start)
        self.update_statusbar()
    
    def create_context_menu(self, position):
        # контекстное меню для рабочей области
        menu = QMenu(self)
        
        # команды навигации
        zoom_in_action = menu.addAction("Увеличить")
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        
        zoom_out_action = menu.addAction("Уменьшить")
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        
        menu.addSeparator()
        
        show_all_action = menu.addAction("Показать всё")
        show_all_action.setShortcut("Ctrl+A")
        show_all_action.triggered.connect(self.canvas.show_all)
        
        reset_view_action = menu.addAction("Сбросить вид")
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.triggered.connect(self.canvas.reset_view)
        
        menu.addSeparator()
        
        rotate_left_action = menu.addAction("Повернуть налево")
        rotate_left_action.setShortcut("Ctrl+Left")
        rotate_left_action.triggered.connect(self.rotate_left)
        
        rotate_right_action = menu.addAction("Повернуть направо")
        rotate_right_action.setShortcut("Ctrl+Right")
        rotate_right_action.triggered.connect(self.rotate_right)
        
        menu.addSeparator()
        
        # инструменты
        pan_action = menu.addAction("Панорамирование")
        pan_action.setCheckable(True)
        pan_action.setChecked(self.pan_action.isChecked())
        pan_action.triggered.connect(self.pan_action.toggle)
        
        menu.exec_(self.mapToGlobal(position))
    
    def rotate_left(self):
        # поворот налево
        self.canvas.rotate_left(15)
        
    def rotate_right(self):
        # поворот направо
        self.canvas.rotate_right(15)
    
    def create_menus(self):
        menubar = self.menuBar()
        
        # меню "Вид"
        view_menu = menubar.addMenu("Вид")
        
        # действия для навигации
        zoom_in_action = QAction("Увеличить", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Уменьшить", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        view_menu.addSeparator()
        
        show_all_action = QAction("Показать всё", self)
        show_all_action.setShortcut("Ctrl+A")
        show_all_action.triggered.connect(self.canvas.show_all)
        view_menu.addAction(show_all_action)
        
        reset_view_action = QAction("Сбросить вид", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.triggered.connect(self.canvas.reset_view)
        view_menu.addAction(reset_view_action)
        
        view_menu.addSeparator()
        
        rotate_left_action = QAction("Повернуть налево", self)
        rotate_left_action.setShortcut("Ctrl+Left")
        rotate_left_action.triggered.connect(self.rotate_left)
        view_menu.addAction(rotate_left_action)
        
        rotate_right_action = QAction("Повернуть направо", self)
        rotate_right_action.setShortcut("Ctrl+Right")
        rotate_right_action.triggered.connect(self.rotate_right)
        view_menu.addAction(rotate_right_action)
    
    def create_toolbar(self):
        # панель инструментов навигации
        toolbar = QToolBar("Навигация")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # инструмент "Рука" для панорамирования
        self.pan_action = QAction("🖑", self)
        self.pan_action.setCheckable(True)
        self.pan_action.setToolTip("Панорамирование (Пробел)")
        self.pan_action.setShortcut(Qt.Key_Space)
        self.pan_action.toggled.connect(self.canvas.set_pan_mode)
        toolbar.addAction(self.pan_action)
        
        toolbar.addSeparator()
        
        # увеличение
        zoom_in_action = QAction("🞢", self)
        zoom_in_action.setToolTip("Увеличить")
        zoom_in_action.triggered.connect(self.canvas.zoom_in)
        toolbar.addAction(zoom_in_action)
        
        # уменьшение
        zoom_out_action = QAction("‒", self)
        zoom_out_action.setToolTip("Уменьшить")
        zoom_out_action.triggered.connect(self.canvas.zoom_out)
        toolbar.addAction(zoom_out_action)
        
        # показать всё сохраняя поворот
        show_all_action = QAction("ⓘ", self)
        show_all_action.setToolTip("Показать всё (сохранить поворот)")
        show_all_action.triggered.connect(self.canvas.show_all)
        toolbar.addAction(show_all_action)
        
        toolbar.addSeparator()
        
        # поворот налево
        rotate_left_action = QAction("↶", self)
        rotate_left_action.setToolTip("Повернуть налево")
        rotate_left_action.triggered.connect(self.rotate_left)
        toolbar.addAction(rotate_left_action)
        
        # поворот направо
        rotate_right_action = QAction("↷", self)
        rotate_right_action.setToolTip("Повернуть направо")
        rotate_right_action.triggered.connect(self.rotate_right)
        toolbar.addAction(rotate_right_action)
        
        # сброс вида
        reset_view_action = QAction("⟲", self)
        reset_view_action.setToolTip("Сбросить вид")
        reset_view_action.triggered.connect(self.canvas.reset_view)
        toolbar.addAction(reset_view_action)
        
        toolbar.addSeparator()
        
        # Кнопка редактирования
        edit_action = QAction("Редактировать", self)
        edit_action.setToolTip("Открыть окно редактирования выделенного объекта")
        edit_action.triggered.connect(self.open_edit_dialog)
        toolbar.addAction(edit_action)
    
    def create_style_toolbar(self):
        """Создает панель инструментов для стилей линий"""
        style_toolbar = QToolBar("Стили линий")
        style_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(style_toolbar)
        
        # Выпадающий список текущего стиля
        style_label = QLabel("Текущий стиль:")
        style_toolbar.addWidget(style_label)
        
        self.current_style_combo = StyleComboBox(self.style_manager)
        self.current_style_combo.currentIndexChanged.connect(self.on_current_style_changed)
        style_toolbar.addWidget(self.current_style_combo)
        
        style_toolbar.addSeparator()
        
        # Кнопки быстрого доступа к популярным стилям
        popular_styles = ["Сплошная основная", "Сплошная тонкая", "Штриховая", "Штрихпунктирная тонкая"]
        
        for style_name in popular_styles:
            style = self.style_manager.get_style(style_name)
            if style:
                action = QAction(style_name, self)
                action.setToolTip(f"Установить стиль: {style_name}")
                action.triggered.connect(lambda checked, name=style_name: self.set_current_style(name))
                style_toolbar.addAction(action)
    
    def on_current_style_changed(self):
        """Обработчик изменения текущего стиля"""
        style = self.current_style_combo.get_current_style()
        if style:
            self.style_manager.set_current_style(style.name)
    
    def set_current_style(self, style_name):
        """Устанавливает текущий стиль"""
        self.style_manager.set_current_style(style_name)
        index = self.current_style_combo.findText(style_name)
        if index >= 0:
            self.current_style_combo.setCurrentIndex(index)
    
    def on_object_style_changed(self, style):
        """Обработчик изменения стиля объекта"""
        # Обновляем отрисовку
        self.canvas.update()
    
    def on_selection_changed(self, selected_objects):
        """Обработчик изменения выделения"""
        # Обновляем выделенные объекты
        self.selected_objects = selected_objects
        # Включаем/отключаем кнопку удаления выбранного
        if hasattr(self, 'delete_selected_btn'):
            self.delete_selected_btn.setEnabled(len(selected_objects) > 0)
        # Показываем или скрываем панель свойств в зависимости от выделения
        if selected_objects:
            self.object_properties_panel.show()
            # Обновляем панель свойств
            self.object_properties_panel.set_selected_objects(selected_objects)
        else:
            self.object_properties_panel.hide()
        # Обновляем информацию об объекте
        self.update_info()
    
    def open_edit_dialog(self):
        """Открывает окно редактирования для выделенного объекта"""
        selected_objects = self.selected_objects
        if len(selected_objects) == 1:
            obj = selected_objects[0]
            self.edit_dialog.set_object(obj)
            # Обновляем информацию для редактируемого объекта
            self.update_info_for_object(obj)
            self.edit_dialog.show()
        elif len(selected_objects) > 1:
            QMessageBox.information(self, "Редактирование", 
                                  "Пожалуйста, выберите один объект для редактирования.")
        else:
            QMessageBox.information(self, "Редактирование", 
                                  "Пожалуйста, выберите объект для редактирования.")
    
    def create_statusbar(self):
        # строка состояния
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # координаты курсора
        self.cursor_coords_label = QLabel("Координаты: (0.00, 0.00)")
        statusbar.addPermanentWidget(self.cursor_coords_label)
        
        # масштаб
        self.scale_label = QLabel("Масштаб: 100%")
        statusbar.addPermanentWidget(self.scale_label)
        
        # угол поворота
        self.rotation_label = QLabel("Поворот: 0°")
        statusbar.addPermanentWidget(self.rotation_label)
        
        # активный инструмент
        self.tool_label = QLabel("Инструмент: Рисование")
        statusbar.addWidget(self.tool_label)
    
    def update_statusbar(self):
        # информация в строке состояния
        # координаты курсора (если доступны)
        cursor_pos = self.canvas.get_cursor_world_coords()
        if cursor_pos:
            self.cursor_coords_label.setText(
                f"Координаты: ({cursor_pos.x():.2f}, {cursor_pos.y():.2f})"
            )

        # масштаб
        scale = self.canvas.get_scale() * 100
        self.scale_label.setText(f"Масштаб: {scale:.1f}%")

        # угол поворота
        rotation = self.canvas.get_rotation()
        self.rotation_label.setText(f"Поворот: {rotation:.1f}°")

        # активный инструмент
        if self.pan_action.isChecked():
            self.tool_label.setText("Инструмент: Панорамирование")
        else:
            self.tool_label.setText("Инструмент: Рисование")

    
    def start_new_line(self):
        # начинает новый отрезок
        # если уже рисуем отрезок, сохраняем его
        if self.canvas.is_drawing and self.canvas.current_line:
            # берем текущее положение мыши как конечную точку
            if self.canvas.current_point:
                self.canvas.current_line.end_point = self.canvas.current_point
                self.canvas.lines.append(self.canvas.current_line)
        
        # начинаем новый отрезок
        self.canvas.start_new_line()
        
        # сбрасываем значения в полях ввода для нового отрезка
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.end_x_spin.blockSignals(True)
        self.end_y_spin.blockSignals(True)
        self.radius_spin.blockSignals(True)
        self.angle_spin.blockSignals(True)
        
        # устанавливаем начальную точку в текущее положение курсора, если доступно
        cursor_pos = self.canvas.get_cursor_world_coords()
        if cursor_pos:
            self.start_x_spin.setValue(cursor_pos.x())
            self.start_y_spin.setValue(cursor_pos.y())
        else:
            self.start_x_spin.setValue(0)
            self.start_y_spin.setValue(0)
        
        # сбрасываем конечные точки
        self.end_x_spin.setValue(100)
        self.end_y_spin.setValue(100)
        self.radius_spin.setValue(100)
        self.angle_spin.setValue(45)
        
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        self.end_x_spin.blockSignals(False)
        self.end_y_spin.blockSignals(False)
        self.radius_spin.blockSignals(False)
        self.angle_spin.blockSignals(False)
        
        self.update_info()
        
    def finish_current_line(self):
        # завершает текущий отрезок и сохраняет его
        if self.canvas.is_drawing and self.canvas.current_line:
            self.canvas.lines.append(self.canvas.current_line)
            self.canvas.current_line = None
            self.canvas.is_drawing = False
            self.canvas.current_point = None
            self.canvas.update()
            self.update_info()
    
    def delete_last_line(self):
        # удаление последний отрезок
        self.canvas.delete_last_line()
        self.update_info()
    
    def delete_all_lines(self):
        #  удаляет все отрезки
        self.canvas.delete_all_lines()
        self.update_info()
    
    def delete_selected_objects(self):
        """Удаляет выделенные объекты"""
        if not self.selected_objects:
            return
        
        # Создаем копию списка, так как мы будем изменять selected_objects
        objects_to_delete = list(self.selected_objects)
        
        # Удаляем каждый выделенный объект из сцены
        for obj in objects_to_delete:
            self.canvas.scene.remove_object(obj)
        
        # Очищаем выделение через selection_manager (это автоматически отправит сигнал selection_changed)
        # который вызовет on_selection_changed и обновит UI
        if hasattr(self.canvas, 'selection_manager'):
            self.canvas.selection_manager.clear_selection()
        
        # Обновляем отображение
        self.canvas.update()
    
    def apply_coordinates(self):
        # координаты из полей ввода и фикс объекта
        start_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        
        # Проверяем, создаем ли мы окружность, дугу, прямоугольник или эллипс
        if self.canvas.primitive_type == 'circle':
            self.apply_circle_coordinates(start_point)
            return
        elif self.canvas.primitive_type == 'arc':
            self.apply_arc_coordinates(start_point)
            return
        elif self.canvas.primitive_type == 'rectangle':
            self.apply_rectangle_coordinates(start_point)
            return
        elif self.canvas.primitive_type == 'ellipse':
            self.apply_ellipse_coordinates(start_point)
            return
        elif self.canvas.primitive_type == 'polygon':
            self.apply_polygon_coordinates(start_point)
            return
        elif self.canvas.primitive_type == 'spline':
            # Для сплайна ручной ввод координат не поддерживается
            return
        
        # Для остальных примитивов (отрезок и т.д.)
        # Используем систему координат и единицы углов для отрезка
        if self.line_coordinate_system == "cartesian":
            end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
        else:
            # преобразуем полярные координаты в декартовы ОТНОСИТЕЛЬНО НАЧАЛЬНОЙ ТОЧКИ
            radius = self.radius_spin.value()
            angle = self.angle_spin.value()
            
            if self.line_angle_units == "degrees":
                angle_rad = math.radians(angle)
            else:
                angle_rad = angle
            
            # вычисляем смещение от начальной точки
            delta_x = radius * math.cos(angle_rad)
            delta_y = radius * math.sin(angle_rad)
            
            # конечная точка = начальная + смещение
            end_x = start_point.x() + delta_x
            end_y = start_point.y() + delta_y
            end_point = QPointF(end_x, end_y)
        
        # фиксируем отрезок (apply=True)
        self.canvas.set_points_from_input(start_point, end_point, apply=True)
    
    def apply_circle_coordinates(self, center_point):
        """Применяет координаты для создания окружности"""
        from widgets.primitives import Circle
        
        # Отменяем текущее рисование, если оно есть
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        method_name = self.circle_method_combo.currentText()
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
        
        if method_name == "Центр и радиус":
            radius = self.circle_radius_spin.value()
            circle = Circle(center_point, radius, style=style, 
                          color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(circle)
        elif method_name == "Центр и диаметр":
            diameter = self.circle_diameter_spin.value()
            radius = diameter / 2.0
            circle = Circle(center_point, radius, style=style,
                          color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(circle)
        elif method_name == "Две точки":
            point2 = QPointF(self.circle_point2_x_spin.value(), self.circle_point2_y_spin.value())
            import math
            dx = point2.x() - center_point.x()
            dy = point2.y() - center_point.y()
            radius = math.sqrt(dx*dx + dy*dy) / 2.0
            center_x = (center_point.x() + point2.x()) / 2.0
            center_y = (center_point.y() + point2.y()) / 2.0
            center = QPointF(center_x, center_y)
            circle = Circle(center, radius, style=style,
                          color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(circle)
        elif method_name == "Три точки на окружности":
            point2 = QPointF(self.circle_point2_x_spin_3p.value(), self.circle_point2_y_spin_3p.value())
            point3 = QPointF(self.circle_point3_x_spin.value(), self.circle_point3_y_spin.value())
            # Используем метод из Scene для вычисления окружности по трем точкам
            import math
            # Вычисляем центр и радиус окружности по трем точкам
            x1, y1 = center_point.x(), center_point.y()
            x2, y2 = point2.x(), point2.y()
            x3, y3 = point3.x(), point3.y()
            
            A = x1 * (y2 - y3) - y1 * (x2 - x3) + (x2 * y3 - x3 * y2)
            
            if abs(A) < 1e-10:
                # Точки коллинеарны
                return
            
            B = (x1*x1 + y1*y1) * (y3 - y2) + (x2*x2 + y2*y2) * (y1 - y3) + (x3*x3 + y3*y3) * (y2 - y1)
            C = (x1*x1 + y1*y1) * (x2 - x3) + (x2*x2 + y2*y2) * (x3 - x1) + (x3*x3 + y3*y3) * (x1 - x2)
            
            center_x = -B / (2 * A)
            center_y = -C / (2 * A)
            center = QPointF(center_x, center_y)
            
            dx = x1 - center_x
            dy = y1 - center_y
            radius = math.sqrt(dx*dx + dy*dy)
            if center and radius > 0:
                circle = Circle(center, radius, style=style,
                              color=self.canvas.line_color, width=self.canvas.line_width)
                self.canvas.scene.add_object(circle)
        
        self.canvas.update()
        # Автоматически показываем все объекты с сохранением поворота
        self.canvas.show_all_preserve_rotation()
        
        # Очищаем точки ввода после применения
        self.canvas.clear_input_points()
        
        # Убеждаемся, что нет активного рисования
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Сбрасываем значения для следующей окружности
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        
        # Сбрасываем значения в зависимости от метода
        method_name = self.circle_method_combo.currentText()
        if method_name == "Центр и радиус":
            self.circle_radius_spin.blockSignals(True)
            self.circle_radius_spin.setValue(50)
            self.circle_radius_spin.blockSignals(False)
        elif method_name == "Центр и диаметр":
            self.circle_diameter_spin.blockSignals(True)
            self.circle_diameter_spin.setValue(100)
            self.circle_diameter_spin.blockSignals(False)
        elif method_name == "Две точки":
            self.circle_point2_x_spin.blockSignals(True)
            self.circle_point2_y_spin.blockSignals(True)
            self.circle_point2_x_spin.setValue(100)
            self.circle_point2_y_spin.setValue(0)
            self.circle_point2_x_spin.blockSignals(False)
            self.circle_point2_y_spin.blockSignals(False)
        elif method_name == "Три точки на окружности":
            self.circle_point2_x_spin_3p.blockSignals(True)
            self.circle_point2_y_spin_3p.blockSignals(True)
            self.circle_point3_x_spin.blockSignals(True)
            self.circle_point3_y_spin.blockSignals(True)
            self.circle_point2_x_spin_3p.setValue(100)
            self.circle_point2_y_spin_3p.setValue(0)
            self.circle_point3_x_spin.setValue(0)
            self.circle_point3_y_spin.setValue(100)
            self.circle_point2_x_spin_3p.blockSignals(False)
            self.circle_point2_y_spin_3p.blockSignals(False)
            self.circle_point3_x_spin.blockSignals(False)
            self.circle_point3_y_spin.blockSignals(False)
        
        self.update_info()
    
    def apply_arc_coordinates(self, start_point):
        """Применяет координаты для создания дуги"""
        from widgets.primitives import Arc
        
        # Отменяем текущее рисование, если оно есть
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        method_name = self.arc_method_combo.currentText()
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
        
        if method_name == "Три точки (начало, вторая точка, конец)":
            point2 = QPointF(self.arc_point2_x_spin.value(), self.arc_point2_y_spin.value())
            point3 = QPointF(self.arc_point3_x_spin.value(), self.arc_point3_y_spin.value())
            # Вычисляем параметры дуги по трем точкам
            result = self.canvas.scene._calculate_ellipse_arc_from_three_points(
                start_point, point2, point3
            )
            if len(result) == 6 and result[0] is not None:
                center, radius_x, radius_y, start_angle, end_angle, rotation_angle = result
                if radius_x > 0 and radius_y > 0:
                    arc = Arc(center, radius_x, radius_y, start_angle, end_angle, style=style,
                            color=self.canvas.line_color, width=self.canvas.line_width, rotation_angle=rotation_angle)
                    self.canvas.scene.add_object(arc)
        elif method_name == "Центр, начальный угол, конечный угол":
            radius = self.arc_radius_spin.value()
            start_angle = self.arc_start_angle_spin.value()
            end_angle = self.arc_end_angle_spin.value()
            arc = Arc(start_point, radius, radius, start_angle, end_angle, style=style,
                     color=self.canvas.line_color, width=self.canvas.line_width, rotation_angle=0.0)
            self.canvas.scene.add_object(arc)
        
        self.canvas.update()
        # Автоматически показываем все объекты с сохранением поворота
        self.canvas.show_all_preserve_rotation()
        
        # Очищаем точки ввода после применения
        self.canvas.clear_input_points()
        
        # Убеждаемся, что нет активного рисования
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Обновляем информацию об объекте
        self.update_info()
        
        # Сбрасываем значения для следующей дуги
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        
        # Сбрасываем значения в зависимости от метода
        if method_name == "Три точки (начало, вторая точка, конец)":
            self.arc_point2_x_spin.blockSignals(True)
            self.arc_point2_y_spin.blockSignals(True)
            self.arc_point3_x_spin.blockSignals(True)
            self.arc_point3_y_spin.blockSignals(True)
            self.arc_point2_x_spin.setValue(100)
            self.arc_point2_y_spin.setValue(0)
            self.arc_point3_x_spin.setValue(0)
            self.arc_point3_y_spin.setValue(100)
            self.arc_point2_x_spin.blockSignals(False)
            self.arc_point2_y_spin.blockSignals(False)
            self.arc_point3_x_spin.blockSignals(False)
            self.arc_point3_y_spin.blockSignals(False)
        elif method_name == "Центр, начальный угол, конечный угол":
            self.arc_radius_spin.blockSignals(True)
            self.arc_start_angle_spin.blockSignals(True)
            self.arc_end_angle_spin.blockSignals(True)
            self.arc_radius_spin.setValue(50)
            self.arc_start_angle_spin.setValue(0)
            self.arc_end_angle_spin.setValue(90)
            self.arc_radius_spin.blockSignals(False)
            self.arc_start_angle_spin.blockSignals(False)
            self.arc_end_angle_spin.blockSignals(False)
        
        self.update_info()
    
    def apply_rectangle_coordinates(self, start_point):
        """Применяет координаты для создания прямоугольника"""
        from widgets.primitives import Rectangle
        
        # Отменяем текущее рисование, если оно есть
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        method_name = self.rectangle_method_combo.currentText()
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
        
        if method_name == "Две противоположные точки":
            # Используем обычные поля для конечной точки
            if self.coordinate_system == "cartesian":
                end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
            else:
                # Преобразуем полярные координаты в декартовы
                radius = self.radius_spin.value()
                angle = self.angle_spin.value()
                if self.angle_units == "degrees":
                    angle_rad = math.radians(angle)
                else:
                    angle_rad = angle
                delta_x = radius * math.cos(angle_rad)
                delta_y = radius * math.sin(angle_rad)
                end_point = QPointF(start_point.x() + delta_x, start_point.y() + delta_y)
            rectangle = Rectangle(start_point, end_point, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(rectangle)
        elif method_name == "Одна точка, ширина и высота":
            width = self.rectangle_width_spin.value()
            height = self.rectangle_height_spin.value()
            end_point = QPointF(start_point.x() + width, start_point.y() + height)
            rectangle = Rectangle(start_point, end_point, style=style,
                                color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(rectangle)
        elif method_name == "Центр, ширина и высота":
            width = self.rectangle_center_width_spin.value()
            height = self.rectangle_center_height_spin.value()
            half_width = width / 2.0
            half_height = height / 2.0
            top_left = QPointF(start_point.x() - half_width, start_point.y() - half_height)
            bottom_right = QPointF(start_point.x() + half_width, start_point.y() + half_height)
            rectangle = Rectangle(top_left, bottom_right, style=style,
                                color=self.canvas.line_color, width=self.canvas.line_width)
            self.canvas.scene.add_object(rectangle)
        elif method_name == "С фасками/скруглениями при создании":
            # Используем обычные поля для конечной точки
            if self.coordinate_system == "cartesian":
                end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
            else:
                # Преобразуем полярные координаты в декартовы
                radius = self.radius_spin.value()
                angle = self.angle_spin.value()
                if self.angle_units == "degrees":
                    angle_rad = math.radians(angle)
                else:
                    angle_rad = angle
                delta_x = radius * math.cos(angle_rad)
                delta_y = radius * math.sin(angle_rad)
                end_point = QPointF(start_point.x() + delta_x, start_point.y() + delta_y)
            fillet_radius = self.rectangle_fillet_radius_spin.value()
            rectangle = Rectangle(start_point, end_point, style=style,
                                color=self.canvas.line_color, width=self.canvas.line_width,
                                fillet_radius=fillet_radius)
            self.canvas.scene.add_object(rectangle)
        
        self.canvas.update()
        # Автоматически показываем все объекты с сохранением поворота
        self.canvas.show_all_preserve_rotation()
        
        # Очищаем точки ввода после применения
        self.canvas.clear_input_points()
        
        # Убеждаемся, что нет активного рисования
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Обновляем информацию об объекте
        self.update_info()
        
        # Сбрасываем значения для следующего прямоугольника
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        
        # Сбрасываем значения в зависимости от метода
        if method_name == "Две противоположные точки":
            self.end_x_spin.blockSignals(True)
            self.end_y_spin.blockSignals(True)
            self.end_x_spin.setValue(100)
            self.end_y_spin.setValue(100)
            self.end_x_spin.blockSignals(False)
            self.end_y_spin.blockSignals(False)
        elif method_name == "Одна точка, ширина и высота":
            self.rectangle_width_spin.blockSignals(True)
            self.rectangle_height_spin.blockSignals(True)
            self.rectangle_width_spin.setValue(100)
            self.rectangle_height_spin.setValue(100)
            self.rectangle_width_spin.blockSignals(False)
            self.rectangle_height_spin.blockSignals(False)
        elif method_name == "Центр, ширина и высота":
            self.rectangle_center_width_spin.blockSignals(True)
            self.rectangle_center_height_spin.blockSignals(True)
            self.rectangle_center_width_spin.setValue(100)
            self.rectangle_center_height_spin.setValue(100)
            self.rectangle_center_width_spin.blockSignals(False)
            self.rectangle_center_height_spin.blockSignals(False)
        elif method_name == "С фасками/скруглениями при создании":
            self.end_x_spin.blockSignals(True)
            self.end_y_spin.blockSignals(True)
            self.rectangle_fillet_radius_spin.blockSignals(True)
            self.end_x_spin.setValue(100)
            self.end_y_spin.setValue(100)
            self.rectangle_fillet_radius_spin.setValue(10)
            self.end_x_spin.blockSignals(False)
            self.end_y_spin.blockSignals(False)
            self.rectangle_fillet_radius_spin.blockSignals(False)
        
        self.update_info()
    
    def apply_ellipse_coordinates(self, center_point):
        """Применяет координаты для создания эллипса"""
        from widgets.primitives import Ellipse
        
        # Отменяем текущее рисование, если оно есть
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        method_name = self.ellipse_method_combo.currentText()
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
        
        if method_name == "Центр и радиусы":
            radius_x = self.ellipse_radius_x_spin.value()
            radius_y = self.ellipse_radius_y_spin.value()
            if radius_x > 0 and radius_y > 0:
                ellipse = Ellipse(center_point, radius_x, radius_y, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width, rotation_angle=0.0)
                self.canvas.scene.add_object(ellipse)
        elif method_name == "Три точки на эллипсе":
            point2 = QPointF(self.ellipse_point2_x_spin.value(), self.ellipse_point2_y_spin.value())
            point3 = QPointF(self.ellipse_point3_x_spin.value(), self.ellipse_point3_y_spin.value())
            # Используем метод из Scene для вычисления эллипса по трем точкам
            result = self.canvas.scene._calculate_ellipse_from_three_points(
                center_point, point2, point3
            )
            if result and len(result) >= 4:
                center, radius_x, radius_y, rotation_angle = result
                if center is not None and radius_x > 0 and radius_y > 0:
                    ellipse = Ellipse(center, radius_x, radius_y, style=style,
                                    color=self.canvas.line_color, width=self.canvas.line_width, rotation_angle=rotation_angle)
                    self.canvas.scene.add_object(ellipse)
        
        self.canvas.update()
        # Автоматически показываем все объекты с сохранением поворота
        self.canvas.show_all_preserve_rotation()
        
        # Очищаем точки ввода после применения
        self.canvas.clear_input_points()
        
        # Убеждаемся, что нет активного рисования
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Обновляем информацию об объекте
        self.update_info()
        
        # Сбрасываем значения для следующего эллипса
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        
        # Сбрасываем значения в зависимости от метода
        if method_name == "Центр и радиусы":
            self.ellipse_radius_x_spin.blockSignals(True)
            self.ellipse_radius_y_spin.blockSignals(True)
            self.ellipse_radius_x_spin.setValue(50)
            self.ellipse_radius_y_spin.setValue(30)
            self.ellipse_radius_x_spin.blockSignals(False)
            self.ellipse_radius_y_spin.blockSignals(False)
        elif method_name == "Три точки на эллипсе":
            self.ellipse_point2_x_spin.blockSignals(True)
            self.ellipse_point2_y_spin.blockSignals(True)
            self.ellipse_point3_x_spin.blockSignals(True)
            self.ellipse_point3_y_spin.blockSignals(True)
            self.ellipse_point2_x_spin.setValue(100)
            self.ellipse_point2_y_spin.setValue(0)
            self.ellipse_point3_x_spin.setValue(0)
            self.ellipse_point3_y_spin.setValue(50)
            self.ellipse_point2_x_spin.blockSignals(False)
            self.ellipse_point2_y_spin.blockSignals(False)
            self.ellipse_point3_x_spin.blockSignals(False)
            self.ellipse_point3_y_spin.blockSignals(False)
        
        self.update_info()
    
    def apply_polygon_coordinates(self, center_point):
        """Применяет координаты для создания многоугольника"""
        from widgets.primitives import Polygon
        
        # Отменяем текущее рисование, если оно есть
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Получаем параметры многоугольника
        radius = self.polygon_radius_spin.value()
        num_vertices = self.polygon_num_vertices_spin.value()
        method_index = self.polygon_method_combo.currentIndex()
        
        if radius > 0 and num_vertices >= 3:
            style = None
            if self.style_manager:
                style = self.style_manager.get_current_style()
            
            if method_index == 0:
                # Центр и радиус курсором - создаем с начальным углом по умолчанию
                polygon = Polygon(center_point, radius, num_vertices, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width)
            elif method_index == 1:
                # Вписанная окружность с ручным вводом
                polygon = Polygon(center_point, radius, num_vertices, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width,
                                 construction_type='inscribed')
            elif method_index == 2:
                # Описанная окружность с ручным вводом
                polygon = Polygon(center_point, radius, num_vertices, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width,
                                 construction_type='circumscribed')
            else:
                polygon = Polygon(center_point, radius, num_vertices, style=style,
                                 color=self.canvas.line_color, width=self.canvas.line_width)
            
            self.canvas.scene.add_object(polygon)
        
        self.canvas.update()
        # Автоматически показываем все объекты с сохранением поворота
        self.canvas.show_all_preserve_rotation()
        
        # Очищаем точки ввода после применения
        self.canvas.clear_input_points()
        
        # Убеждаемся, что нет активного рисования
        if self.canvas.scene.is_drawing():
            self.canvas.scene.cancel_drawing()
        
        # Обновляем информацию об объекте
        self.update_info()
        
        # Сбрасываем значения для следующего многоугольника
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(0)
        self.start_y_spin.setValue(0)
        self.start_y_spin.blockSignals(False)
        self.start_x_spin.blockSignals(False)
        
        self.polygon_radius_spin.blockSignals(True)
        self.polygon_num_vertices_spin.blockSignals(True)
        self.polygon_radius_spin.setValue(50)
        self.polygon_num_vertices_spin.setValue(3)
        self.polygon_radius_spin.blockSignals(False)
        self.polygon_num_vertices_spin.blockSignals(False)
        
        self.update_info()
    
    def change_coordinate_system(self, system):
        self.coordinate_system = "polar" if system == "Полярная" else "cartesian"
        self.update_input_fields()
        self.update_info()
    
    def change_primitive_type(self, primitive_name):
        """Изменяет тип создаваемого примитива"""
        primitive_map = {
            "Отрезок": "line",
            "Окружность": "circle",
            "Дуга": "arc",
            "Прямоугольник": "rectangle",
            "Эллипс": "ellipse",
            "Многоугольник": "polygon",
            "Сплайн": "spline"
        }
        primitive_type = primitive_map.get(primitive_name, "line")
        self.canvas.set_primitive_type(primitive_type)
        
        # Очищаем точки ввода при смене типа примитива
        self.canvas.clear_input_points()
        
        # Показываем/скрываем выбор метода создания окружности или дуги
        if primitive_type == "line":
            self.line_method_widget.show()
            self.circle_method_widget.hide()
            self.arc_method_widget.hide()
            self.rectangle_method_widget.hide()
            self.ellipse_method_widget.hide()
            # Убеждаемся, что комбобокс имеет правильное значение
            if self.line_method_combo.currentIndex() < 0:
                self.line_method_combo.setCurrentIndex(0)
            # Синхронизируем комбобоксы системы координат и единиц углов с выбранным методом
            method_text = self.line_method_combo.currentText()
            if "декартовых" in method_text.lower():
                self.line_coord_combo.blockSignals(True)
                self.line_coord_combo.setCurrentText("Декартова")
                self.line_coord_combo.blockSignals(False)
                self.line_coordinate_system = "cartesian"
            else:
                self.line_coord_combo.blockSignals(True)
                self.line_coord_combo.setCurrentText("Полярная")
                self.line_coord_combo.blockSignals(False)
                self.line_coordinate_system = "polar"
            # Явно вызываем обновление полей ввода
            self.change_line_method(method_text)
        elif primitive_type == "circle":
            self.line_method_widget.hide()
            self.circle_method_widget.show()
            self.arc_method_widget.hide()
            self.update_circle_input_fields()
        elif primitive_type == "arc":
            self.line_method_widget.hide()
            self.circle_method_widget.hide()
            self.arc_method_widget.show()
            self.rectangle_method_widget.hide()
            # Убеждаемся, что комбобокс имеет правильное значение
            if self.arc_method_combo.currentIndex() < 0:
                self.arc_method_combo.setCurrentIndex(0)
            # Явно вызываем обновление полей ввода
            self.change_arc_method(self.arc_method_combo.currentText())
        elif primitive_type == "rectangle":
            self.line_method_widget.hide()
            self.circle_method_widget.hide()
            self.arc_method_widget.hide()
            self.rectangle_method_widget.show()
            # Убеждаемся, что комбобокс имеет правильное значение
            if self.rectangle_method_combo.currentIndex() < 0:
                self.rectangle_method_combo.setCurrentIndex(0)
            # Явно вызываем обновление полей ввода
            self.change_rectangle_method(self.rectangle_method_combo.currentText())
        elif primitive_type == "ellipse":
            self.line_method_widget.hide()
            self.circle_method_widget.hide()
            self.arc_method_widget.hide()
            self.rectangle_method_widget.hide()
            self.ellipse_method_widget.show()
            # Убеждаемся, что комбобокс имеет правильное значение
            if self.ellipse_method_combo.currentIndex() < 0:
                self.ellipse_method_combo.setCurrentIndex(0)
            # Явно вызываем обновление полей ввода
            self.change_ellipse_method(self.ellipse_method_combo.currentText())
        elif primitive_type == "polygon":
            self.line_method_widget.hide()
            self.circle_method_widget.hide()
            self.arc_method_widget.hide()
            self.rectangle_method_widget.hide()
            self.ellipse_method_widget.hide()
            self.update_polygon_input_fields()
        else:
            self.line_method_widget.hide()
            self.circle_method_widget.hide()
            self.arc_method_widget.hide()
            self.rectangle_method_widget.hide()
            # Восстанавливаем метку для не-окружности/дуги/прямоугольника
            self.start_point_label_widget.setText("Начальная точка (x, y):")
            # Скрываем все группы окружности
            self.circle_center_radius_group.hide()
            self.circle_center_diameter_group.hide()
            self.circle_two_points_group.hide()
            self.circle_three_points_group.hide()
            # Скрываем все группы дуги
            self.arc_three_points_group.hide()
            self.arc_center_angles_group.hide()
            # Скрываем все группы прямоугольника
            self.rectangle_point_size_group.hide()
            self.rectangle_center_size_group.hide()
            self.rectangle_fillets_group.hide()
            # Скрываем все группы эллипса
            self.ellipse_center_radii_group.hide()
            self.ellipse_three_points_group.hide()
            # Скрываем все группы многоугольника
            self.polygon_center_radius_vertices_group.hide()
            # Скрываем все группы сплайна
            if hasattr(self, 'spline_control_points_group'):
                self.spline_control_points_group.hide()
            # Показываем метку "Конечная точка" для отрезка
            self.end_point_label_widget.show()
            # Показываем обычные поля ввода
            if self.coordinate_system == "cartesian":
                self.cartesian_group.show()
                self.polar_group.hide()
            else:
                self.cartesian_group.hide()
                self.polar_group.show()
    
    def change_line_method(self, method_name):
        """Изменяет способ задания отрезка"""
        if "декартовых" in method_name.lower():
            # Декартовы координаты
            self.line_coordinate_system = "cartesian"
            # Обновляем комбобокс без вызова сигнала, чтобы избежать рекурсии
            self.line_coord_combo.blockSignals(True)
            self.line_coord_combo.setCurrentText("Декартова")
            self.line_coord_combo.blockSignals(False)
        else:
            # Полярные координаты
            self.line_coordinate_system = "polar"
            # Обновляем комбобокс без вызова сигнала, чтобы избежать рекурсии
            self.line_coord_combo.blockSignals(True)
            self.line_coord_combo.setCurrentText("Полярная")
            self.line_coord_combo.blockSignals(False)
        self.update_line_input_fields()
        # Очищаем точки ввода при смене метода
        self.canvas.clear_input_points()
    
    def change_line_coordinate_system(self, system):
        """Изменяет систему координат для отрезка"""
        self.line_coordinate_system = "polar" if system == "Полярная" else "cartesian"
        self.update_line_input_fields()
        self.update_info()
    
    def change_line_angle_units(self, units):
        """Изменяет единицы углов для отрезка"""
        self.line_angle_units = "radians" if units == "Радианы" else "degrees"
        self.update_line_angle_units()
        self.update_info()
    
    def update_line_input_fields(self):
        """Обновляет поля ввода для отрезка в зависимости от способа задания"""
        # Показываем метку "Конечная точка"
        self.end_point_label_widget.show()
        
        # Обновляем отображение полей ввода в зависимости от системы координат
        if self.line_coordinate_system == "cartesian":
            self.cartesian_group.show()
            self.polar_group.hide()
        else:
            self.cartesian_group.hide()
            self.polar_group.show()
            
            # При переключении на полярные координаты преобразуем текущие декартовы координаты
            # ОТНОСИТЕЛЬНО НАЧАЛЬНОЙ ТОЧКИ
            start_x = self.start_x_spin.value()
            start_y = self.start_y_spin.value()
            end_x = self.end_x_spin.value()
            end_y = self.end_y_spin.value()
            
            # Вычисляем смещение от начальной точки
            delta_x = end_x - start_x
            delta_y = end_y - start_y
            
            # Преобразуем смещение в полярные координаты
            radius = math.sqrt(delta_x**2 + delta_y**2)
            angle = math.atan2(delta_y, delta_x)
            
            if self.line_angle_units == "degrees":
                angle = math.degrees(angle)
            
            self.radius_spin.blockSignals(True)
            self.angle_spin.blockSignals(True)
            self.radius_spin.setValue(radius)
            self.angle_spin.setValue(angle)
            self.radius_spin.blockSignals(False)
            self.angle_spin.blockSignals(False)
    
    def update_line_angle_units(self):
        """Обновляет единицы измерения углов для отрезка"""
        # Обновляем метку единиц углов
        self.angle_label.setText("°" if self.line_angle_units == "degrees" else "rad")
        
        # Конвертируем угол при смене единиц измерения
        if self.line_coordinate_system == "polar":
            current_angle = self.angle_spin.value()
            if self.line_angle_units == "degrees":
                # Были радианы, стали градусы
                current_angle = math.degrees(current_angle)
            else:
                # Были градусы, стали радианы
                current_angle = math.radians(current_angle)
            
            self.angle_spin.blockSignals(True)
            self.angle_spin.setValue(current_angle)
            self.angle_spin.blockSignals(False)
    
    def change_circle_method(self, method_name):
        """Изменяет метод создания окружности"""
        method_map = {
            "Центр и радиус": "center_radius",
            "Центр и диаметр": "center_diameter",
            "Две точки": "two_points",
            "Три точки на окружности": "three_points"
        }
        method = method_map.get(method_name, "center_radius")
        self.canvas.set_circle_creation_method(method)
        self.update_circle_input_fields()
        # Очищаем точки ввода при смене метода
        self.canvas.clear_input_points()
    
    def change_arc_method(self, method_name):
        """Изменяет метод создания дуги"""
        method_map = {
            "Три точки (начало, вторая точка, конец)": "three_points",
            "Центр, начальный угол, конечный угол": "center_angles"
        }
        method = method_map.get(method_name, "three_points")
        self.canvas.set_arc_creation_method(method)
        self.update_arc_input_fields()
        # Очищаем точки ввода при смене метода
        self.canvas.clear_input_points()
    
    def update_arc_input_fields(self):
        """Обновляет отображение полей ввода в зависимости от метода создания дуги"""
        # Показываем группу "Ввод координат"
        self.input_group.show()
        # Обновляем метку для дуги
        self.start_point_label_widget.setText("Начальная точка (x, y):")
        self.start_point_label_widget.show()
        self.start_x_spin.show()
        self.start_y_spin.show()
        
        # Скрываем метку "Конечная точка" для дуги
        self.end_point_label_widget.hide()
        
        # Скрываем ВСЕ группы (включая группы окружности, прямоугольника, многоугольника и эллипса)
        self.cartesian_group.hide()
        self.polar_group.hide()
        self.circle_center_radius_group.hide()
        self.circle_center_diameter_group.hide()
        self.circle_two_points_group.hide()
        self.circle_three_points_group.hide()
        self.arc_three_points_group.hide()
        self.arc_center_angles_group.hide()
        self.rectangle_point_size_group.hide()
        self.rectangle_center_size_group.hide()
        self.rectangle_fillets_group.hide()
        self.polygon_center_radius_vertices_group.hide()
        self.ellipse_center_radii_group.hide()
        self.ellipse_three_points_group.hide()
        
        # Показываем нужную группу
        method_name = self.arc_method_combo.currentText()
        if method_name == "Три точки (начало, вторая точка, конец)":
            self.arc_three_points_group.show()
        elif method_name == "Центр, начальный угол, конечный угол":
            self.start_point_label_widget.setText("Центр (x, y):")
            self.arc_center_angles_group.show()
        
        # Не обновляем точки ввода автоматически - только при изменении значений в полях
    
    def on_arc_coordinates_changed(self):
        """Обработчик изменения координат дуги"""
        # Получаем точки ввода в зависимости от метода создания
        method_name = self.arc_method_combo.currentText()
        start_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        input_points = [start_point]
        
        if method_name == "Три точки (начало, вторая точка, конец)":
            point2 = QPointF(self.arc_point2_x_spin.value(), self.arc_point2_y_spin.value())
            point3 = QPointF(self.arc_point3_x_spin.value(), self.arc_point3_y_spin.value())
            input_points.append(point2)
            input_points.append(point3)
        # Для метода "Центр, начальный угол, конечный угол" показываем только центр
        
        # Устанавливаем точки для визуализации
        self.canvas.set_input_points(input_points)
    
    def change_rectangle_method(self, method_name):
        """Изменяет метод создания прямоугольника"""
        method_map = {
            "Две противоположные точки": "two_points",
            "Одна точка, ширина и высота": "point_size",
            "Центр, ширина и высота": "center_size",
            "С фасками/скруглениями при создании": "with_fillets"
        }
        method = method_map.get(method_name, "two_points")
        self.canvas.set_rectangle_creation_method(method)
        self.update_rectangle_input_fields()
        # Очищаем точки ввода при смене метода
        self.canvas.clear_input_points()
    
    def update_rectangle_input_fields(self):
        """Обновляет отображение полей ввода в зависимости от метода создания прямоугольника"""
        # Показываем группу "Ввод координат"
        self.input_group.show()
        # Обновляем метку для прямоугольника
        self.start_point_label_widget.setText("Начальная точка (x, y):")
        self.start_point_label_widget.show()
        self.start_x_spin.show()
        self.start_y_spin.show()
        
        # Скрываем ВСЕ группы (включая группы окружности, дуги, многоугольника и эллипса)
        self.cartesian_group.hide()
        self.polar_group.hide()
        self.circle_center_radius_group.hide()
        self.circle_center_diameter_group.hide()
        self.circle_two_points_group.hide()
        self.circle_three_points_group.hide()
        self.arc_three_points_group.hide()
        self.arc_center_angles_group.hide()
        self.rectangle_point_size_group.hide()
        self.rectangle_center_size_group.hide()
        self.rectangle_fillets_group.hide()
        self.polygon_center_radius_vertices_group.hide()
        self.ellipse_center_radii_group.hide()
        self.ellipse_three_points_group.hide()
        
        # Показываем нужную группу
        method_name = self.rectangle_method_combo.currentText()
        if method_name == "Две противоположные точки":
            # Используем обычные поля для конечной точки
            self.end_point_label_widget.show()  # Показываем метку "Конечная точка"
            if self.coordinate_system == "cartesian":
                self.cartesian_group.show()
                self.polar_group.hide()
            else:
                self.cartesian_group.hide()
                self.polar_group.show()
        elif method_name == "Одна точка, ширина и высота":
            self.end_point_label_widget.hide()  # Скрываем метку
            self.rectangle_point_size_group.show()
        elif method_name == "Центр, ширина и высота":
            self.start_point_label_widget.setText("Центр (x, y):")
            self.end_point_label_widget.hide()  # Скрываем метку
            self.rectangle_center_size_group.show()
        elif method_name == "С фасками/скруглениями при создании":
            # Используем обычные поля для конечной точки + радиус скругления
            self.end_point_label_widget.show()  # Показываем метку "Конечная точка"
            if self.coordinate_system == "cartesian":
                self.cartesian_group.show()
                self.polar_group.hide()
            else:
                self.cartesian_group.hide()
                self.polar_group.show()
            self.rectangle_fillets_group.show()
        
        # Не обновляем точки ввода автоматически - только при изменении значений в полях
    
    def on_rectangle_coordinates_changed(self):
        """Обработчик изменения координат прямоугольника"""
        # Получаем точки ввода в зависимости от метода создания
        method_name = self.rectangle_method_combo.currentText()
        start_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        input_points = [start_point]
        
        if method_name == "Две противоположные точки":
            if self.coordinate_system == "cartesian":
                end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
            else:
                # Преобразуем полярные координаты в декартовы
                radius = self.radius_spin.value()
                angle = self.angle_spin.value()
                if self.angle_units == "degrees":
                    angle_rad = math.radians(angle)
                else:
                    angle_rad = angle
                delta_x = radius * math.cos(angle_rad)
                delta_y = radius * math.sin(angle_rad)
                end_point = QPointF(start_point.x() + delta_x, start_point.y() + delta_y)
            input_points.append(end_point)
        elif method_name == "Одна точка, ширина и высота":
            width = self.rectangle_width_spin.value()
            height = self.rectangle_height_spin.value()
            end_point = QPointF(start_point.x() + width, start_point.y() + height)
            input_points.append(end_point)
        elif method_name == "Центр, ширина и высота":
            width = self.rectangle_center_width_spin.value()
            height = self.rectangle_center_height_spin.value()
            half_width = width / 2.0
            half_height = height / 2.0
            top_left = QPointF(start_point.x() - half_width, start_point.y() - half_height)
            bottom_right = QPointF(start_point.x() + half_width, start_point.y() + half_height)
            input_points = [top_left, bottom_right]
        elif method_name == "С фасками/скруглениями при создании":
            if self.coordinate_system == "cartesian":
                end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
            else:
                # Преобразуем полярные координаты в декартовы
                radius = self.radius_spin.value()
                angle = self.angle_spin.value()
                if self.angle_units == "degrees":
                    angle_rad = math.radians(angle)
                else:
                    angle_rad = angle
                delta_x = radius * math.cos(angle_rad)
                delta_y = radius * math.sin(angle_rad)
                end_point = QPointF(start_point.x() + delta_x, start_point.y() + delta_y)
            input_points.append(end_point)
        
        # Устанавливаем точки для визуализации
        self.canvas.set_input_points(input_points)
        
        # Обновляем размеры прямоугольника в сцене, если идет рисование
        # Важно: применяем параметры только к новому прямоугольнику в процессе создания,
        # не к уже зафиксированным объектам
        if self.canvas.scene.is_drawing() and self.canvas.scene._drawing_type == 'rectangle':
            # Дополнительная проверка: убеждаемся, что текущий объект еще не в сцене
            if self.canvas.scene._current_object is not None:
                from widgets.primitives import Rectangle
                if isinstance(self.canvas.scene._current_object, Rectangle):
                    if self.canvas.scene._current_object not in self.canvas.scene._objects:
                        if method_name == "Одна точка, ширина и высота":
                            width = self.rectangle_width_spin.value()
                            height = self.rectangle_height_spin.value()
                            if width > 0 and height > 0:
                                self.canvas.scene.set_rectangle_size(width, height)
                                self.canvas.update()
                        elif method_name == "Центр, ширина и высота":
                            width = self.rectangle_center_width_spin.value()
                            height = self.rectangle_center_height_spin.value()
                            if width > 0 and height > 0:
                                self.canvas.scene.set_rectangle_size(width, height)
                                self.canvas.update()
                        elif method_name == "С фасками/скруглениями при создании":
                            # Применяем fillet_radius только к новому прямоугольнику в процессе создания
                            radius = self.rectangle_fillet_radius_spin.value()
                            if radius >= 0:  # Разрешаем 0 для отключения скругления
                                self.canvas.scene.set_rectangle_fillet_radius(radius)
                                self.canvas.update()
    
    def update_rectangle_on_drawing_start(self, method: str):
        """Обновляет параметры прямоугольника при начале рисования"""
        if self.canvas.scene.is_drawing() and self.canvas.scene._drawing_type == 'rectangle':
            if method == 'point_size':
                width = self.rectangle_width_spin.value()
                height = self.rectangle_height_spin.value()
                if width > 0 and height > 0:
                    self.canvas.scene.set_rectangle_size(width, height)
                    self.canvas.update()
            elif method == 'center_size':
                width = self.rectangle_center_width_spin.value()
                height = self.rectangle_center_height_spin.value()
                if width > 0 and height > 0:
                    self.canvas.scene.set_rectangle_size(width, height)
                    self.canvas.update()
            elif method == 'with_fillets':
                radius = self.rectangle_fillet_radius_spin.value()
                if radius > 0:
                    self.canvas.scene.set_rectangle_fillet_radius(radius)
                    self.canvas.update()
    
    def update_circle_input_fields(self):
        """Обновляет отображение полей ввода в зависимости от метода создания окружности"""
        # Обновляем метку для окружности
        self.start_point_label_widget.setText("Центр (x, y):")
        
        # Скрываем метку "Конечная точка" для окружности
        self.end_point_label_widget.hide()
        
        # Скрываем ВСЕ группы (включая группы дуги, прямоугольника, многоугольника и эллипса)
        self.cartesian_group.hide()
        self.polar_group.hide()
        self.circle_center_radius_group.hide()
        self.circle_center_diameter_group.hide()
        self.circle_two_points_group.hide()
        self.circle_three_points_group.hide()
        self.arc_three_points_group.hide()
        self.arc_center_angles_group.hide()
        self.rectangle_point_size_group.hide()
        self.rectangle_center_size_group.hide()
        self.rectangle_fillets_group.hide()
        self.polygon_center_radius_vertices_group.hide()
        self.ellipse_center_radii_group.hide()
        self.ellipse_three_points_group.hide()
        
        # Показываем нужную группу
        method_name = self.circle_method_combo.currentText()
        if method_name == "Центр и радиус":
            self.circle_center_radius_group.show()
        elif method_name == "Центр и диаметр":
            self.circle_center_diameter_group.show()
        elif method_name == "Две точки":
            self.circle_two_points_group.show()
        elif method_name == "Три точки на окружности":
            self.circle_three_points_group.show()
        
        # Не обновляем точки ввода автоматически - только при изменении значений в полях
    
    def update_polygon_input_fields(self):
        """Обновляет отображение полей ввода для многоугольника"""
        # Обновляем метку для многоугольника
        self.start_point_label_widget.setText("Центр (x, y):")
        
        # Скрываем метку "Конечная точка" для многоугольника
        self.end_point_label_widget.hide()
        
        # Скрываем ВСЕ группы
        self.cartesian_group.hide()
        self.polar_group.hide()
        self.circle_center_radius_group.hide()
        self.circle_center_diameter_group.hide()
        self.circle_two_points_group.hide()
        self.circle_three_points_group.hide()
        self.arc_three_points_group.hide()
        self.arc_center_angles_group.hide()
        self.rectangle_point_size_group.hide()
        self.rectangle_center_size_group.hide()
        self.rectangle_fillets_group.hide()
        self.ellipse_center_radii_group.hide()
        self.ellipse_three_points_group.hide()
        
        # Показываем группу многоугольника
        self.polygon_method_group.show()
        self.polygon_center_radius_vertices_group.show()
    
    def update_spline_input_fields(self):
        """Обновляет отображение полей ввода для сплайна"""
        # Скрываем всю группу "Ввод координат"
        self.input_group.hide()
        
        # Показываем группу сплайна (она находится в tools_group, вне input_group)
        if hasattr(self, 'spline_control_points_group'):
            self.spline_control_points_group.show()
    
    def on_polygon_method_changed(self):
        """Обработчик изменения способа создания многоугольника"""
        method_index = self.polygon_method_combo.currentIndex()
        if method_index == 0:
            # Центр и радиус курсором
            self.canvas.set_polygon_creation_method('center_radius_vertices')
        elif method_index == 1:
            # Вписанная окружность с ручным вводом
            self.canvas.set_polygon_creation_method('inscribed_manual')
        elif method_index == 2:
            # Описанная окружность с ручным вводом
            self.canvas.set_polygon_creation_method('circumscribed_manual')
    
    def on_polygon_coordinates_changed(self):
        """Обработчик изменения координат многоугольника"""
        # Получаем центр
        center_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        input_points = [center_point]
        
        # Получаем радиус и количество вершин
        radius = self.polygon_radius_spin.value()
        num_vertices = self.polygon_num_vertices_spin.value()
        
        # Устанавливаем параметры в canvas
        self.canvas.set_polygon_num_vertices(num_vertices)
        
        # Если идет рисование, обновляем радиус
        if self.canvas.scene.is_drawing() and self.canvas.scene._drawing_type == 'polygon':
            method = self.canvas.scene._polygon_creation_method or 'center_radius_vertices'
            if method in ['inscribed_manual', 'circumscribed_manual']:
                # Для ручного ввода радиуса обновляем радиус объекта
                if radius > 0:
                    self.canvas.scene.set_polygon_radius(radius)
                    self.canvas.update()
        
        # Вычисляем точку на окружности для визуализации
        import math
        if radius > 0:
            angle = 0  # Начинаем с верхней точки
            x = center_point.x() + radius * math.cos(angle - math.pi / 2)
            y = center_point.y() + radius * math.sin(angle - math.pi / 2)
            input_points.append(QPointF(x, y))
        
        # Устанавливаем точки для визуализации
        self.canvas.set_input_points(input_points)
    
    def on_circle_coordinates_changed(self):
        """Обработчик изменения координат окружности"""
        # Получаем точки ввода в зависимости от метода создания
        method_name = self.circle_method_combo.currentText()
        center_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        input_points = [center_point]
        
        if method_name == "Две точки":
            point2 = QPointF(self.circle_point2_x_spin.value(), self.circle_point2_y_spin.value())
            input_points.append(point2)
        elif method_name == "Три точки на окружности":
            point2 = QPointF(self.circle_point2_x_spin_3p.value(), self.circle_point2_y_spin_3p.value())
            point3 = QPointF(self.circle_point3_x_spin.value(), self.circle_point3_y_spin.value())
            input_points.append(point2)
            input_points.append(point3)
        
        # Устанавливаем точки для визуализации
        self.canvas.set_input_points(input_points)
    
    def change_ellipse_method(self, method_name):
        """Изменяет метод создания эллипса"""
        method_map = {
            "Центр и радиусы": "center_radii",
            "Три точки на эллипсе": "three_points"
        }
        method = method_map.get(method_name, "center_radii")
        self.canvas.set_ellipse_creation_method(method)
        self.update_ellipse_input_fields()
        # Очищаем точки ввода при смене метода
        self.canvas.clear_input_points()
    
    def update_ellipse_input_fields(self):
        """Обновляет отображение полей ввода в зависимости от метода создания эллипса"""
        # Обновляем метку для эллипса
        self.start_point_label_widget.setText("Центр (x, y):")
        
        # Скрываем метку "Конечная точка" для эллипса
        self.end_point_label_widget.hide()
        
        # Скрываем ВСЕ группы (включая группы окружности, дуги и прямоугольника)
        self.cartesian_group.hide()
        self.polar_group.hide()
        self.circle_center_radius_group.hide()
        self.circle_center_diameter_group.hide()
        self.circle_two_points_group.hide()
        self.circle_three_points_group.hide()
        self.arc_three_points_group.hide()
        self.arc_center_angles_group.hide()
        self.rectangle_point_size_group.hide()
        self.rectangle_center_size_group.hide()
        self.rectangle_fillets_group.hide()
        self.ellipse_center_radii_group.hide()
        self.ellipse_three_points_group.hide()
        
        # Показываем нужную группу
        method_name = self.ellipse_method_combo.currentText()
        if method_name == "Центр и радиусы":
            self.ellipse_center_radii_group.show()
        elif method_name == "Три точки на эллипсе":
            self.ellipse_three_points_group.show()
        
        # Не обновляем точки ввода автоматически - только при изменении значений в полях
    
    def on_ellipse_coordinates_changed(self):
        """Обработчик изменения координат эллипса"""
        # Получаем точки ввода в зависимости от метода создания
        method_name = self.ellipse_method_combo.currentText()
        center_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        input_points = [center_point]
        
        if method_name == "Три точки на эллипсе":
            point2 = QPointF(self.ellipse_point2_x_spin.value(), self.ellipse_point2_y_spin.value())
            point3 = QPointF(self.ellipse_point3_x_spin.value(), self.ellipse_point3_y_spin.value())
            input_points.append(point2)
            input_points.append(point3)
        # Для метода "Центр и радиусы" показываем только центр
        
        # Устанавливаем точки для визуализации
        self.canvas.set_input_points(input_points)
    
    def change_angle_units(self, units):
        self.angle_units = "radians" if units == "Радианы" else "degrees"
        self.update_angle_units()
        self.update_info()
    
    def change_grid_step(self, step):
        self.canvas.set_grid_step(step)
    
    def change_line_width(self, width):
        self.canvas.set_line_width(width)
    
    def change_line_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.canvas.set_line_color(color)
            self.canvas.update()
    
    def change_background_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.canvas.set_background_color(color)
    
    def change_grid_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.canvas.set_grid_color(color)
    
    def update_input_fields(self):
        #  обновляет отображение полей ввода в зависимости от системы координат
        if self.coordinate_system == "cartesian":
            self.cartesian_group.show()
            self.polar_group.hide()
        else:
            self.cartesian_group.hide()
            self.polar_group.show()
            
            # при переключении на полярные координаты преобразуем текущие декартовы координаты
            # ОТНОСИТЕЛЬНО НАЧАЛЬНОЙ ТОЧКИ
            start_x = self.start_x_spin.value()
            start_y = self.start_y_spin.value()
            end_x = self.end_x_spin.value()
            end_y = self.end_y_spin.value()
            
            # вычисляем смещение от начальной точки
            delta_x = end_x - start_x
            delta_y = end_y - start_y
            
            # преобразуем смещение в полярные координаты
            radius = math.sqrt(delta_x**2 + delta_y**2)
            angle = math.atan2(delta_y, delta_x)
            
            if self.angle_units == "degrees":
                angle = math.degrees(angle)
            
            self.radius_spin.blockSignals(True)
            self.angle_spin.blockSignals(True)
            self.radius_spin.setValue(radius)
            self.angle_spin.setValue(angle)
            self.radius_spin.blockSignals(False)
            self.angle_spin.blockSignals(False)
    
    def update_angle_units(self):
        # обновляет единицы измерения углов
        self.angle_label.setText("°" if self.angle_units == "degrees" else "rad")
        
        # конвертируем угол при смене единиц измерения
        if self.coordinate_system == "polar":
            current_angle = self.angle_spin.value()
            if self.angle_units == "degrees":
                # были радианы, стали градусы
                current_angle = math.degrees(current_angle)
            else:
                # были градусы, стали радианы
                current_angle = math.radians(current_angle)
            
            self.angle_spin.blockSignals(True)
            self.angle_spin.setValue(current_angle)
            self.angle_spin.blockSignals(False)
    
    def on_start_coordinates_changed(self):
        """Обработчик изменения начальных координат"""
        # Обновляем точки ввода для окружности, дуги, прямоугольника и эллипса
        if self.canvas.primitive_type == 'circle':
            self.on_circle_coordinates_changed()
        elif self.canvas.primitive_type == 'arc':
            self.on_arc_coordinates_changed()
        elif self.canvas.primitive_type == 'rectangle':
            self.on_rectangle_coordinates_changed()
        elif self.canvas.primitive_type == 'ellipse':
            self.on_ellipse_coordinates_changed()
        elif self.canvas.primitive_type == 'polygon':
            self.on_polygon_coordinates_changed()
        else:
            # Для отрезков используем обычный обработчик
            self.on_coordinates_changed()
    
    def on_coordinates_changed(self):
        # обработчик изменения декартовых координат только предпросмотр
        # Показываем предпросмотр только для отрезков
        if self.canvas.primitive_type != 'line':
            # Для прямоугольника обновляем точки ввода
            if self.canvas.primitive_type == 'rectangle':
                self.on_rectangle_coordinates_changed()
            return
        if self.line_coordinate_system == "cartesian":
            self.preview_coordinates()

    def on_polar_changed(self):
        # обработчик изменения полярных координат только предпросмотр
        # Показываем предпросмотр только для отрезков
        if self.canvas.primitive_type != 'line':
            # Для прямоугольника обновляем точки ввода
            if self.canvas.primitive_type == 'rectangle':
                self.on_rectangle_coordinates_changed()
            return
        if self.line_coordinate_system == "polar":
            self.preview_coordinates()

    def preview_coordinates(self):
        # предпросмотр отрезка без сохранения
        # Показываем предпросмотр только для отрезков
        if self.canvas.primitive_type != 'line':
            return
        
        start_point = QPointF(self.start_x_spin.value(), self.start_y_spin.value())
        
        if self.line_coordinate_system == "cartesian":
            end_point = QPointF(self.end_x_spin.value(), self.end_y_spin.value())
        else:
            # преобразуем полярные координаты в декартовы ОТНОСИТЕЛЬНО НАЧАЛЬНОЙ ТОЧКИ
            radius = self.radius_spin.value()
            angle = self.angle_spin.value()
            
            if self.line_angle_units == "degrees":
                angle_rad = math.radians(angle)
            else:
                angle_rad = angle
            
            # вычисляем смещение от начальной точки
            delta_x = radius * math.cos(angle_rad)
            delta_y = radius * math.sin(angle_rad)
            
            # конечная точка = начальная + смещение
            end_x = start_point.x() + delta_x
            end_y = start_point.y() + delta_y
            end_point = QPointF(end_x, end_y)
        
        # только предпросмотр без сохранения (apply=False)
        self.canvas.set_points_from_input(start_point, end_point, apply=False)
        self.update_info()
    
    def update_info(self):
        """Обновляет информационную панель в зависимости от типа последнего объекта"""
        # Получаем все объекты из сцены
        objects = self.canvas.scene.get_objects()
        
        # Обновляем счетчик объектов
        total_objects = len(objects)
        self.lines_count_label.setText(f"Объектов на экране: {total_objects}")
        
        if not objects:
            # Нет объектов - показываем пустую информацию
            self._clear_info_panel()
            return
        
        # Определяем, какой объект показывать:
        # 1. Если открыт диалог редактирования - показываем редактируемый объект
        # 2. Если есть выделенный объект - показываем его
        # 3. Иначе - показываем последний объект (новый объект)
        obj_to_display = None
        
        # Проверяем, открыт ли диалог редактирования (не только наличие editing_object)
        if (hasattr(self, 'edit_dialog') and 
            self.edit_dialog.isVisible() and 
            hasattr(self.edit_dialog, 'editing_object') and 
            self.edit_dialog.editing_object):
            obj_to_display = self.edit_dialog.editing_object
            # Проверяем, что объект все еще в сцене
            if obj_to_display not in objects:
                obj_to_display = None
        
        if obj_to_display is None and self.selected_objects:
            obj_to_display = self.selected_objects[0]
            # Проверяем, что объект все еще в сцене
            if obj_to_display not in objects:
                obj_to_display = None
        
        # Если не нашли объект для отображения, используем последний (новый объект)
        if obj_to_display is None:
            obj_to_display = objects[-1]
        
        self.update_info_for_object(obj_to_display)
    
    def update_info_for_object(self, obj):
        """Обновляет информационную панель для конкретного объекта"""
        if obj is None:
            self._clear_info_panel()
            return
        
        # Определяем тип объекта и показываем соответствующую информацию
        from widgets.line_segment import LineSegment
        from widgets.primitives import Circle, Arc, Rectangle, Ellipse, Polygon, Spline
        
        if isinstance(obj, LineSegment):
            self._update_line_info(obj)
        elif isinstance(obj, Circle):
            self._update_circle_info(obj)
        elif isinstance(obj, Arc):
            self._update_arc_info(obj)
        elif isinstance(obj, Rectangle):
            self._update_rectangle_info(obj)
        elif isinstance(obj, Ellipse):
            self._update_ellipse_info(obj)
        elif isinstance(obj, Polygon):
            self._update_polygon_info(obj)
        elif isinstance(obj, Spline):
            self._update_spline_info(obj)
        else:
            self._clear_info_panel()
    
    def on_object_edited(self, obj):
        """Обработчик изменения объекта в диалоге редактирования"""
        # Обновляем информацию об объекте в панели
        self._update_info_if_needed(obj)
    
    def on_edit_dialog_closed(self, result):
        """Обработчик закрытия диалога редактирования"""
        # При закрытии диалога обновляем информацию
        # После закрытия диалога показываем последний объект или выделенный
        self.update_info()
    
    def _update_info_if_needed(self, obj):
        """Обновляет информацию в панели, если объект отображается"""
        if obj is None:
            return
        
        objects = self.canvas.scene.get_objects()
        if obj not in objects:
            return
        
        # Определяем, какой объект сейчас отображается в панели информации
        # По умолчанию это последний объект в сцене
        current_displayed_obj = objects[-1] if objects else None
        
        # Обновляем информацию, если:
        # 1. Редактируемый объект - это последний объект (что отображается)
        # 2. Или редактируемый объект выделен (и может отображаться)
        # 3. Или редактируемый объект совпадает с текущим отображаемым
        if current_displayed_obj == obj or obj in self.selected_objects:
            self.update_info_for_object(obj)
    
    def _clear_info_panel(self):
        """Очищает информационную панель"""
        self.info_label1.setText("")
        self.info_value1.setText("")
        self.info_label2.setText("")
        self.info_value2.setText("")
        self.info_label3.setText("")
        self.info_value3.setText("")
        self.info_label4.setText("")
        self.info_value4.setText("")
    
    def _update_line_info(self, line):
        """Обновляет информацию об отрезке"""
        start_x, start_y = line.start_point.x(), line.start_point.y()
        end_x, end_y = line.end_point.x(), line.end_point.y()
        
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.sqrt(dx**2 + dy**2)
        
        if dx != 0 or dy != 0:
            angle_rad = math.atan2(dy, dx)
            if self.line_angle_units == "degrees":
                angle = math.degrees(angle_rad)
                angle_str = f"{angle:.2f}°"
            else:
                angle_str = f"{angle_rad:.2f} rad"
        else:
            angle_str = "0.00°" if self.line_angle_units == "degrees" else "0.00 rad"
        
        self.info_label1.setText("Начальная точка:")
        self.info_value1.setText(f"({start_x:.2f}, {start_y:.2f})")
        self.info_label2.setText("Конечная точка:")
        self.info_value2.setText(f"({end_x:.2f}, {end_y:.2f})")
        self.info_label3.setText("Длина:")
        self.info_value3.setText(f"{length:.2f}")
        self.info_label4.setText("Угол наклона:")
        self.info_value4.setText(angle_str)
    
    def _update_circle_info(self, circle):
        """Обновляет информацию об окружности"""
        center_x, center_y = circle.center.x(), circle.center.y()
        radius = circle.radius
        
        # Периметр окружности
        perimeter = 2 * math.pi * radius
        # Площадь окружности
        area = math.pi * radius * radius
        
        self.info_label1.setText("Центр:")
        self.info_value1.setText(f"({center_x:.2f}, {center_y:.2f})")
        self.info_label2.setText("Радиус:")
        self.info_value2.setText(f"{radius:.2f}")
        self.info_label3.setText("Периметр:")
        self.info_value3.setText(f"{perimeter:.2f}")
        self.info_label4.setText("Площадь:")
        self.info_value4.setText(f"{area:.2f}")
    
    def _update_arc_info(self, arc):
        """Обновляет информацию о дуге"""
        center_x, center_y = arc.center.x(), arc.center.y()
        radius_x = arc.radius_x
        radius_y = arc.radius_y
        start_angle = arc.start_angle
        end_angle = arc.end_angle
        
        # Длина дуги (приблизительно)
        angle_span = abs(end_angle - start_angle)
        if angle_span > 180:
            angle_span = 360 - angle_span
        avg_radius = (radius_x + radius_y) / 2
        arc_length = (angle_span * math.pi / 180) * avg_radius
        
        self.info_label1.setText("Центр:")
        self.info_value1.setText(f"({center_x:.2f}, {center_y:.2f})")
        self.info_label2.setText("Радиусы:")
        self.info_value2.setText(f"X: {radius_x:.2f}, Y: {radius_y:.2f}")
        self.info_label3.setText("Углы:")
        self.info_value3.setText(f"Начало: {start_angle:.2f}°, Конец: {end_angle:.2f}°")
        self.info_label4.setText("Длина дуги:")
        self.info_value4.setText(f"{arc_length:.2f}")
    
    def _update_rectangle_info(self, rectangle):
        """Обновляет информацию о прямоугольнике"""
        bbox = rectangle.get_bounding_box()
        width = bbox.width()
        height = bbox.height()
        top_left_x = bbox.left()
        top_left_y = bbox.top()
        bottom_right_x = bbox.right()
        bottom_right_y = bbox.bottom()
        
        # Периметр
        perimeter = 2 * (width + height)
        # Площадь
        area = width * height
        
        self.info_label1.setText("Верхний левый угол:")
        self.info_value1.setText(f"({top_left_x:.2f}, {top_left_y:.2f})")
        self.info_label2.setText("Нижний правый угол:")
        self.info_value2.setText(f"({bottom_right_x:.2f}, {bottom_right_y:.2f})")
        self.info_label3.setText("Размеры:")
        self.info_value3.setText(f"Ширина: {width:.2f}, Высота: {height:.2f}")
        self.info_label4.setText("Площадь:")
        self.info_value4.setText(f"{area:.2f}")
    
    def _update_ellipse_info(self, ellipse):
        """Обновляет информацию об эллипсе"""
        center_x, center_y = ellipse.center.x(), ellipse.center.y()
        radius_x = ellipse.radius_x
        radius_y = ellipse.radius_y
        
        # Периметр эллипса (приблизительно по формуле Рамануджана)
        h = ((radius_x - radius_y) / (radius_x + radius_y)) ** 2
        perimeter = math.pi * (radius_x + radius_y) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))
        # Площадь эллипса
        area = math.pi * radius_x * radius_y
        
        self.info_label1.setText("Центр:")
        self.info_value1.setText(f"({center_x:.2f}, {center_y:.2f})")
        self.info_label2.setText("Радиусы:")
        self.info_value2.setText(f"X: {radius_x:.2f}, Y: {radius_y:.2f}")
        self.info_label3.setText("Периметр:")
        self.info_value3.setText(f"{perimeter:.2f}")
        self.info_label4.setText("Площадь:")
        self.info_value4.setText(f"{area:.2f}")
    
    def _update_polygon_info(self, polygon):
        """Обновляет информацию о многоугольнике"""
        center_x, center_y = polygon.center.x(), polygon.center.y()
        radius = polygon.radius
        num_vertices = polygon.num_vertices
        
        # Периметр многоугольника (сумма длин всех сторон)
        vertices = polygon.get_vertices()
        perimeter = 0.0
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            perimeter += math.sqrt(dx*dx + dy*dy)
        
        # Площадь многоугольника (формула площади через координаты вершин)
        area = 0.0
        for i in range(len(vertices)):
            p1 = vertices[i]
            p2 = vertices[(i + 1) % len(vertices)]
            area += p1.x() * p2.y() - p2.x() * p1.y()
        area = abs(area) / 2.0
        
        self.info_label1.setText("Центр:")
        self.info_value1.setText(f"({center_x:.2f}, {center_y:.2f})")
        self.info_label2.setText("Радиус:")
        self.info_value2.setText(f"{radius:.2f}")
        self.info_label3.setText("Количество углов:")
        self.info_value3.setText(f"{num_vertices}")
        self.info_label4.setText("Периметр:")
        self.info_value4.setText(f"{perimeter:.2f}")
    
    def _update_spline_info(self, spline):
        """Обновляет информацию о сплайне"""
        num_points = len(spline.control_points)
        
        if num_points == 0:
            self._clear_info_panel()
            return
        
        # Вычисляем длину сплайна (приблизительно)
        length = 0.0
        if num_points >= 2:
            num_samples = max(100, num_points * 20)
            prev_point = spline._get_point_on_spline(0)
            for i in range(1, num_samples):
                t = i / (num_samples - 1) if num_samples > 1 else 0
                curr_point = spline._get_point_on_spline(t)
                dx = curr_point.x() - prev_point.x()
                dy = curr_point.y() - prev_point.y()
                length += math.sqrt(dx*dx + dy*dy)
                prev_point = curr_point
        
        # Первая и последняя контрольные точки
        first_point = spline.control_points[0]
        last_point = spline.control_points[-1]
        
        self.info_label1.setText("Количество точек:")
        self.info_value1.setText(f"{num_points}")
    
    def _create_primitive_icon(self, primitive_name: str) -> QIcon:
        """Создает иконку для типа примитива"""
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        
        margin = 3
        width = size - 2 * margin
        height = size - 2 * margin
        center_x = size / 2
        center_y = size / 2
        
        if primitive_name == "Отрезок":
            # Линия
            painter.drawLine(margin, center_y, size - margin, center_y)
        elif primitive_name == "Окружность":
            # Круг
            painter.drawEllipse(margin, margin, width, height)
        elif primitive_name == "Дуга":
            # Дуга (четверть окружности)
            rect = QRectF(margin, margin, width, height)
            painter.drawArc(rect, 0, 90 * 16)  # 90 градусов
        elif primitive_name == "Прямоугольник":
            # Прямоугольник
            painter.drawRect(margin, margin, width, height)
        elif primitive_name == "Эллипс":
            # Эллипс
            painter.drawEllipse(margin + 2, margin, width - 4, height)
        elif primitive_name == "Многоугольник":
            # Шестиугольник (как пример многоугольника)
            num_vertices = 6
            radius = min(width, height) / 2 - 1
            points = []
            for i in range(num_vertices):
                angle = 2 * math.pi * i / num_vertices - math.pi / 2
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                points.append((x, y))
            
            for i in range(num_vertices):
                start = points[i]
                end = points[(i + 1) % num_vertices]
                painter.drawLine(int(start[0]), int(start[1]), int(end[0]), int(end[1]))
        elif primitive_name == "Сплайн":
            # Волнистая линия (сплайн)
            num_points = 8
            for i in range(num_points - 1):
                x1 = margin + (width / (num_points - 1)) * i
                y1 = center_y + 3 * math.sin(i * math.pi / 2)
                x2 = margin + (width / (num_points - 1)) * (i + 1)
                y2 = center_y + 3 * math.sin((i + 1) * math.pi / 2)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        painter.end()
        return QIcon(pixmap)
        self.info_label2.setText("Первая точка:")
        self.info_value2.setText(f"({first_point.x():.2f}, {first_point.y():.2f})")
        self.info_label3.setText("Последняя точка:")
        self.info_value3.setText(f"({last_point.x():.2f}, {last_point.y():.2f})")
        self.info_label4.setText("Длина:")
        self.info_value4.setText(f"{length:.2f}")
        self.info_value4.setText(f"{length:.2f}")