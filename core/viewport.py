"""
Класс для управления видом (масштаб, поворот, панорамирование)
"""
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform


class Viewport:
    """Управляет преобразованиями координат и видом"""
    
    def __init__(self, width: int = 600, height: int = 400):
        self.width = width
        self.height = height
        
        # Параметры трансформации
        self.scale_factor = 1.0
        self.min_scale = 0.01
        self.max_scale = 100.0
        self.rotation_angle = 0.0  # в градусах
        self.translation = QPointF(0, 0)
    
    def set_size(self, width: int, height: int):
        """Устанавливает размеры viewport"""
        self.width = width
        self.height = height
    
    def get_total_transform(self) -> QTransform:
        """Возвращает полную матрицу преобразования"""
        transform = QTransform()
        
        # Центрирование (перевод в центр виджета)
        transform.translate(self.width / 2, self.height / 2)
        
        # Трансляция (панорамирование)
        transform.translate(self.translation.x(), self.translation.y())
        
        # Поворот вокруг центра
        transform.rotate(self.rotation_angle)
        
        # Масштабирование с инверсией Y (в Qt Y вниз, в математике Y вверх)
        transform.scale(self.scale_factor, -self.scale_factor)
        
        return transform
    
    def screen_to_world(self, screen_point: QPointF) -> QPointF:
        """Преобразует экранные координаты в мировые"""
        transform, success = self.get_total_transform().inverted()
        if success:
            return transform.map(screen_point)
        return screen_point
    
    def world_to_screen(self, world_point: QPointF) -> QPointF:
        """Преобразует мировые координаты в экранные"""
        transform = self.get_total_transform()
        return transform.map(world_point)
    
    def zoom_at_point(self, screen_point: QPointF, factor: float):
        """Масштабирование относительно точки с сохранением положения этой точки"""
        world_point_before = self.screen_to_world(screen_point)
        
        # Применяем масштаб
        self.scale_factor *= factor
        self.scale_factor = max(self.min_scale, min(self.max_scale, self.scale_factor))
        
        world_point_after = self.screen_to_world(screen_point)
        
        # Корректируем трансляцию для сохранения положения точки
        delta = world_point_after - world_point_before
        self.translation += QPointF(delta.x() * self.scale_factor, delta.y() * self.scale_factor)
    
    def zoom_in(self, factor: float = 1.2):
        """Увеличивает масштаб"""
        center = QPointF(self.width / 2, self.height / 2)
        self.zoom_at_point(center, factor)
    
    def zoom_out(self, factor: float = 1.2):
        """Уменьшает масштаб"""
        center = QPointF(self.width / 2, self.height / 2)
        self.zoom_at_point(center, 1.0 / factor)
    
    def pan(self, delta: QPointF):
        """Панорамирование"""
        self.translation += delta
    
    def rotate(self, angle: float):
        """Вращает вид вокруг центра координат (0, 0)"""
        # Сохраняем текущее положение точки (0, 0) на экране
        origin_world = QPointF(0, 0)
        origin_screen_before = self.world_to_screen(origin_world)
        
        # Применяем поворот
        self.rotation_angle += angle
        # Нормализуем угол
        self.rotation_angle %= 360
        
        # Вычисляем новое положение точки (0, 0) на экране после поворота
        origin_screen_after = self.world_to_screen(origin_world)
        
        # Корректируем трансляцию, чтобы точка (0, 0) оставалась в том же месте на экране
        delta_screen = origin_screen_after - origin_screen_before
        self.translation += delta_screen
    
    def reset(self):
        """Полностью сбрасывает вид к начальному состоянию"""
        self.scale_factor = 1.0
        self.rotation_angle = 0
        self.translation = QPointF(0, 0)
    
    def get_scale(self) -> float:
        """Возвращает текущий масштаб"""
        return self.scale_factor
    
    def get_rotation(self) -> float:
        """Возвращает текущий угол поворота"""
        return self.rotation_angle
    
    def get_visible_rect(self) -> QRectF:
        """Возвращает видимую область в мировых координатах"""
        transform, success = self.get_total_transform().inverted()
        if not success:
            return QRectF()
        
        widget_rect = QRectF(0, 0, self.width, self.height)
        return transform.mapRect(widget_rect)

