"""
UI панели для управления стилями линий
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QGroupBox, QPushButton, QDoubleSpinBox, QSpinBox, QListWidget,
                               QListWidgetItem, QMessageBox, QDialog, QFormLayout,
                               QDialogButtonBox, QLineEdit, QCheckBox, QStyledItemDelegate,
                               QToolTip, QStyleOptionViewItem, QFrame, QApplication)
from PySide6.QtCore import Qt, Signal, QSize, QEvent, QPoint, QRect, QTimer, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QHelpEvent, QPainterPath, QScreen
import math

from widgets.line_style import LineStyleManager, LineType


class StylePreviewWidget(QWidget):
    """Виджет для отображения превью стиля линии"""
    def __init__(self, style=None, width=100, height=20, parent=None):
        super().__init__(parent)
        self.style = style
        self.preview_width = width
        self.preview_height = height
        self.setFixedSize(width, height)
    
    def set_style(self, style):
        self.style = style
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Рисуем белый фон
        painter.fillRect(self.rect(), Qt.white)
        
        if self.style:
            pen = self.style.get_pen()
            painter.setPen(pen)
            
            # Рисуем линию в зависимости от типа
            y = self.height() // 2
            margin = 5
            start_x = margin
            end_x = self.width() - margin
            start_point = QPointF(start_x, y)
            end_point = QPointF(end_x, y)
            
            line_type = self.style.line_type
            if line_type == LineType.SOLID_WAVY:
                self._draw_wavy_line(painter, start_point, end_point, pen)
            elif line_type == LineType.SOLID_THIN_BROKEN:
                self._draw_broken_line(painter, start_point, end_point, pen)
            elif line_type == LineType.DASHED:
                self._draw_dashed_line(painter, start_point, end_point, pen)
            elif line_type in [LineType.DASH_DOT_THICK, LineType.DASH_DOT_THIN, LineType.DASH_DOT_TWO_DOTS]:
                self._draw_dash_dot_line(painter, start_point, end_point, pen)
            else:
                # Сплошная линия
                painter.drawLine(start_point, end_point)
        else:
            # Рисуем пустую линию
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            y = self.height() // 2
            margin = 5
            painter.drawLine(margin, y, self.width() - margin, y)
    
    def _draw_wavy_line(self, painter, start_point, end_point, pen):
        """Отрисовывает волнистую линию (плавная синусоида) - как в coordinate_system"""
        # Вычисляем длину и угол линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx)
        
        if length < 1:
            return
        
        # Амплитуда волны - используем из стиля, если доступна
        if self.style and hasattr(self.style, 'wavy_amplitude_mm'):
            amplitude_mm = self.style.wavy_amplitude_mm
        else:
            # Автоматический расчет по ГОСТ
            main_thickness_mm = 0.8  # Толщина основной линии по ГОСТ
            line_thickness_mm = pen.widthF() * 25.4 / 96  # Текущая толщина в мм
            # Амплитуда пропорциональна толщине линии
            amplitude_mm = (main_thickness_mm / 2.5) * (line_thickness_mm / 0.4)
        
        amplitude_px = (amplitude_mm * 96) / 25.4
        
        # Длина волны: примерно 4-6 амплитуд для плавной волны
        wave_length_px = amplitude_px * 5
        
        # Количество полных волн
        num_waves = max(1, int(length / wave_length_px))
        actual_wave_length = length / num_waves if num_waves > 0 else length
        
        # Создаем путь для волнистой линии с плавной синусоидой
        path = QPainterPath()
        
        # Единичные векторы направления линии и перпендикуляра
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        perp_cos = -sin_angle  # Перпендикулярный вектор
        perp_sin = cos_angle
        
        # Создаем достаточное количество точек для плавной кривой
        num_points = max(50, int(length / 2))  # Минимум 50 точек для плавности
        
        for i in range(num_points + 1):
            t = i / num_points
            # Позиция вдоль линии
            along_line = t * length
            
            # Синусоидальное смещение
            wave_phase = (along_line / actual_wave_length) * 2 * math.pi
            wave_offset = amplitude_px * math.sin(wave_phase)
            
            # Вычисляем координаты точки
            x = start_point.x() + along_line * cos_angle + wave_offset * perp_cos
            y = start_point.y() + along_line * sin_angle + wave_offset * perp_sin
            
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        
        # Рисуем путь только обводкой, без заливки
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)  # Отключаем заливку
        painter.drawPath(path)
    
    def _draw_broken_line(self, painter, start_point, end_point, pen):
        """Отрисовывает сплошную линию с изломами (острые углы, зигзаг) - как в coordinate_system"""
        # Вычисляем длину и угол линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx)
        
        if length < 1:
            return
        
        # Количество зигзагов и шаг из стиля
        zigzag_count = self.style.zigzag_count if self.style and hasattr(self.style, 'zigzag_count') else 1
        zigzag_count = max(1, int(zigzag_count))  # Минимум 1 зигзаг
        zigzag_step_mm = self.style.zigzag_step_mm if self.style and hasattr(self.style, 'zigzag_step_mm') else 4.0
        
        # Параметры зигзага: фиксированные размеры в миллиметрах (не зависят от длины линии)
        # Стандартная высота зигзага: 3.5 мм
        zigzag_height_mm = 3.5
        # Стандартная ширина одного зигзага: 4.0 мм
        zigzag_width_mm = 4.0
        dpi = 96
        # Конвертируем миллиметры в пиксели (независимо от масштаба)
        zigzag_height = (zigzag_height_mm * dpi) / 25.4
        zigzag_length_single = (zigzag_width_mm * dpi) / 25.4
        zigzag_step = (zigzag_step_mm * dpi) / 25.4  # Шаг между зигзагами в пикселях
        
        # Общая длина области зигзагов: ширина одного зигзага * количество + шаги между ними
        total_zigzag_length = zigzag_length_single * zigzag_count + zigzag_step * (zigzag_count - 1)
        
        # Вычисляем длину прямых участков по бокам
        # Если зигзаги длиннее линии, уменьшаем шаг
        if total_zigzag_length > length * 0.9:
            max_length = length * 0.9
            if zigzag_count > 1:
                zigzag_step = (max_length - zigzag_length_single * zigzag_count) / (zigzag_count - 1)
                zigzag_step = max(zigzag_step, zigzag_length_single * 0.5)  # Минимальный шаг
            total_zigzag_length = zigzag_length_single * zigzag_count + zigzag_step * (zigzag_count - 1)
        
        straight_length = (length - total_zigzag_length) / 2  # Длина прямых участков по бокам
        
        # Единичные векторы направления линии и перпендикуляра
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        perp_cos = -sin_angle
        perp_sin = cos_angle
        
        # Создаем путь с острыми углами
        path = QPainterPath()
        path.moveTo(start_point)
        
        # Первый прямой участок
        zigzag_start = QPointF(
            start_point.x() + straight_length * cos_angle,
            start_point.y() + straight_length * sin_angle
        )
        path.lineTo(zigzag_start)
        
        # Рисуем все зигзаги с шагом между ними
        current_pos = zigzag_start
        for z in range(zigzag_count):
            segment_length_along = zigzag_length_single / 3
            
            # Первый сегмент: вверх на половину высоты
            point1 = QPointF(
                current_pos.x() + segment_length_along * cos_angle + (zigzag_height / 2) * perp_cos,
                current_pos.y() + segment_length_along * sin_angle + (zigzag_height / 2) * perp_sin
            )
            path.lineTo(point1)
            
            # Второй сегмент: вниз на всю высоту
            point2 = QPointF(
                point1.x() + segment_length_along * cos_angle - zigzag_height * perp_cos,
                point1.y() + segment_length_along * sin_angle - zigzag_height * perp_sin
            )
            path.lineTo(point2)
            
            # Третий сегмент: вверх на половину высоты (возврат к прямой линии)
            zigzag_end = QPointF(
                current_pos.x() + zigzag_length_single * cos_angle,
                current_pos.y() + zigzag_length_single * sin_angle
            )
            path.lineTo(zigzag_end)
            
            # Если это не последний зигзаг, добавляем шаг (прямой участок) до следующего зигзага
            if z < zigzag_count - 1:
                current_pos = QPointF(
                    zigzag_end.x() + zigzag_step * cos_angle,
                    zigzag_end.y() + zigzag_step * sin_angle
                )
                path.lineTo(current_pos)
            else:
                current_pos = zigzag_end
        
        # Второй прямой участок до конца
        path.lineTo(end_point)
        
        # Рисуем путь только обводкой, без заливки
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)  # Отключаем заливку
        painter.drawPath(path)
    
    def _draw_dashed_line(self, painter, start_point, end_point, pen):
        """Отрисовывает штриховую линию вручную, разбивая на сегменты - как в coordinate_system"""
        # Вычисляем длину и направление линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return
        
        # Получаем параметры штрихов из стиля (в миллиметрах, мировых координатах)
        dash_length_mm = self.style.dash_length if self.style else 5.0  # Длина штриха в мм
        dash_gap_mm = self.style.dash_gap if self.style else 2.5  # Пробел в мм
        
        # Конвертируем миллиметры в пиксели для превью
        # Используем фиксированный масштаб scale_factor = 1.0 и DPI = 96
        dpi = 96
        scale_factor = 1.0
        dash_length = dash_length_mm * scale_factor
        dash_gap = dash_gap_mm * scale_factor
        
        # Единичный вектор направления линии
        cos_angle = dx / length
        sin_angle = dy / length
        
        # Рисуем штрихи вдоль линии
        current_pos = 0.0
        painter.setPen(pen)
        
        while current_pos < length:
            # Рисуем штрих
            dash_end = min(current_pos + dash_length, length)
            start_seg = QPointF(
                start_point.x() + current_pos * cos_angle,
                start_point.y() + current_pos * sin_angle
            )
            end_seg = QPointF(
                start_point.x() + dash_end * cos_angle,
                start_point.y() + dash_end * sin_angle
            )
            painter.drawLine(start_seg, end_seg)
            
            # Переходим к следующему штриху (пропускаем пробел)
            current_pos += dash_length + dash_gap
    
    def _draw_dash_dot_line(self, painter, start_point, end_point, pen):
        """Отрисовывает штрихпунктирную линию вручную - как в coordinate_system"""
        # Вычисляем длину и направление линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return
        
        # Получаем параметры из стиля (в миллиметрах, мировых координатах)
        dash_length_mm = self.style.dash_length if self.style else 5.0  # Длина штриха в мм
        dash_gap_mm = self.style.dash_gap if self.style else 2.5  # Пробел в мм
        dot_length_mm = self.style.thickness_mm * 0.5 if self.style else 0.4  # Длина точки пропорциональна толщине
        
        # Конвертируем миллиметры в пиксели для превью
        # Используем фиксированный масштаб scale_factor = 1.0
        scale_factor = 1.0
        dash_length = dash_length_mm * scale_factor
        dash_gap = dash_gap_mm * scale_factor
        dot_length = dot_length_mm * scale_factor
        
        # Определяем тип линии для количества точек
        if self.style and self.style.line_type == LineType.DASH_DOT_TWO_DOTS:
            pattern = [dash_length, dash_gap, dot_length, dash_gap, dot_length, dash_gap]
        else:
            pattern = [dash_length, dash_gap, dot_length, dash_gap]
        
        # Единичный вектор направления линии
        cos_angle = dx / length
        sin_angle = dy / length
        
        # Рисуем паттерн вдоль линии
        current_pos = 0.0
        pattern_index = 0
        painter.setPen(pen)
        
        while current_pos < length:
            segment_length = pattern[pattern_index % len(pattern)]
            segment_end = min(current_pos + segment_length, length)
            
            # Определяем, является ли текущий сегмент пробелом
            # Пробелы - это элементы, равные dash_gap
            is_gap = (segment_length == dash_gap)
            
            if not is_gap:
                # Рисуем только штрихи и точки (не пробелы)
                start_seg = QPointF(
                    start_point.x() + current_pos * cos_angle,
                    start_point.y() + current_pos * sin_angle
                )
                end_seg = QPointF(
                    start_point.x() + segment_end * cos_angle,
                    start_point.y() + segment_end * sin_angle
                )
                painter.drawLine(start_seg, end_seg)
            
            current_pos += segment_length
            pattern_index += 1


class StyleTooltipWidget(QFrame):
    """Виджет tooltip с превью стиля линии"""
    def __init__(self, style, parent=None):
        super().__init__(parent)
        self.style = style
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        # Убираем прозрачный фон, используем белый
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #888;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Название стиля
        name_label = QLabel(style.name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        
        # Превью линии
        preview = StylePreviewWidget(style, 250, 50)
        layout.addWidget(preview)
        
        # Информация о типе
        type_label = QLabel(f"Тип: {style.line_type.name}")
        type_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(type_label)
        
        self.setLayout(layout)
        self.adjustSize()


class StyleComboBoxDelegate(QStyledItemDelegate):
    """Делегат для ComboBox с tooltip превью при наведении"""
    def __init__(self, style_manager, parent=None):
        super().__init__(parent)
        self.style_manager = style_manager
        self.tooltip_widget = None
        self.tooltip_timer = QTimer()
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self._hide_tooltip)
        self.current_index = None
    
    def _hide_tooltip(self):
        """Скрывает tooltip виджет"""
        if self.tooltip_widget:
            self.tooltip_widget.hide()
            self.tooltip_widget.deleteLater()
            self.tooltip_widget = None
    
    def helpEvent(self, event, view, option, index):
        """Обрабатывает события помощи (hover) для показа tooltip"""
        if event.type() == QEvent.ToolTip:
            style_name = index.data(Qt.UserRole)
            if not style_name:
                style_name = index.data(Qt.DisplayRole)
            
            if style_name and self.style_manager:
                style = self.style_manager.get_style(style_name)
                if style:
                    # Скрываем предыдущий tooltip
                    self._hide_tooltip()
                    
                    # Создаем новый tooltip виджет
                    self.tooltip_widget = StyleTooltipWidget(style, view)
                    
                    # Позиционируем tooltip рядом с курсором
                    pos = event.globalPos()
                    tooltip_pos = QPoint(pos.x() + 10, pos.y() + 10)
                    
                    # Проверяем границы экрана и корректируем позицию
                    screen = QApplication.primaryScreen()
                    if screen:
                        screen_geometry = screen.availableGeometry()
                        tooltip_size = self.tooltip_widget.size()
                        
                        # Проверяем правую границу
                        if tooltip_pos.x() + tooltip_size.width() > screen_geometry.right():
                            tooltip_pos.setX(pos.x() - tooltip_size.width() - 10)
                        
                        # Проверяем нижнюю границу
                        if tooltip_pos.y() + tooltip_size.height() > screen_geometry.bottom():
                            tooltip_pos.setY(pos.y() - tooltip_size.height() - 10)
                        
                        # Проверяем левую границу
                        if tooltip_pos.x() < screen_geometry.left():
                            tooltip_pos.setX(screen_geometry.left() + 5)
                        
                        # Проверяем верхнюю границу
                        if tooltip_pos.y() < screen_geometry.top():
                            tooltip_pos.setY(screen_geometry.top() + 5)
                    
                    self.tooltip_widget.move(tooltip_pos)
                    self.tooltip_widget.show()
                    
                    # Устанавливаем таймер для автоматического скрытия
                    self.tooltip_timer.stop()
                    self.tooltip_timer.start(5000)  # 5 секунд
                    
                    self.current_index = index
                    return True
        elif event.type() == QEvent.Leave:
            # Скрываем tooltip при уходе курсора
            self._hide_tooltip()
            self.current_index = None
        
        return super().helpEvent(event, view, option, index)


class StyleComboBox(QComboBox):
    """ComboBox с превью стилей"""
    def __init__(self, style_manager, parent=None):
        super().__init__(parent)
        self.style_manager = style_manager
        self.delegate = StyleComboBoxDelegate(style_manager, self)
        self.setup_combobox()
        
        # Устанавливаем кастомный делегат для tooltip превью
        self.setItemDelegate(self.delegate)
        
        # Подключаем сигналы менеджера стилей
        if style_manager:
            style_manager.style_added.connect(self.refresh_styles)
            style_manager.style_removed.connect(self.refresh_styles)
            style_manager.style_changed.connect(self.refresh_styles)
    
    def showPopup(self):
        """Переопределяем для установки обработчика событий на view"""
        super().showPopup()
        # Устанавливаем обработчик событий на view для tooltip
        view = self.view()
        if view:
            view.viewport().installEventFilter(self)
    
    def hidePopup(self):
        """Переопределяем для скрытия tooltip при закрытии списка"""
        # Скрываем tooltip при закрытии выпадающего списка
        if self.delegate:
            self.delegate._hide_tooltip()
        super().hidePopup()
    
    def eventFilter(self, obj, event):
        """Обрабатывает события для показа tooltip"""
        if obj == self.view().viewport():
            if event.type() == QEvent.Leave:
                # Скрываем tooltip при уходе курсора
                if self.delegate:
                    self.delegate._hide_tooltip()
        return super().eventFilter(obj, event)
    
    def setup_combobox(self):
        """Настраивает ComboBox с превью"""
        self.clear()
        if not self.style_manager:
            return
        
        for style in self.style_manager.get_all_styles():
            self.addItem(style.name, style.name)
            # Сохраняем имя стиля в UserRole для делегата
            self.setItemData(self.count() - 1, style.name, Qt.UserRole)
            # Создаем превью для каждого стиля
            preview = StylePreviewWidget(style, 80, 16)
            pixmap = QPixmap(80, 16)
            pixmap.fill(Qt.white)
            preview.render(pixmap)
            self.setItemIcon(self.count() - 1, self._create_icon_from_style(style))
    
    def _create_icon_from_style(self, style):
        """Создает иконку из стиля"""
        pixmap = QPixmap(80, 16)
        pixmap.fill(Qt.white)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if style:
            pen = style.get_pen()
            painter.setPen(pen)
            painter.drawLine(5, 8, 75, 8)
        
        painter.end()
        return pixmap
    
    def refresh_styles(self):
        """Обновляет список стилей"""
        current_text = self.currentText()
        self.setup_combobox()
        # Восстанавливаем выбор
        index = self.findText(current_text)
        if index >= 0:
            self.setCurrentIndex(index)
    
    def get_current_style(self):
        """Возвращает текущий выбранный стиль"""
        style_name = self.currentData()
        if style_name and self.style_manager:
            return self.style_manager.get_style(style_name)
        return None


class ObjectPropertiesPanel(QGroupBox):
    """Панель свойств объекта"""
    style_changed = Signal(object)  # Сигнал при изменении стиля
    
    def __init__(self, style_manager, parent=None):
        super().__init__("Свойства объекта", parent)
        self.style_manager = style_manager
        self.selected_objects = []
        self.canvas = None  # Будет установлен извне
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Выбор стиля
        style_label = QLabel("Стиль линии:")
        layout.addWidget(style_label)
        
        self.style_combo = StyleComboBox(self.style_manager)
        self.style_combo.currentIndexChanged.connect(self.on_style_changed)
        layout.addWidget(self.style_combo)
        
        # Информация о текущем стиле
        self.style_info_label = QLabel("")
        self.style_info_label.setWordWrap(True)
        layout.addWidget(self.style_info_label)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def set_selected_objects(self, objects):
        """Устанавливает выделенные объекты"""
        self.selected_objects = objects
        self.update_display()
    
    def update_display(self):
        """Обновляет отображение панели"""
        if not self.selected_objects:
            self.style_combo.setCurrentIndex(-1)
            self.style_info_label.setText("Нет выделенных объектов")
            return
        
        # Проверяем, все ли объекты имеют один стиль
        styles = set()
        for obj in self.selected_objects:
            if hasattr(obj, 'style') and obj.style:
                styles.add(obj.style.name)
            elif hasattr(obj, 'style_name') and obj.style_name:
                styles.add(obj.style_name)
        
        if len(styles) == 1:
            # Все объекты имеют один стиль
            style_name = list(styles)[0]
            index = self.style_combo.findText(style_name)
            if index >= 0:
                self.style_combo.setCurrentIndex(index)
            self.style_info_label.setText(f"Стиль: {style_name}")
        elif len(styles) > 1:
            # Разные стили
            self.style_combo.setCurrentIndex(-1)
            self.style_info_label.setText("Разные стили")
        else:
            # Нет стилей
            self.style_combo.setCurrentIndex(-1)
            self.style_info_label.setText("Стиль не назначен")
    
    def on_style_changed(self):
        """Обработчик изменения стиля"""
        style = self.style_combo.get_current_style()
        if not style:
            return
        
        # Применяем стиль только к выделенным объектам
        if style and self.selected_objects:
            # Применяем стиль ко всем выделенным объектам
            for obj in self.selected_objects:
                if hasattr(obj, 'style'):
                    # Для уже зафиксированных прямоугольников сохраняем fillet_radius
                    # Скругленные углы применяются только при создании нового прямоугольника
                    from widgets.primitives import Rectangle
                    if isinstance(obj, Rectangle):
                        # Сохраняем текущий fillet_radius перед применением стиля
                        original_fillet_radius = getattr(obj, 'fillet_radius', 0.0)
                        obj.style = style
                        # Восстанавливаем fillet_radius для зафиксированных прямоугольников
                        obj.fillet_radius = original_fillet_radius
                    else:
                        obj.style = style
            # Обновляем отображение панели
            self.update_display()
            # Отправляем сигнал об изменении стиля
            self.style_changed.emit(style)
            # Обновляем canvas
            if self.canvas:
                self.canvas.update()


class StyleManagementPanel(QGroupBox):
    """Панель управления стилями"""
    def __init__(self, style_manager, parent=None):
        super().__init__("Управление стилями", parent)
        self.style_manager = style_manager
        self.init_ui()
        
        # Подключаем сигналы
        if style_manager:
            style_manager.style_added.connect(self.refresh_list)
            style_manager.style_removed.connect(self.refresh_list)
            style_manager.style_changed.connect(self.refresh_list)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Список стилей
        self.style_list = QListWidget()
        self.style_list.itemClicked.connect(self.on_style_selected)
        layout.addWidget(self.style_list)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("Редактировать")
        self.edit_btn.clicked.connect(self.edit_selected_style)
        buttons_layout.addWidget(self.edit_btn)
        
        self.add_btn = QPushButton("Создать")
        self.add_btn.clicked.connect(self.create_style)
        buttons_layout.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_selected_style)
        buttons_layout.addWidget(self.delete_btn)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.refresh_list()
    
    def refresh_list(self):
        """Обновляет список стилей"""
        self.style_list.clear()
        if not self.style_manager:
            return
        
        for style in self.style_manager.get_all_styles():
            item = QListWidgetItem(style.name)
            item.setData(Qt.UserRole, style.name)
            
            # Создаем превью
            preview = StylePreviewWidget(style, 100, 20)
            pixmap = QPixmap(100, 20)
            pixmap.fill(Qt.white)
            preview.render(pixmap)
            item.setIcon(self._create_icon_from_style(style))
            
            # Отмечаем базовые стили ГОСТ
            if style.is_gost_base:
                item.setForeground(QColor(100, 100, 100))
            
            self.style_list.addItem(item)
    
    def _create_icon_from_style(self, style):
        """Создает иконку из стиля"""
        pixmap = QPixmap(100, 20)
        pixmap.fill(Qt.white)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if style:
            pen = style.get_pen()
            painter.setPen(pen)
            painter.drawLine(5, 10, 95, 10)
        
        painter.end()
        return pixmap
    
    def on_style_selected(self, item):
        """Обработчик выбора стиля"""
        self.edit_btn.setEnabled(True)
        style_name = item.data(Qt.UserRole)
        style = self.style_manager.get_style(style_name)
        if style and style.is_gost_base:
            self.delete_btn.setEnabled(False)
        else:
            self.delete_btn.setEnabled(True)
    
    def edit_selected_style(self):
        """Редактирует выбранный стиль"""
        item = self.style_list.currentItem()
        if not item:
            return
        
        style_name = item.data(Qt.UserRole)
        style = self.style_manager.get_style(style_name)
        if not style:
            return
        
        dialog = StyleEditDialog(style, self.style_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_list()
    
    def create_style(self):
        """Создает новый стиль"""
        dialog = StyleEditDialog(None, self.style_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_list()
    
    def delete_selected_style(self):
        """Удаляет выбранный стиль"""
        item = self.style_list.currentItem()
        if not item:
            return
        
        style_name = item.data(Qt.UserRole)
        style = self.style_manager.get_style(style_name)
        
        if not style:
            return
        
        if style.is_gost_base:
            QMessageBox.warning(self, "Ошибка", "Нельзя удалять базовые стили ГОСТ")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить стиль '{style_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.style_manager.remove_style(style_name)
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))


class StyleEditDialog(QDialog):
    """Диалог редактирования стиля"""
    def __init__(self, style=None, style_manager=None, parent=None):
        super().__init__(parent)
        self.style = style
        self.style_manager = style_manager
        self.is_new = style is None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Редактировать стиль" if not self.is_new else "Создать стиль")
        layout = QFormLayout()
        
        # Имя стиля
        self.name_edit = QLineEdit()
        if self.style:
            self.name_edit.setText(self.style.name)
            if self.style.is_gost_base:
                self.name_edit.setEnabled(False)
        layout.addRow("Название:", self.name_edit)
        
        # Тип линии
        self.type_combo = QComboBox()
        for line_type in LineType:
            self.type_combo.addItem(line_type.name, line_type)
        if self.style:
            index = self.type_combo.findData(self.style.line_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            if self.style.is_gost_base:
                self.type_combo.setEnabled(False)
        layout.addRow("Тип линии:", self.type_combo)
        
        # Толщина
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(0.25, 1.4)
        self.thickness_spin.setDecimals(2)
        self.thickness_spin.setSingleStep(0.1)
        self.thickness_spin.setSuffix(" мм")
        if self.style:
            self.thickness_spin.setValue(self.style.thickness_mm)
        else:
            self.thickness_spin.setValue(0.8)
        layout.addRow("Толщина:", self.thickness_spin)
        
        # Длина штриха
        self.dash_length_spin = QDoubleSpinBox()
        self.dash_length_spin.setRange(0.1, 50.0)
        self.dash_length_spin.setDecimals(2)
        self.dash_length_spin.setSingleStep(0.5)
        self.dash_length_spin.setSuffix(" мм")
        if self.style:
            self.dash_length_spin.setValue(self.style.dash_length)
        else:
            self.dash_length_spin.setValue(5.0)
        self.dash_length_label = QLabel("Длина штриха:")
        layout.addRow(self.dash_length_label, self.dash_length_spin)
        
        # Расстояние между штрихами
        self.dash_gap_spin = QDoubleSpinBox()
        self.dash_gap_spin.setRange(0.1, 50.0)
        self.dash_gap_spin.setDecimals(2)
        self.dash_gap_spin.setSingleStep(0.5)
        self.dash_gap_spin.setSuffix(" мм")
        if self.style:
            self.dash_gap_spin.setValue(self.style.dash_gap)
        else:
            self.dash_gap_spin.setValue(2.5)
        self.dash_gap_label = QLabel("Расстояние между штрихами:")
        layout.addRow(self.dash_gap_label, self.dash_gap_spin)
        
        # Количество зигзагов (только для ломаной линии)
        self.zigzag_count_spin = QSpinBox()
        self.zigzag_count_spin.setRange(1, 20)
        self.zigzag_count_spin.setSingleStep(1)
        if self.style:
            self.zigzag_count_spin.setValue(getattr(self.style, 'zigzag_count', 1))
        else:
            self.zigzag_count_spin.setValue(1)
        self.zigzag_count_label = QLabel("Количество зигзагов:")
        layout.addRow(self.zigzag_count_label, self.zigzag_count_spin)
        
        # Шаг между зигзагами (только для ломаной линии)
        self.zigzag_step_spin = QDoubleSpinBox()
        self.zigzag_step_spin.setRange(0.5, 50.0)
        self.zigzag_step_spin.setDecimals(2)
        self.zigzag_step_spin.setSingleStep(0.5)
        self.zigzag_step_spin.setSuffix(" мм")
        if self.style:
            self.zigzag_step_spin.setValue(getattr(self.style, 'zigzag_step_mm', 4.0))
        else:
            self.zigzag_step_spin.setValue(4.0)
        self.zigzag_step_label = QLabel("Шаг между зигзагами:")
        layout.addRow(self.zigzag_step_label, self.zigzag_step_spin)
        
        # Амплитуда волнистой линии (только для волнистой линии)
        self.wavy_amplitude_spin = QDoubleSpinBox()
        self.wavy_amplitude_spin.setRange(0.1, 10.0)
        self.wavy_amplitude_spin.setDecimals(2)
        self.wavy_amplitude_spin.setSingleStep(0.1)
        self.wavy_amplitude_spin.setSuffix(" мм")
        if self.style:
            self.wavy_amplitude_spin.setValue(getattr(self.style, 'wavy_amplitude_mm', 0.32))
        else:
            self.wavy_amplitude_spin.setValue(0.32)
        self.wavy_amplitude_label = QLabel("Амплитуда волны:")
        layout.addRow(self.wavy_amplitude_label, self.wavy_amplitude_spin)
        
        # Превью
        self.preview_widget = StylePreviewWidget(None, 200, 30)
        layout.addRow("Превью:", self.preview_widget)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
        
        # Обновляем превью при изменении параметров
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.type_combo.currentIndexChanged.connect(self.update_preview)
        self.thickness_spin.valueChanged.connect(self.update_preview)
        self.dash_length_spin.valueChanged.connect(self.update_preview)
        self.dash_gap_spin.valueChanged.connect(self.update_preview)
        self.zigzag_count_spin.valueChanged.connect(self.update_preview)
        self.zigzag_step_spin.valueChanged.connect(self.update_preview)
        self.wavy_amplitude_spin.valueChanged.connect(self.update_preview)
        
        # Инициализируем видимость полей
        self.on_type_changed()
        self.update_preview()
    
    def on_type_changed(self):
        """Обновляет видимость полей в зависимости от типа линии"""
        line_type = self.type_combo.currentData()
        
        # Определяем, какие поля нужны для каждого типа линии
        is_broken = line_type == LineType.SOLID_THIN_BROKEN
        is_wavy = line_type == LineType.SOLID_WAVY
        # Поля для штрихов используются только для штриховых и штрихпунктирных линий
        is_dashed = line_type in [LineType.DASHED, LineType.DASH_DOT_THICK, 
                                  LineType.DASH_DOT_THIN, LineType.DASH_DOT_TWO_DOTS]
        
        # Поля для зигзагов (только для ломаной линии)
        self.zigzag_count_label.setVisible(is_broken)
        self.zigzag_count_spin.setVisible(is_broken)
        self.zigzag_step_label.setVisible(is_broken)
        self.zigzag_step_spin.setVisible(is_broken)
        
        # Поля для амплитуды (только для волнистой линии)
        self.wavy_amplitude_label.setVisible(is_wavy)
        self.wavy_amplitude_spin.setVisible(is_wavy)
        
        # Поля для штрихов (только для штриховых и штрихпунктирных линий)
        self.dash_length_label.setVisible(is_dashed)
        self.dash_length_spin.setVisible(is_dashed)
        self.dash_gap_label.setVisible(is_dashed)
        self.dash_gap_spin.setVisible(is_dashed)
    
    def update_preview(self):
        """Обновляет превью стиля"""
        from widgets.line_style import LineStyle
        
        # Создаем временный стиль для превью
        temp_style = LineStyle(
            name="preview",
            line_type=self.type_combo.currentData(),
            thickness_mm=self.thickness_spin.value(),
            dash_length=self.dash_length_spin.value(),
            dash_gap=self.dash_gap_spin.value(),
            zigzag_count=self.zigzag_count_spin.value(),
            zigzag_step_mm=self.zigzag_step_spin.value(),
            wavy_amplitude_mm=self.wavy_amplitude_spin.value()
        )
        self.preview_widget.set_style(temp_style)
    
    def accept(self):
        """Применяет изменения"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название стиля")
            return
        
        try:
            if self.is_new:
                # Создаем новый стиль
                from widgets.line_style import LineStyle
                new_style = LineStyle(
                    name=name,
                    line_type=self.type_combo.currentData(),
                    thickness_mm=self.thickness_spin.value(),
                    dash_length=self.dash_length_spin.value(),
                    dash_gap=self.dash_gap_spin.value(),
                    is_gost_base=False,
                    zigzag_count=self.zigzag_count_spin.value(),
                    zigzag_step_mm=self.zigzag_step_spin.value(),
                    wavy_amplitude_mm=self.wavy_amplitude_spin.value()
                )
                self.style_manager.add_style(new_style)
            else:
                # Обновляем существующий стиль
                if not self.style.is_gost_base:
                    if name != self.style.name:
                        self.style_manager.rename_style(self.style.name, name)
                
                self.style.line_type = self.type_combo.currentData()
                self.style.thickness_mm = self.thickness_spin.value()
                self.style.dash_length = self.dash_length_spin.value()
                self.style.dash_gap = self.dash_gap_spin.value()
                self.style.zigzag_count = self.zigzag_count_spin.value()
                self.style.zigzag_step_mm = self.zigzag_step_spin.value()
                self.style.wavy_amplitude_mm = self.wavy_amplitude_spin.value()
            
            super().accept()
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
