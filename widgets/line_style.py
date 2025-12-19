"""
Модуль для управления стилями линий согласно ГОСТ 2.303-68
"""
from enum import Enum
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QPen, QColor


class LineType(Enum):
    """Типы линий согласно ГОСТ 2.303-68"""
    SOLID_MAIN = "solid_main"  # Сплошная основная
    SOLID_THIN = "solid_thin"  # Сплошная тонкая
    SOLID_WAVY = "solid_wavy"  # Сплошная волнистая
    DASHED = "dashed"  # Штриховая
    DASH_DOT_THICK = "dash_dot_thick"  # Штрихпунктирная утолщенная
    DASH_DOT_THIN = "dash_dot_thin"  # Штрихпунктирная тонкая
    DASH_DOT_TWO_DOTS = "dash_dot_two_dots"  # Штрихпунктирная с двумя точками
    SOLID_THIN_BROKEN = "solid_thin_broken"  # Сплошная тонкая с изломами


class LineStyle(QObject):
    """Класс для представления стиля линии"""
    style_changed = Signal()  # Сигнал при изменении стиля
    
    def __init__(self, name, line_type, thickness_mm=0.8, dash_length=5.0, dash_gap=2.5, 
                 is_gost_base=False, zigzag_count=1, zigzag_step_mm=4.0, wavy_amplitude_mm=None, parent=None):
        super().__init__(parent)
        self._name = name
        self._line_type = line_type
        self._thickness_mm = thickness_mm  # Толщина в миллиметрах
        self._dash_length = dash_length  # Длина штриха
        self._dash_gap = dash_gap  # Расстояние между штрихами
        self._is_gost_base = is_gost_base  # Базовый стиль ГОСТ (нельзя удалять/переименовывать)
        self._color = QColor(0, 0, 0)  # Цвет линии
        self._zigzag_count = zigzag_count  # Количество зигзагов для ломаной линии
        self._zigzag_step_mm = zigzag_step_mm  # Шаг между зигзагами в миллиметрах
        # Амплитуда волнистой линии в миллиметрах (None означает автоматический расчет)
        if wavy_amplitude_mm is None:
            # Автоматический расчет на основе толщины линии
            main_thickness_mm = 0.8
            self._wavy_amplitude_mm = (main_thickness_mm / 2.5) * (thickness_mm / 0.4)
        else:
            self._wavy_amplitude_mm = wavy_amplitude_mm
        
        # Объекты, использующие этот стиль
        self._objects = set()
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        if self._is_gost_base:
            raise ValueError("Нельзя переименовывать базовые стили ГОСТ")
        if value != self._name:
            self._name = value
            self.style_changed.emit()
    
    @property
    def line_type(self):
        return self._line_type
    
    @line_type.setter
    def line_type(self, value):
        if value != self._line_type:
            self._line_type = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def thickness_mm(self):
        return self._thickness_mm
    
    @thickness_mm.setter
    def thickness_mm(self, value):
        if 0.25 <= value <= 1.4:
            if value != self._thickness_mm:
                self._thickness_mm = value
                self.style_changed.emit()
                self._notify_objects()
        else:
            raise ValueError("Толщина должна быть от 0.25 до 1.4 мм")
    
    @property
    def dash_length(self):
        return self._dash_length
    
    @dash_length.setter
    def dash_length(self, value):
        if value > 0 and value != self._dash_length:
            self._dash_length = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def dash_gap(self):
        return self._dash_gap
    
    @dash_gap.setter
    def dash_gap(self, value):
        if value > 0 and value != self._dash_gap:
            self._dash_gap = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def is_gost_base(self):
        return self._is_gost_base
    
    @property
    def color(self):
        return self._color
    
    @color.setter
    def color(self, value):
        if value != self._color:
            self._color = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def zigzag_count(self):
        return self._zigzag_count
    
    @zigzag_count.setter
    def zigzag_count(self, value):
        if value < 1:
            raise ValueError("Количество зигзагов должно быть не менее 1")
        if value != self._zigzag_count:
            self._zigzag_count = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def zigzag_step_mm(self):
        return self._zigzag_step_mm
    
    @zigzag_step_mm.setter
    def zigzag_step_mm(self, value):
        if value <= 0:
            raise ValueError("Шаг между зигзагами должен быть больше 0")
        if value != self._zigzag_step_mm:
            self._zigzag_step_mm = value
            self.style_changed.emit()
            self._notify_objects()
    
    @property
    def wavy_amplitude_mm(self):
        return self._wavy_amplitude_mm
    
    @wavy_amplitude_mm.setter
    def wavy_amplitude_mm(self, value):
        if value <= 0:
            raise ValueError("Амплитуда должна быть больше 0")
        if value != self._wavy_amplitude_mm:
            self._wavy_amplitude_mm = value
            self.style_changed.emit()
            self._notify_objects()
    
    def register_object(self, obj):
        """Регистрирует объект, использующий этот стиль"""
        self._objects.add(obj)
    
    def unregister_object(self, obj):
        """Удаляет объект из списка использующих стиль"""
        self._objects.discard(obj)
    
    def _notify_objects(self):
        """Уведомляет все объекты об изменении стиля"""
        for obj in self._objects:
            if hasattr(obj, 'on_style_changed'):
                obj.on_style_changed()
    
    def get_pen(self, scale_factor=1.0, dpi=96):
        """
        Создает QPen для отрисовки линии
        Толщина линии не зависит от масштаба (в пикселях экрана)
        Длина штрихов задается в миллиметрах (мировых координатах) и масштабируется вместе с сеткой
        Это обеспечивает соответствие между размером штрихов и шагом сетки
        """
        # Конвертируем миллиметры в пиксели для толщины (независимо от масштаба)
        thickness_px = (self._thickness_mm * dpi) / 25.4
        
        pen = QPen(self._color, thickness_px)
        
        # Настраиваем тип линии
        if self._line_type == LineType.SOLID_MAIN or self._line_type == LineType.SOLID_THIN:
            pen.setStyle(Qt.SolidLine)
        elif self._line_type == LineType.SOLID_WAVY:
            # Волнистая линия - используем кастомный паттерн
            pen.setStyle(Qt.SolidLine)  # Будет обработано отдельно
        elif self._line_type == LineType.DASHED:
            # Штриховая: штрих-пробел
            # Теперь рисуется вручную в _draw_dashed_line, поэтому просто сплошная линия
            pen.setStyle(Qt.SolidLine)
        elif self._line_type == LineType.DASH_DOT_THICK or self._line_type == LineType.DASH_DOT_THIN:
            # Штрихпунктирная: штрих-пробел-точка-пробел
            # Теперь рисуется вручную в _draw_dash_dot_line, поэтому просто сплошная линия
            pen.setStyle(Qt.SolidLine)
        elif self._line_type == LineType.DASH_DOT_TWO_DOTS:
            # Штрихпунктирная с двумя точками: штрих-пробел-точка-пробел-точка-пробел
            # Теперь рисуется вручную в _draw_dash_dot_line, поэтому просто сплошная линия
            pen.setStyle(Qt.SolidLine)
        elif self._line_type == LineType.SOLID_THIN_BROKEN:
            # Сплошная тонкая с изломами - сплошная линия с острыми углами
            # Будет обработано отдельно в методе отрисовки
            pen.setStyle(Qt.SolidLine)
        else:
            pen.setStyle(Qt.SolidLine)
        
        return pen
    
    def clone(self, new_name=None):
        """Создает копию стиля (для пользовательских стилей)"""
        name = new_name if new_name else f"{self._name} (копия)"
        return LineStyle(
            name=name,
            line_type=self._line_type,
            thickness_mm=self._thickness_mm,
            dash_length=self._dash_length,
            dash_gap=self._dash_gap,
            is_gost_base=False,
            zigzag_count=self._zigzag_count,
            zigzag_step_mm=self._zigzag_step_mm,
            wavy_amplitude_mm=self._wavy_amplitude_mm
        )


class LineStyleManager(QObject):
    """Централизованный менеджер стилей линий"""
    style_added = Signal(object)  # Сигнал при добавлении стиля
    style_removed = Signal(str)  # Сигнал при удалении стиля
    style_changed = Signal(object)  # Сигнал при изменении стиля
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._styles = {}
        self._current_style_id = None
        self._initialize_gost_styles()
    
    def _initialize_gost_styles(self):
        """Инициализирует базовые стили ГОСТ 2.303-68"""
        gost_styles = [
            ("Сплошная основная", LineType.SOLID_MAIN, 0.8),
            ("Сплошная тонкая", LineType.SOLID_THIN, 0.4),
            ("Сплошная волнистая", LineType.SOLID_WAVY, 0.4),
            ("Штриховая", LineType.DASHED, 0.4, 5.0, 2.5),
            ("Штрихпунктирная утолщенная", LineType.DASH_DOT_THICK, 0.8, 10.0, 5.0),
            ("Штрихпунктирная тонкая", LineType.DASH_DOT_THIN, 0.4, 5.0, 2.5),
            ("Штрихпунктирная с двумя точками", LineType.DASH_DOT_TWO_DOTS, 0.4, 5.0, 2.5),
            ("Сплошная тонкая с изломами", LineType.SOLID_THIN_BROKEN, 0.4, 3.0, 1.5),
        ]
        
        for style_data in gost_styles:
            name = style_data[0]
            line_type = style_data[1]
            thickness = style_data[2]
            dash_length = style_data[3] if len(style_data) > 3 else 5.0
            dash_gap = style_data[4] if len(style_data) > 4 else 2.5
            
            style = LineStyle(
                name=name,
                line_type=line_type,
                thickness_mm=thickness,
                dash_length=dash_length,
                dash_gap=dash_gap,
                is_gost_base=True
            )
            style.style_changed.connect(lambda s=style: self.style_changed.emit(s))
            self._styles[name] = style
        
        # Устанавливаем первый стиль как текущий
        if self._styles:
            self._current_style_id = list(self._styles.keys())[0]
    
    def get_style(self, name):
        """Получает стиль по имени"""
        return self._styles.get(name)
    
    def get_all_styles(self):
        """Возвращает все стили"""
        return list(self._styles.values())
    
    def get_style_names(self):
        """Возвращает имена всех стилей"""
        return list(self._styles.keys())
    
    def get_current_style(self):
        """Возвращает текущий стиль"""
        if self._current_style_id:
            return self._styles.get(self._current_style_id)
        return None
    
    def set_current_style(self, style_name):
        """Устанавливает текущий стиль"""
        if style_name in self._styles:
            self._current_style_id = style_name
    
    def add_style(self, style):
        """Добавляет новый стиль"""
        if style.name in self._styles:
            raise ValueError(f"Стиль с именем '{style.name}' уже существует")
        style.style_changed.connect(lambda: self.style_changed.emit(style))
        self._styles[style.name] = style
        self.style_added.emit(style)
    
    def remove_style(self, name):
        """Удаляет стиль (только пользовательские)"""
        if name not in self._styles:
            return False
        
        style = self._styles[name]
        if style.is_gost_base:
            raise ValueError("Нельзя удалять базовые стили ГОСТ")
        
        del self._styles[name]
        if self._current_style_id == name:
            # Переключаемся на первый доступный стиль
            if self._styles:
                self._current_style_id = list(self._styles.keys())[0]
            else:
                self._current_style_id = None
        self.style_removed.emit(name)
        return True
    
    def rename_style(self, old_name, new_name):
        """Переименовывает стиль (только пользовательские)"""
        if old_name not in self._styles:
            raise ValueError(f"Стиль '{old_name}' не найден")
        
        style = self._styles[old_name]
        if style.is_gost_base:
            raise ValueError("Нельзя переименовывать базовые стили ГОСТ")
        
        if new_name in self._styles:
            raise ValueError(f"Стиль с именем '{new_name}' уже существует")
        
        style.name = new_name
        self._styles[new_name] = self._styles.pop(old_name)
        
        if self._current_style_id == old_name:
            self._current_style_id = new_name

