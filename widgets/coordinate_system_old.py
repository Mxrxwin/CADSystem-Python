import math
from PySide6.QtWidgets import QWidget, QApplication, QMenu
from PySide6.QtCore import Qt, QPointF, QPoint, Signal, QRectF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QTransform, QPainterPath

from .line_segment import LineSegment
from .line_style import LineType


class CoordinateSystemWidget(QWidget):
    view_changed = Signal()  # сигнал при изменении вида
    context_menu_requested = Signal(QPoint)  # сигнал для запроса контекстного меню
    selection_changed = Signal(list)  # сигнал при изменении выделения
    line_finished = Signal()  # сигнал при завершении рисования отрезка

    def __init__(self, style_manager=None):
        super().__init__()
        # Шаг сетки в миллиметрах (по умолчанию 20 мм)
        # Сетка рисуется в мировых координатах, где 1 мм = 1 единица
        self.grid_step_mm = 20.0
        self.dpi = 96
        # Шаг сетки в мировых координатах (в миллиметрах)
        self.grid_step = self.grid_step_mm
        self.background_color = QColor(255, 255, 255)
        self.grid_color = QColor(200, 200, 200)
        self.axis_color = QColor(0, 0, 0)
        self.line_color = QColor(0, 0, 0)
        self.line_width = 2
        self.style_manager = style_manager  # Менеджер стилей

        # хранилище всех отрезков
        self.lines = []
        
        # выделенные объекты
        self.selected_lines = set()
        
        # режим выделения (по умолчанию включен)
        self.selection_mode = True

        # текущий рисуемый отрезок
        self.current_line = None
        self.is_drawing = False
        self.current_point = None

        # параметры навигации
        self.pan_mode = False
        self.last_mouse_pos = None
        
        # параметры выделения рамкой
        self.is_selecting = False
        self.selection_start = None  # Начальная точка выделения (экранные координаты)
        self.selection_end = None  # Текущая точка выделения (экранные координаты)
        self.right_button_press_pos = None  # Позиция нажатия правой кнопки для определения клика/перетаскивания
        self.right_button_press_time = None  # Время нажатия правой кнопки
        self.right_button_click_count = 0  # Счетчик кликов ПКМ для определения двойного клика
        self.right_button_click_timer = None  # Таймер для определения двойного клика
        
        # единая система трансформаций
        self.scale_factor = 1.0
        self.min_scale = 0.01  # уменьшаем минимальный масштаб
        self.max_scale = 100.0  # увеличиваем максимальный масштаб
        self.rotation_angle = 0.0  # в градусах
        self.translation = QPointF(0, 0)

        # координаты курсора
        self.cursor_world_coords = None

        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)  # отключаем автоматическое контекстное меню

    def show_context_menu(self, position):
        """Показывает контекстное меню"""
        menu = QMenu(self)
        
        # команды навигации
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
        
        # показываем меню в позиции клика
        menu.exec_(self.mapToGlobal(position))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # фон рисуем без трансформации
        painter.fillRect(self.rect(), self.background_color)

        # применяем текущее преобразование
        transform = self.get_total_transform()
        painter.setTransform(transform)

        # рисуем сетку
        self.draw_grid(painter)

        # рисуем оси координат
        self.draw_axes(painter)

        # рисуем все сохраненные отрезки
        for line in self.lines:
            self.draw_saved_line(painter, line)

        # рисуем текущий отрезок если есть
        if self.current_line:
            self.draw_saved_line(painter, self.current_line)

        # рисуем текущую точку при рисовании
        if self.is_drawing and self.current_point:
            self.draw_current_point(painter)
        
        # рисуем рамку выделения
        if self.is_selecting and self.selection_start and self.selection_end:
            self._draw_selection_rect(painter)
        
        # рисуем рамку выделения
        if self.is_selecting and self.selection_start and self.selection_end:
            self._draw_selection_rect(painter)

    def draw_grid(self, painter):
        painter.setPen(QPen(self.grid_color, 1, Qt.DotLine))

        # получаем видимую область в мировых координатах
        transform, success = self.get_total_transform().inverted()
        if not success:
            return
            
        visible_rect = transform.mapRect(QRectF(self.rect()))

        start_x = math.floor(visible_rect.left() / self.grid_step) * self.grid_step
        end_x = math.ceil(visible_rect.right() / self.grid_step) * self.grid_step
        start_y = math.floor(visible_rect.top() / self.grid_step) * self.grid_step
        end_y = math.ceil(visible_rect.bottom() / self.grid_step) * self.grid_step

        # вертикальные линии
        x = start_x
        while x <= end_x:
            painter.drawLine(x, visible_rect.top(), x, visible_rect.bottom())
            x += self.grid_step

        # горизонтальные линии
        y = start_y
        while y <= end_y:
            painter.drawLine(visible_rect.left(), y, visible_rect.right(), y)
            y += self.grid_step

    def draw_axes(self, painter):
        painter.setPen(QPen(self.axis_color, 2))
        
        # получаем видимую область
        transform, success = self.get_total_transform().inverted()
        if not success:
            return
            
        visible_rect = transform.mapRect(QRectF(self.rect()))

        # оси координат
        painter.drawLine(visible_rect.left(), 0, visible_rect.right(), 0)  # X axis
        painter.drawLine(0, visible_rect.top(), 0, visible_rect.bottom())  # Y axis

        # подписи осей - рисуем в экранных координатах без трансформации
        # Сохраняем текущую трансформацию
        saved_transform = painter.transform()
        # Сбрасываем трансформацию для текста
        painter.resetTransform()
        
        # Преобразуем границы виджета в мировые координаты для правильного размещения подписей
        widget_rect = QRectF(self.rect())
        widget_corners = [
            QPointF(widget_rect.left(), widget_rect.top()),
            QPointF(widget_rect.right(), widget_rect.top()),
            QPointF(widget_rect.right(), widget_rect.bottom()),
            QPointF(widget_rect.left(), widget_rect.bottom())
        ]
        inv_transform, success = self.get_total_transform().inverted()
        if success:
            world_corners = [inv_transform.map(corner) for corner in widget_corners]
            world_right = max(c.x() for c in world_corners)
            world_top = max(c.y() for c in world_corners)  # top в мировых координатах (Y вверх)
        else:
            world_right = visible_rect.right()
            world_top = visible_rect.top()
        
        # Используем позиции относительно видимой области, но в мировых координатах
        # "X" - справа от оси X, немного выше оси
        x_pos_world = QPointF(world_right - 20, 15)
        x_pos_screen = saved_transform.map(x_pos_world)
        # "Y" - выше оси Y, немного справа от оси
        y_pos_world = QPointF(15, world_top - 15)
        y_pos_screen = saved_transform.map(y_pos_world)
        # "0" - в начале координат, немного выше и правее
        zero_pos_world = QPointF(15, 15)
        zero_pos_screen = saved_transform.map(zero_pos_world)
        
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QPen(self.axis_color))
        # Рисуем текст в экранных координатах (текст не будет инвертирован)
        painter.drawText(int(x_pos_screen.x()), int(x_pos_screen.y()), "X")
        painter.drawText(int(y_pos_screen.x()), int(y_pos_screen.y()), "Y")
        painter.drawText(int(zero_pos_screen.x()), int(zero_pos_screen.y()), "0")
        
        # Восстанавливаем трансформацию
        painter.setTransform(saved_transform)

    def draw_saved_line(self, painter, line):
        """Отрисовывает линию с учетом стиля"""
        # Проверяем, выделена ли линия
        is_selected = line in self.selected_lines
        
        if line.style:
            # Используем стиль линии
            pen = line.style.get_pen(scale_factor=self.scale_factor)
            # Если у линии есть legacy цвет, используем его вместо цвета стиля
            if hasattr(line, '_legacy_color') and line._legacy_color != line.style.color:
                pen.setColor(line._legacy_color)
            # Если линия выделена, делаем её более заметной
            if is_selected:
                # Увеличиваем толщину для выделенной линии
                pen.setWidthF(pen.widthF() * 1.5)
                # Делаем цвет более ярким
                color = pen.color()
                color.setAlpha(255)
                pen.setColor(color)
            line_type = line.style.line_type
            
            # Для волнистой линии, линии с изломами и штриховой нужна специальная отрисовка
            if line_type == LineType.SOLID_WAVY:
                self._draw_wavy_line(painter, line.start_point, line.end_point, pen)
            elif line_type == LineType.SOLID_THIN_BROKEN:
                self._draw_broken_line(painter, line.start_point, line.end_point, pen)
            elif line_type == LineType.DASHED:
                self._draw_dashed_line(painter, line.start_point, line.end_point, pen, line.style)
            elif line_type in [LineType.DASH_DOT_THICK, LineType.DASH_DOT_THIN, LineType.DASH_DOT_TWO_DOTS]:
                self._draw_dash_dot_line(painter, line.start_point, line.end_point, pen, line.style)
            else:
                painter.setPen(pen)
                painter.drawLine(line.start_point, line.end_point)
        else:
            # Обратная совместимость - используем старый способ
            pen = QPen(line.color, line.width)
            if is_selected:
                pen.setWidthF(pen.widthF() * 1.5)
            painter.setPen(pen)
            painter.drawLine(line.start_point, line.end_point)
        
        # Рисуем точки на концах
        if is_selected:
            # Выделенные линии - рисуем точки другим цветом
            painter.setBrush(QColor(0, 100, 255))  # Синий для выделенных
        else:
            painter.setBrush(line.color)
        point_size = max(2, 4 / self.scale_factor)  # минимальный размер точки
        painter.drawEllipse(line.start_point, point_size, point_size)
        painter.drawEllipse(line.end_point, point_size, point_size)
        
        # Рисуем рамку выделения вокруг выделенной линии
        if is_selected:
            self._draw_selection_highlight(painter, line)
    
    def _draw_wavy_line(self, painter, start_point, end_point, pen):
        """Отрисовывает волнистую линию (плавная синусоида)"""
        # Вычисляем длину и угол линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx)
        
        if length < 1:
            return
        
        # Амплитуда волны согласно ГОСТ: от S/3 до S/2, где S - толщина основной линии (0.8 мм)
        # Для тонкой линии (0.4 мм) используем пропорциональную амплитуду
        # Используем среднее значение: S/2.5
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
        """Отрисовывает сплошную линию с изломами (острые углы, зигзаг)"""
        # Вычисляем длину и угол линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx)
        
        if length < 1:
            return
        
        # Параметры зигзага: фиксированные размеры в миллиметрах (не зависят от длины линии)
        # Стандартная высота зигзага: 2.5 мм (чуть больше)
        zigzag_height_mm = 3.5
        # Стандартная ширина зигзага: 6.0 мм (фиксированная)
        zigzag_width_mm = 4.0
        dpi = 96
        # Конвертируем миллиметры в пиксели (независимо от масштаба)
        zigzag_height = (zigzag_height_mm * dpi) / 25.4
        zigzag_length = (zigzag_width_mm * dpi) / 25.4
        
        # Вычисляем длину прямых участков по бокам
        # Если зигзаг длиннее линии, делаем его короче
        if zigzag_length > length * 0.8:
            zigzag_length = length * 0.8
        
        straight_length = (length - zigzag_length) / 2  # Длина прямых участков по бокам
        
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
        
        # Центральный зигзаг: 3 сегмента
        # 1. Вверх на половину высоты
        # 2. Вниз на всю высоту
        # 3. Вверх на половину высоты
        # Все три сегмента равной длины вдоль линии
        # Высота зигзага фиксированная (уже вычислена выше в миллиметрах)
        
        # Длина каждого сегмента вдоль линии
        segment_length_along = zigzag_length / 3
        
        # Первый сегмент: вверх на половину высоты
        point1 = QPointF(
            zigzag_start.x() + segment_length_along * cos_angle + (zigzag_height / 2) * perp_cos,
            zigzag_start.y() + segment_length_along * sin_angle + (zigzag_height / 2) * perp_sin
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
            zigzag_start.x() + zigzag_length * cos_angle,
            zigzag_start.y() + zigzag_length * sin_angle
        )
        path.lineTo(zigzag_end)
        
        # Второй прямой участок до конца
        path.lineTo(end_point)
        
        # Рисуем путь только обводкой, без заливки
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)  # Отключаем заливку
        painter.drawPath(path)

    def _draw_dashed_line(self, painter, start_point, end_point, pen, style):
        """Отрисовывает штриховую линию вручную, разбивая на сегменты"""
        # Вычисляем длину и направление линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return
        
        # Получаем параметры штрихов из стиля (в миллиметрах, мировых координатах)
        dash_length = style.dash_length  # Длина штриха в мм
        dash_gap = style.dash_gap  # Пробел в мм
        
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

    def _draw_dash_dot_line(self, painter, start_point, end_point, pen, style):
        """Отрисовывает штрихпунктирную линию вручную"""
        # Вычисляем длину и направление линии
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return
        
        # Получаем параметры из стиля (в миллиметрах, мировых координатах)
        dash_length = style.dash_length  # Длина штриха в мм
        dash_gap = style.dash_gap  # Пробел в мм
        dot_length = style.thickness_mm * 0.5  # Длина точки пропорциональна толщине
        
        # Определяем тип линии для количества точек
        if style.line_type == LineType.DASH_DOT_TWO_DOTS:
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
            # Пробелы - это элементы с нечетными индексами (1, 3, 5...)
            # или элементы, равные dash_gap
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

    def draw_current_point(self, painter):
        painter.setPen(QPen(Qt.blue, 2))
        painter.setBrush(Qt.blue)
        point_size = max(2, 3 / self.scale_factor)  # минимальный размер точки
        painter.drawEllipse(self.current_point, point_size, point_size)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.pan_mode:
                self.last_mouse_pos = event.position()
            else:
                world_pos = self.screen_to_world(event.position())
                
                # Проверяем, кликнули ли по существующей линии (для выделения)
                if not self.is_drawing and self.selection_mode:
                    clicked_line = self._find_line_at_point(world_pos)
                    if clicked_line:
                        # Выделение линии (Ctrl для множественного выделения)
                        if event.modifiers() & Qt.ControlModifier:
                            # Множественное выделение
                            if clicked_line in self.selected_lines:
                                self.selected_lines.remove(clicked_line)
                            else:
                                self.selected_lines.add(clicked_line)
                        else:
                            # Одиночное выделение
                            if clicked_line in self.selected_lines and len(self.selected_lines) == 1:
                                # Если уже выделена одна эта линия, снимаем выделение
                                self.selected_lines.clear()
                            else:
                                self.selected_lines = {clicked_line}
                        self.selection_changed.emit(list(self.selected_lines))
                        self.update()
                        return
                    else:
                        # Клик не по линии - снимаем выделение (если не Ctrl)
                        if not (event.modifiers() & Qt.ControlModifier):
                            if self.selected_lines:
                                self.selected_lines.clear()
                                self.selection_changed.emit([])
                        # Продолжаем выполнение для начала рисования линии
                
                if not self.is_drawing:
                    # Снимаем выделение при начале рисования новой линии
                    if self.selected_lines:
                        self.selected_lines.clear()
                        self.selection_changed.emit([])
                    # Используем стиль из менеджера, если доступен
                    style = None
                    if self.style_manager:
                        style = self.style_manager.get_current_style()
                    self.current_line = LineSegment(world_pos, world_pos, style=style, 
                                                   color=self.line_color, width=self.line_width)
                    # Сохраняем цвет в legacy_color для использования при отрисовке
                    self.current_line._legacy_color = self.line_color
                    self.is_drawing = True
                else:
                    if self.current_line:
                        self.current_line.end_point = world_pos
                        self.lines.append(self.current_line)
                        self.current_line = None
                        # Эмитируем сигнал о завершении рисования отрезка
                        self.line_finished.emit()
                    self.is_drawing = False

                self.current_point = world_pos
                self.update()

        elif event.button() == Qt.RightButton:
            # Правая кнопка - сохраняем позицию для определения клика/перетаскивания
            # Работает всегда, независимо от состояния рисования
            self.right_button_press_pos = event.position()
            self.right_button_press_time = event.timestamp()  # Время нажатия для определения простого клика
            
            # Увеличиваем счетчик кликов
            self.right_button_click_count += 1
            
            # Если это первый клик, запускаем таймер для определения двойного клика
            if self.right_button_click_count == 1:
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_timer = QTimer()
                self.right_button_click_timer.setSingleShot(True)
                self.right_button_click_timer.timeout.connect(self._handle_single_right_click)
                self.right_button_click_timer.start(300)  # 300 мс для определения двойного клика
            elif self.right_button_click_count == 2:
                # Двойной клик - отменяем таймер и обрабатываем двойной клик
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
                # Открываем контекстное меню
                pos_point = QPoint(int(event.position().x()), int(event.position().y()))
                self.show_context_menu(pos_point)
                return
            
            # Пока не начинаем выделение - ждем движения мыши
        
        elif event.button() == Qt.MiddleButton:
            self.last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        self.cursor_world_coords = self.screen_to_world(event.position())
        self.view_changed.emit()
        
        # Проверяем, началось ли перетаскивание правой кнопкой
        if (event.buttons() & Qt.RightButton and self.right_button_press_pos):
            # Проверяем, что переместились достаточно далеко (больше 3 пикселей)
            delta = (event.position() - self.right_button_press_pos).manhattanLength()
            if delta > 3:
                # При перетаскивании отменяем обработку одинарного клика
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
                
                # Начинаем выделение рамкой
                if not self.is_selecting:
                    if not (event.modifiers() & Qt.ControlModifier):
                        # Без Ctrl - снимаем текущее выделение
                        if self.selected_lines:
                            self.selected_lines.clear()
                            self.selection_changed.emit([])
                    self.is_selecting = True
                    self.selection_start = self.right_button_press_pos
                    self.selection_end = event.position()
                    # НЕ сбрасываем right_button_press_pos - он нужен для проверки движения при отпускании
                else:
                    self.selection_end = event.position()
                self.update()
                return
        
        # Обновляем выделение рамкой (правая кнопка мыши)
        if self.is_selecting and self.selection_start and (event.buttons() & Qt.RightButton):
            self.selection_end = event.position()
            self.update()
            return

        if self.pan_mode and event.buttons() & Qt.LeftButton:
            if self.last_mouse_pos:
                delta = event.position() - self.last_mouse_pos
                # панорамирование в экранных координатах проще и стабильнее
                self.translation += delta
                self.last_mouse_pos = event.position()
                self.update()
        elif event.buttons() & Qt.MiddleButton:
            if self.last_mouse_pos:
                delta = event.position() - self.last_mouse_pos
                self.translation += delta
                self.last_mouse_pos = event.position()
                self.update()
        elif self.is_drawing and self.current_line and event.buttons() & Qt.LeftButton:
            world_pos = self.screen_to_world(event.position())
            self.current_point = world_pos
            self.current_line.end_point = world_pos
            self.update()

    def _handle_single_right_click(self):
        """Обрабатывает одинарный клик ПКМ (после таймаута)"""
        # Сбрасываем счетчик
        self.right_button_click_count = 0
        
        # Сбрасываем инструмент (незаконченный отрезок)
        if self.is_drawing:
            self.current_line = None
            self.is_drawing = False
            self.current_point = None
            self.update()
        
        # Сбрасываем позицию нажатия
        self.right_button_press_pos = None
        self.right_button_press_time = None
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            # Если было выделение рамкой - завершаем его
            if self.is_selecting:
                # Завершаем выделение рамкой
                if self.selection_start and self.selection_end:
                    # Преобразуем экранные координаты в мировые
                    start_world = self.screen_to_world(self.selection_start)
                    end_world = self.screen_to_world(self.selection_end)
                    
                    # Создаем прямоугольник выделения
                    selection_rect = QRectF(
                        min(start_world.x(), end_world.x()),
                        min(start_world.y(), end_world.y()),
                        abs(end_world.x() - start_world.x()),
                        abs(end_world.y() - start_world.y())
                    )
                    
                    # Находим все линии, попадающие в рамку
                    if selection_rect.width() > 1 and selection_rect.height() > 1:
                        # Выделяем линии, которые пересекаются с рамкой
                        new_selection = set()
                        for line in self.lines:
                            if self._line_intersects_rect(line, selection_rect):
                                new_selection.add(line)
                        
                        # Обновляем выделение
                        if event.modifiers() & Qt.ControlModifier:
                            # Добавляем к текущему выделению
                            self.selected_lines.update(new_selection)
                        else:
                            # Заменяем выделение
                            self.selected_lines = new_selection
                        
                        self.selection_changed.emit(list(self.selected_lines))
                
                # Сбрасываем выделение рамкой
                self.is_selecting = False
                self.selection_start = None
                self.selection_end = None
                self.update()
                # Сбрасываем позицию нажатия после выделения
                self.right_button_press_pos = None
                self.right_button_press_time = None
                # Сбрасываем счетчик кликов при выделении
                if self.right_button_click_timer:
                    self.right_button_click_timer.stop()
                self.right_button_click_count = 0
        
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self.last_mouse_pos = None

    def wheelEvent(self, event):
        zoom_factor = 1.1
        if event.angleDelta().y() > 0:
            self.zoom_at_point(event.position(), zoom_factor)
        else:
            self.zoom_at_point(event.position(), 1.0 / zoom_factor)

    def zoom_at_point(self, screen_point, factor):
        # масштабирование относительно точки с сохранением положения этой точки
        world_point_before = self.screen_to_world(screen_point)
        
        # применяем масштаб
        self.scale_factor *= factor
        self.scale_factor = max(self.min_scale, min(self.max_scale, self.scale_factor))
        
        world_point_after = self.screen_to_world(screen_point)
        
        # корректируем трансляцию для сохранения положения точки
        delta = world_point_after - world_point_before
        self.translation += QPointF(delta.x() * self.scale_factor, delta.y() * self.scale_factor)

        self.view_changed.emit()
        self.update()

    def get_total_transform(self):
        # возвращает полную матрицу преобразования
        transform = QTransform()
        
        # центрирование (перевод в центр виджета)
        transform.translate(self.width() / 2, self.height() / 2)
        
        # трансляция (панорамирование)
        transform.translate(self.translation.x(), self.translation.y())
        
        # поворот вокруг центра
        transform.rotate(self.rotation_angle)
        
        # масштабирование с инверсией Y (в Qt Y вниз, в математике Y вверх)
        transform.scale(self.scale_factor, -self.scale_factor)
        
        return transform

    def screen_to_world(self, screen_point):
        # преобразует экранные координаты в мировые
        transform, success = self.get_total_transform().inverted()
        if success:
            return transform.map(screen_point)
        return screen_point

    def world_to_screen(self, world_point):
        # преобразует мировые координаты в экранные
        transform = self.get_total_transform()
        return transform.map(world_point)

    def set_pan_mode(self, enabled):
        self.pan_mode = enabled
        self.view_changed.emit()

    def zoom_in(self):
        self.zoom_at_point(QPointF(self.width() / 2, self.height() / 2), 1.2)

    def zoom_out(self):
        self.zoom_at_point(QPointF(self.width() / 2, self.height() / 2), 1.0 / 1.2)

    def show_all(self):
        # показывает все отрезки с правильным учетом поворота
        if not self.lines and not self.current_line:
            self.reset_view()
            return

        # собираем все точки отрезков
        all_points = []
        for line in self.lines:
            all_points.append(line.start_point)
            all_points.append(line.end_point)
        if self.current_line:
            all_points.append(self.current_line.start_point)
            all_points.append(self.current_line.end_point)

        if not all_points:
            return

        # Находим границы всех точек в мировых координатах
        min_x = min(p.x() for p in all_points)
        max_x = max(p.x() for p in all_points)
        min_y = min(p.y() for p in all_points)
        max_y = max(p.y() for p in all_points)

        # Вычисляем центр сцены в мировых координатах
        scene_center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
        scene_width = max_x - min_x
        scene_height = max_y - min_y

        # Создаем углы прямоугольника
        corners = [
            QPointF(min_x, min_y),
            QPointF(max_x, min_y),
            QPointF(max_x, max_y),
            QPointF(min_x, max_y)
        ]
        
        # Применяем поворот к углам прямоугольника относительно центра сцены
        # Это даст нам bounding box повернутого прямоугольника в мировых координатах
        if abs(self.rotation_angle) > 0.01:
            rotation_transform = QTransform()
            rotation_transform.rotate(self.rotation_angle)
            
            # Поворачиваем углы относительно центра сцены
            rotated_corners = []
            for corner in corners:
                relative = corner - scene_center
                rotated_relative = rotation_transform.map(relative)
                rotated_corners.append(rotated_relative + scene_center)
            
            # Находим границы повернутого прямоугольника
            rotated_min_x = min(p.x() for p in rotated_corners)
            rotated_max_x = max(p.x() for p in rotated_corners)
            rotated_min_y = min(p.y() for p in rotated_corners)
            rotated_max_y = max(p.y() for p in rotated_corners)
            
            rotated_width = rotated_max_x - rotated_min_x
            rotated_height = rotated_max_y - rotated_min_y
        else:
            # Если нет поворота, используем исходные размеры
            rotated_width = scene_width
            rotated_height = scene_height
        
        # Добавляем отступ (20% от размеров) после поворота
        padding_x = rotated_width * 0.2 if rotated_width > 0 else 10
        padding_y = rotated_height * 0.2 if rotated_height > 0 else 10
        rotated_width += 2 * padding_x
        rotated_height += 2 * padding_y

        # Вычисляем масштаб для вписывания в виджет
        widget_width = self.width()
        widget_height = self.height()
        
        if rotated_width <= 0 or rotated_height <= 0:
            new_scale = 1.0
        else:
            scale_x = widget_width / rotated_width
            scale_y = widget_height / rotated_height
            new_scale = min(scale_x, scale_y) * 0.9  # 90% для отступов
            new_scale = max(self.min_scale, min(self.max_scale, new_scale))

        # Применяем новый масштаб
        self.scale_factor = new_scale
        
        # Вычисляем трансляцию для центрирования
        # Нужно, чтобы scene_center оказался в центре виджета после всех трансформаций
        # Порядок трансформации: translate(center) -> translate(translation) -> rotate -> scale
        
        widget_center = QPointF(self.width() / 2, self.height() / 2)
        
        # Создаем трансформацию rotate -> scale (с учетом инверсии Y)
        rotation_scale_transform = QTransform()
        rotation_scale_transform.rotate(self.rotation_angle)
        rotation_scale_transform.scale(self.scale_factor, -self.scale_factor)  # Инверсия Y как в get_total_transform
        inv_rotation_scale, success = rotation_scale_transform.inverted()
        
        if success:
            # Правильный подход:
            # Порядок трансформации: translate(center) -> translate(translation) -> rotate -> scale
            # После translate(center), координаты (0,0) в мировых координатах становятся widget_center на экране
            # После translate(translation), координаты (0,0) в мировых координатах становятся widget_center + translation на экране
            # После rotate -> scale, точка scene_center в мировых координатах переходит в:
            # widget_center + translation + (scene_center после rotate -> scale)
            
            # Мы хотим, чтобы эта точка оказалась в widget_center:
            # widget_center + translation + (scene_center после rotate -> scale) = widget_center
            # Поэтому: translation = -(scene_center после rotate -> scale)
            
            # Вычисляем scene_center после rotate -> scale (в экранных координатах)
            # Это будет смещение от (0,0) в мировых координатах после rotate -> scale
            rotated_scaled_center = rotation_scale_transform.map(scene_center)
            
            # translation должен быть таким, чтобы widget_center + translation + rotated_scaled_center = widget_center
            # Поэтому: translation = -rotated_scaled_center
            self.translation = QPointF(-rotated_scaled_center.x(), -rotated_scaled_center.y())
        else:
            # Fallback: просто центрируем без учета поворота (с учетом инверсии Y)
            self.translation = QPointF(-scene_center.x() * self.scale_factor, 
                                      scene_center.y() * self.scale_factor)  # Y инвертирован

        self.view_changed.emit()
        self.update()

    def show_all_preserve_rotation(self):
        # альтернатива show_all, которая сохраняет текущий поворот
        self.show_all()

    def reset_view(self):
        # полностью сбрасывает вид к начальному состоянию
        self.scale_factor = 1.0
        self.rotation_angle = 0
        self.translation = QPointF(0, 0)
        self.view_changed.emit()
        self.update()

    def rotate(self, angle):
        # вращает вид вокруг центра координат (0, 0)
        # Сохраняем текущее положение точки (0, 0) на экране
        origin_world = QPointF(0, 0)
        origin_screen_before = self.world_to_screen(origin_world)
        
        # применяем поворот
        self.rotation_angle += angle
        # нормализуем угол
        self.rotation_angle %= 360
        
        # Вычисляем новое положение точки (0, 0) на экране после поворота
        origin_screen_after = self.world_to_screen(origin_world)
        
        # Корректируем трансляцию, чтобы точка (0, 0) оставалась в том же месте на экране
        delta_screen = origin_screen_after - origin_screen_before
        self.translation += delta_screen

        self.view_changed.emit()
        self.update()

    def rotate_left(self, angle=15):
        # поворот налево на указанный угол
        self.rotate(angle)

    def rotate_right(self, angle=15):
        # поворот направо на указанный угол
        self.rotate(-angle)

    def get_cursor_world_coords(self):
        return self.cursor_world_coords

    def get_scale(self):
        return self.scale_factor

    def get_rotation(self):
        return self.rotation_angle

    def start_new_line(self):
        if self.is_drawing and self.current_line and self.current_point:
            self.current_line.end_point = self.current_point
            self.lines.append(self.current_line)
        self.is_drawing = True
        self.current_point = None
        self.current_line = None
        self.update()

    def delete_last_line(self):
        if self.lines:
            self.lines.pop()
            self.update()

    def delete_all_lines(self):
        self.lines.clear()
        self.current_line = None
        self.is_drawing = False
        self.current_point = None
        self.update()

    def set_grid_step(self, step_mm):
        """Устанавливает шаг сетки в миллиметрах"""
        self.grid_step_mm = step_mm
        # Шаг сетки в мировых координатах (в миллиметрах)
        self.grid_step = self.grid_step_mm
        self.update()

    def set_line_color(self, color):
        self.line_color = color
        # Применяем цвет к текущей линии, если она есть
        # Сохраняем цвет в legacy_color, чтобы не менять стиль
        if self.current_line:
            self.current_line._legacy_color = color
            # Если у линии есть стиль, временно меняем цвет стиля только для этой линии
            # Но лучше сохранить в legacy_color и использовать его при отрисовке
        # Цвет будет использоваться для новых линий (через self.line_color)
        self.update()

    def set_background_color(self, color):
        self.background_color = color
        self.update()

    def set_grid_color(self, color):
        self.grid_color = color
        self.update()

    def set_line_width(self, width):
        # Устаревший метод - толщина теперь управляется через стили
        # Оставляем для обратной совместимости, но не используем
        self.line_width = width
        if self.current_line:
            self.current_line.width = width
        self.update()

    def get_current_points(self):
        if self.current_line:
            return self.current_line.start_point, self.current_line.end_point
        elif self.lines:
            last_line = self.lines[-1]
            return last_line.start_point, last_line.end_point
        else:
            return QPointF(0, 0), QPointF(0, 0)

    def set_points_from_input(self, start_point, end_point, apply=False):
        # Получаем текущий стиль из менеджера
        style = None
        if self.style_manager:
            style = self.style_manager.get_current_style()
            # Если есть стиль, применяем к нему текущий цвет (для этой линии)
            if style:
                # Создаем копию стиля или обновляем цвет для этой линии
                # Но не меняем оригинальный стиль в менеджере
                pass
        
        if apply:
            new_line = LineSegment(start_point, end_point, style=style, 
                                  color=self.line_color, width=self.line_width)
            # Сохраняем цвет в legacy_color для использования при отрисовке
            new_line._legacy_color = self.line_color
            self.lines.append(new_line)
            self.update()
        else:
            if not self.current_line:
                self.current_line = LineSegment(start_point, end_point, style=style,
                                               color=self.line_color, width=self.line_width)
                # Сохраняем цвет в legacy_color для использования при отрисовке
                self.current_line._legacy_color = self.line_color
            else:
                self.current_line.start_point = start_point
                self.current_line.end_point = end_point
                if style and not self.current_line.style:
                    self.current_line.style = style
                # Обновляем цвет
                self.current_line._legacy_color = self.line_color
            self.update()
    
    def set_style_manager(self, style_manager):
        """Устанавливает менеджер стилей"""
        self.style_manager = style_manager
    
    def _find_line_at_point(self, point, tolerance=5.0):
        """Находит линию, ближайшую к указанной точке"""
        # Конвертируем tolerance из пикселей в мировые координаты
        world_tolerance = tolerance / self.scale_factor
        
        closest_line = None
        min_distance = float('inf')
        
        for line in self.lines:
            # Вычисляем расстояние от точки до линии
            distance = self._point_to_line_distance(point, line.start_point, line.end_point)
            if distance < world_tolerance and distance < min_distance:
                min_distance = distance
                closest_line = line
        
        return closest_line
    
    def _point_to_line_distance(self, point, line_start, line_end):
        """Вычисляет расстояние от точки до отрезка"""
        # Вектор линии
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()
        
        # Если линия - точка
        if dx == 0 and dy == 0:
            return math.sqrt((point.x() - line_start.x())**2 + (point.y() - line_start.y())**2)
        
        # Параметр t для проекции точки на линию
        t = ((point.x() - line_start.x()) * dx + (point.y() - line_start.y()) * dy) / (dx*dx + dy*dy)
        
        # Ограничиваем t отрезком [0, 1]
        t = max(0, min(1, t))
        
        # Ближайшая точка на отрезке
        closest_x = line_start.x() + t * dx
        closest_y = line_start.y() + t * dy
        
        # Расстояние от точки до ближайшей точки на отрезке
        return math.sqrt((point.x() - closest_x)**2 + (point.y() - closest_y)**2)
    
    def _draw_selection_highlight(self, painter, line):
        """Рисует подсветку выделенной линии"""
        # Рисуем пунктирную рамку вокруг выделенной линии
        highlight_pen = QPen(QColor(0, 100, 255), 1, Qt.DashLine)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.NoBrush)
        
        # Вычисляем границы линии с отступом
        margin = 3.0 / self.scale_factor
        min_x = min(line.start_point.x(), line.end_point.x()) - margin
        max_x = max(line.start_point.x(), line.end_point.x()) + margin
        min_y = min(line.start_point.y(), line.end_point.y()) - margin
        max_y = max(line.start_point.y(), line.end_point.y()) + margin
        
        # Рисуем прямоугольник вокруг линии
        painter.drawRect(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def get_selected_lines(self):
        """Возвращает список выделенных линий"""
        return list(self.selected_lines)
    
    def clear_selection(self):
        """Очищает выделение"""
        if self.selected_lines:
            self.selected_lines.clear()
            self.selection_changed.emit([])
            self.update()
    
    def _line_intersects_rect(self, line, rect):
        """Проверяет, пересекается ли линия с прямоугольником"""
        # Получаем координаты линии
        x1, y1 = line.start_point.x(), line.start_point.y()
        x2, y2 = line.end_point.x(), line.end_point.y()
        
        # Границы прямоугольника
        rect_left = rect.left()
        rect_right = rect.right()
        rect_top = rect.top()
        rect_bottom = rect.bottom()
        
        # Проверяем, находятся ли обе точки внутри прямоугольника
        if (rect_left <= x1 <= rect_right and rect_top <= y1 <= rect_bottom and
            rect_left <= x2 <= rect_right and rect_top <= y2 <= rect_bottom):
            return True
        
        # Проверяем пересечение с каждой стороной прямоугольника
        if self._line_segment_intersection(x1, y1, x2, y2, rect_left, rect_top, rect_left, rect_bottom):
            return True
        if self._line_segment_intersection(x1, y1, x2, y2, rect_right, rect_top, rect_right, rect_bottom):
            return True
        if self._line_segment_intersection(x1, y1, x2, y2, rect_left, rect_top, rect_right, rect_top):
            return True
        if self._line_segment_intersection(x1, y1, x2, y2, rect_left, rect_bottom, rect_right, rect_bottom):
            return True
        
        return False
    
    def _line_segment_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        """Проверяет пересечение двух отрезков"""
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return False  # Параллельные линии
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        return 0 <= t <= 1 and 0 <= u <= 1
    
    def _draw_selection_rect(self, painter):
        """Рисует рамку выделения"""
        if not self.selection_start or not self.selection_end:
            return
        
        # Преобразуем экранные координаты в мировые
        start_world = self.screen_to_world(self.selection_start)
        end_world = self.screen_to_world(self.selection_end)
        
        # Создаем прямоугольник
        rect = QRectF(
            min(start_world.x(), end_world.x()),
            min(start_world.y(), end_world.y()),
            abs(end_world.x() - start_world.x()),
            abs(end_world.y() - start_world.y())
        )
        
        # Рисуем рамку
        selection_pen = QPen(QColor(0, 100, 255), 1, Qt.DashLine)
        painter.setPen(selection_pen)
        painter.setBrush(QColor(0, 100, 255, 30))  # Полупрозрачная заливка
        painter.drawRect(rect)