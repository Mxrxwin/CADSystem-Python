"""
Классы для работы с координатами и их преобразованиями
"""
import math
from enum import Enum
from PySide6.QtCore import QPointF


class CoordinateSystem(Enum):
    """Типы систем координат"""
    CARTESIAN = "cartesian"
    POLAR = "polar"


class AngleUnit(Enum):
    """Единицы измерения углов"""
    DEGREES = "degrees"
    RADIANS = "radians"


class CoordinateConverter:
    """Класс для преобразования координат между различными системами"""
    
    @staticmethod
    def polar_to_cartesian(radius: float, angle: float, angle_unit: AngleUnit = AngleUnit.DEGREES,
                          origin: QPointF = QPointF(0, 0)) -> QPointF:
        """Преобразует полярные координаты в декартовы относительно начала координат"""
        if angle_unit == AngleUnit.DEGREES:
            angle_rad = math.radians(angle)
        else:
            angle_rad = angle
        
        delta_x = radius * math.cos(angle_rad)
        delta_y = radius * math.sin(angle_rad)
        
        return QPointF(origin.x() + delta_x, origin.y() + delta_y)
    
    @staticmethod
    def cartesian_to_polar(point: QPointF, origin: QPointF = QPointF(0, 0),
                          angle_unit: AngleUnit = AngleUnit.DEGREES) -> tuple:
        """Преобразует декартовы координаты в полярные относительно начала координат"""
        delta_x = point.x() - origin.x()
        delta_y = point.y() - origin.y()
        
        radius = math.sqrt(delta_x**2 + delta_y**2)
        angle_rad = math.atan2(delta_y, delta_x)
        
        if angle_unit == AngleUnit.DEGREES:
            angle = math.degrees(angle_rad)
        else:
            angle = angle_rad
        
        return radius, angle
    
    @staticmethod
    def convert_angle(angle: float, from_unit: AngleUnit, to_unit: AngleUnit) -> float:
        """Преобразует угол из одной единицы измерения в другую"""
        if from_unit == to_unit:
            return angle
        
        if from_unit == AngleUnit.DEGREES and to_unit == AngleUnit.RADIANS:
            return math.radians(angle)
        else:
            return math.degrees(angle)


class CoordinateInputController:
    """Контроллер для управления вводом координат"""
    
    def __init__(self, coordinate_system: CoordinateSystem = CoordinateSystem.CARTESIAN,
                 angle_unit: AngleUnit = AngleUnit.DEGREES):
        self.coordinate_system = coordinate_system
        self.angle_unit = angle_unit
        self.converter = CoordinateConverter()
    
    def set_coordinate_system(self, system: CoordinateSystem):
        """Устанавливает систему координат"""
        self.coordinate_system = system
    
    def set_angle_unit(self, unit: AngleUnit):
        """Устанавливает единицы измерения углов"""
        self.angle_unit = unit
    
    def get_end_point(self, start_point: QPointF, 
                     cartesian_end: QPointF = None,
                     polar_radius: float = None, polar_angle: float = None) -> QPointF:
        """Возвращает конечную точку в зависимости от системы координат"""
        if self.coordinate_system == CoordinateSystem.CARTESIAN:
            if cartesian_end is None:
                raise ValueError("Для декартовой системы нужны координаты cartesian_end")
            return QPointF(cartesian_end)
        else:  # POLAR
            if polar_radius is None or polar_angle is None:
                raise ValueError("Для полярной системы нужны radius и angle")
            return self.converter.polar_to_cartesian(
                polar_radius, polar_angle, self.angle_unit, start_point
            )
    
    def convert_to_display(self, start_point: QPointF, end_point: QPointF) -> dict:
        """Преобразует координаты для отображения в зависимости от системы координат"""
        if self.coordinate_system == CoordinateSystem.CARTESIAN:
            return {
                'start': (start_point.x(), start_point.y()),
                'end': (end_point.x(), end_point.y())
            }
        else:  # POLAR
            radius, angle = self.converter.cartesian_to_polar(end_point, start_point, self.angle_unit)
            return {
                'start': (start_point.x(), start_point.y()),
                'end': (radius, angle)
            }

