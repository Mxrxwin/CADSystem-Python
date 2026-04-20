# Инициализация пакета widgets
from .line_segment import LineSegment
from .coordinate_system import CoordinateSystemWidget
from .dimensions import LinearDimension, RadialDimension, AngularDimension, DimensionStyle

__all__ = [
    'LineSegment',
    'CoordinateSystemWidget',
    'LinearDimension',
    'RadialDimension',
    'AngularDimension',
    'DimensionStyle',
]