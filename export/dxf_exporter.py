"""
DXF Export Module — ЛР №5.

Экспортирует сцену в формат DXF R2010 (ezdxf).
Координатная система: Qt использует Y-down, DXF — Y-up. При экспорте Y инвертируется.
"""
from __future__ import annotations

import math
from typing import List, Optional, TYPE_CHECKING

import ezdxf
from ezdxf.document import Drawing

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from core.geometry import GeometricObject
from widgets.line_style import LineType

if TYPE_CHECKING:
    from core.layer import LayerManager


# -----------------------------------------------------------------------
# Таблица соответствия типов линий ГОСТ → DXF
# -----------------------------------------------------------------------
_LINETYPE_MAP: dict[LineType, str] = {
    LineType.BY_LAYER:           "ByLayer",
    LineType.SOLID_MAIN:         "Continuous",
    LineType.SOLID_THIN:         "Continuous",
    LineType.SOLID_WAVY:         "Continuous",
    LineType.DASHED:             "CAD_DASHED",
    LineType.DASH_DOT_THICK:     "CAD_CENTER",
    LineType.DASH_DOT_THIN:      "CAD_DASHDOT",
    LineType.DASH_DOT_TWO_DOTS:  "CAD_PHANTOM",
    LineType.SOLID_THIN_BROKEN:  "Continuous",
}

# Определения пользовательских типов линий (паттерны в единицах чертежа)
_CUSTOM_LINETYPES: list[dict] = [
    {
        "name": "CAD_DASHED",
        "description": "Штриховая ____ ____ ____",
        "pattern": [5.0, 3.0, -3.0],
    },
    {
        "name": "CAD_CENTER",
        "description": "Штрих-пунктирная утолщённая ____ _ ____",
        "pattern": [10.0, 7.0, -2.0, 0.5, -2.0],
    },
    {
        "name": "CAD_DASHDOT",
        "description": "Штрих-пунктирная тонкая ___ . ___",
        "pattern": [7.0, 5.0, -1.5, 0.0, -1.5],
    },
    {
        "name": "CAD_PHANTOM",
        "description": "Штрих-пунктирная с двумя точками ___ . . ___",
        "pattern": [9.0, 6.0, -1.5, 0.0, -1.5, 0.0, -1.5],
    },
]


# -----------------------------------------------------------------------
# Преобразования координат
#
# Viewport применяет scale(s, -s), значит сцена уже хранит координаты
# в стандартной математической системе Y-up (как в DXF).
# Никакого переворота Y не требуется — координаты передаются как есть.
# -----------------------------------------------------------------------

def _p2(p: QPointF) -> tuple[float, float]:
    return (p.x(), p.y())


def _p3(p: QPointF, z: float = 0.0) -> tuple[float, float, float]:
    return (p.x(), p.y(), z)


def _xy3(x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
    return (x, y, z)


# -----------------------------------------------------------------------
# Цвет
# -----------------------------------------------------------------------

def _true_color(c: QColor) -> int:
    """QColor → 24-bit RGB integer для DXF true_color."""
    return (c.red() << 16) | (c.green() << 8) | c.blue()


def _aci(c: QColor) -> int:
    """Приближённое преобразование QColor в ACI (AutoCAD Color Index)."""
    r, g, b = c.red(), c.green(), c.blue()
    if r < 32 and g < 32 and b < 32:
        return 7   # чёрный/белый
    if r >= 192 and g < 64 and b < 64:
        return 1   # красный
    if r < 64 and g >= 128 and b < 64:
        return 3   # зелёный
    if r < 64 and g < 64 and b >= 192:
        return 5   # синий
    if r >= 192 and g >= 192 and b < 64:
        return 2   # жёлтый
    if r < 64 and g >= 192 and b >= 192:
        return 4   # голубой
    if r >= 192 and g < 64 and b >= 192:
        return 6   # пурпурный
    return 7


# -----------------------------------------------------------------------
# Толщина линии (mm → ближайший стандарт DXF в 1/100 mm)
# -----------------------------------------------------------------------
_VALID_LW = (
    0, 5, 9, 13, 15, 18, 20, 25, 30, 35,
    40, 50, 53, 60, 70, 80, 90, 100, 106,
    120, 140, 158, 200, 211,
)


def _lineweight(mm: float) -> int:
    hundredths = round(mm * 100)
    return min(_VALID_LW, key=lambda x: abs(x - hundredths))


# -----------------------------------------------------------------------
# Основной класс экспортёра
# -----------------------------------------------------------------------

class DXFExporter:
    """
    Экспортирует список GeometricObject в файл DXF формата R2010.

    Поддерживаемые примитивы:
        LineSegment, Circle, Arc, Rectangle, Ellipse, Polygon, Spline, Point,
        LinearDimension, RadialDimension, AngularDimension.
    """

    def __init__(self, layer_manager: Optional[LayerManager] = None) -> None:
        self._lm = layer_manager

    # ------------------------------------------------------------------
    # Публичный метод
    # ------------------------------------------------------------------

    def export(self, objects: List[GeometricObject], filepath: str) -> None:
        """Экспортирует объекты в файл DXF."""
        doc: Drawing = ezdxf.new(dxfversion="R2010")
        msp = doc.modelspace()

        self._setup_linetypes(doc)
        self._setup_layers(doc)

        for obj in objects:
            self._export_object(doc, msp, obj)

        doc.saveas(filepath)

    # ------------------------------------------------------------------
    # Настройка документа
    # ------------------------------------------------------------------

    def _setup_linetypes(self, doc: Drawing) -> None:
        lttable = doc.linetypes
        for lt in _CUSTOM_LINETYPES:
            if lt["name"] not in lttable:
                try:
                    lttable.new(
                        lt["name"],
                        dxfattribs={
                            "description": lt["description"],
                            "pattern": lt["pattern"],
                        },
                    )
                except Exception:
                    pass

    def _setup_layers(self, doc: Drawing) -> None:
        if self._lm is None:
            return
        for layer in self._lm.get_all_layers():
            if layer.name == "0":
                # Настраиваем слой 0
                try:
                    l0 = doc.layers.get("0")
                    if l0:
                        l0.dxf.true_color = _true_color(layer.color)
                        l0.dxf.color = _aci(layer.color)
                        if layer.line_type and layer.line_type != "Continuous":
                            l0.dxf.linetype = layer.line_type
                except Exception:
                    pass
                continue
            if layer.name in doc.layers:
                continue
            try:
                dl = doc.layers.new(layer.name)
                dl.dxf.true_color = _true_color(layer.color)
                dl.dxf.color = _aci(layer.color)
                if layer.line_type and layer.line_type != "Continuous":
                    dl.dxf.linetype = layer.line_type
                if not layer.visible:
                    dl.off()
                if layer.locked:
                    dl.lock()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Общие атрибуты объекта
    # ------------------------------------------------------------------

    def _effective_color(self, obj: GeometricObject) -> Optional[QColor]:
        layer_name = getattr(obj, "layer_name", "0")
        if self._lm is not None:
            layer = self._lm.get_layer(layer_name)
            layer_color = getattr(layer, "color", None) if layer is not None else None
            if isinstance(layer_color, QColor) and layer_color.isValid():
                return layer_color

        color: Optional[QColor] = getattr(obj, "color", None)
        if isinstance(color, QColor) and color.isValid():
            return color
        return None

    def _attribs(self, obj: GeometricObject) -> dict:
        a: dict = {"layer": getattr(obj, "layer_name", "0")}
        layer_name = getattr(obj, "layer_name", "0")
        layer_exists = self._lm is not None and self._lm.get_layer(layer_name) is not None
        color = self._effective_color(obj)
        if not layer_exists and isinstance(color, QColor) and color.isValid():
            a["true_color"] = _true_color(color)
            a["color"] = _aci(color)

        style = getattr(obj, "style", None)
        if style is not None:
            # Тип линии
            lt = getattr(style, "line_type", None)
            if lt is not None and lt != LineType.BY_LAYER:
                dxf_lt = _LINETYPE_MAP.get(lt, "Continuous")
                if dxf_lt != "Continuous":
                    a["linetype"] = dxf_lt
            # Толщина
            tmm = getattr(style, "thickness_mm", None)
            if tmm is not None:
                a["lineweight"] = _lineweight(tmm)

        return a

    # ------------------------------------------------------------------
    # Диспетчер
    # ------------------------------------------------------------------

    def _export_object(self, doc: Drawing, msp, obj: GeometricObject) -> None:
        from widgets.line_segment import LineSegment
        from widgets.primitives import Circle, Arc, Rectangle, Ellipse, Polygon, Spline
        from core.geometry import Point

        if isinstance(obj, LineSegment):
            self._line(msp, obj)
        elif isinstance(obj, Circle):
            self._circle(msp, obj)
        elif isinstance(obj, Arc):
            self._arc(msp, obj)
        elif isinstance(obj, Rectangle):
            self._rectangle(msp, obj)
        elif isinstance(obj, Ellipse):
            self._ellipse(msp, obj)
        elif isinstance(obj, Polygon):
            self._polygon(msp, obj)
        elif isinstance(obj, Spline):
            self._spline(msp, obj)
        elif isinstance(obj, Point):
            self._point(msp, obj)
        else:
            self._try_dimension(msp, obj)

    # ------------------------------------------------------------------
    # Примитивы
    # ------------------------------------------------------------------

    def _line(self, msp, obj) -> None:
        msp.add_line(
            start=_p3(obj.start_point),
            end=_p3(obj.end_point),
            dxfattribs=self._attribs(obj),
        )

    def _circle(self, msp, obj) -> None:
        msp.add_circle(
            center=_p3(obj.center),
            radius=obj.radius,
            dxfattribs=self._attribs(obj),
        )

    def _arc(self, msp, obj) -> None:
        attribs = self._attribs(obj)
        is_circular = (
            abs(obj.radius_x - obj.radius_y) < 1e-3
            and abs(obj.rotation_angle) < 1e-6
        )

        if is_circular:
            # Сцена хранит Y-up координаты — углы дуги уже в стандарте CCW DXF.
            # Передаём напрямую без трансформации.
            msp.add_arc(
                center=_p3(obj.center),
                radius=obj.radius_x,
                start_angle=obj.start_angle % 360,
                end_angle=obj.end_angle % 360,
                dxfattribs=attribs,
            )
        else:
            self._arc_as_polyline(msp, obj, attribs)

    def _arc_as_polyline(self, msp, obj, attribs: dict) -> None:
        start_a = obj.start_angle
        end_a = obj.end_angle
        if end_a < start_a:
            end_a += 360.0
        n = max(64, int(abs(end_a - start_a)))
        pts = []
        for i in range(n + 1):
            t = start_a + (end_a - start_a) * i / n
            p = obj.get_point_at_angle(t % 360 if t > 360 else t)
            pts.append(_p3(p))
        if len(pts) >= 2:
            msp.add_polyline3d(pts, dxfattribs=attribs)

    def _rectangle(self, msp, obj) -> None:
        attribs = self._attribs(obj)
        x1, y1 = obj.top_left.x(), obj.top_left.y()
        x2, y2 = obj.bottom_right.x(), obj.bottom_right.y()
        r = obj.fillet_radius

        if r <= 0:
            pts = [
                (x1, y1),
                (x2, y1),
                (x2, y2),
                (x1, y2),
            ]
            msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
        else:
            pts = self._rounded_rect_pts(x1, y1, x2, y2, r)
            msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)

    def _rounded_rect_pts(
        self, x1: float, y1: float, x2: float, y2: float, r: float,
        seg: int = 12
    ) -> list[tuple[float, float]]:
        """Генерирует точки скруглённого прямоугольника в Y-up мировых координатах.

        top_left = (x1, y1) — y1 БОЛЬШЕ (выше на экране в Y-up).
        bottom_right = (x2, y2) — y2 МЕНЬШЕ (ниже на экране в Y-up).
        """
        # Нормализуем: x1 < x2, y1 > y2 (y1 = верх в Y-up)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 < y2:
            y1, y2 = y2, y1
        r = min(r, (x2 - x1) / 2, abs(y1 - y2) / 2)

        # Углы в Y-up координатах (стандартная математика CCW):
        #   0°=право, 90°=вверх, 180°=лево, 270°=вниз
        # Обходим фигуру CCW: снизу-слева → снизу-справа → сверху-справа → сверху-слева
        corners = [
            (x1 + r, y2 + r, 180, 270),  # нижний-левый:  180→270
            (x2 - r, y2 + r, 270, 360),  # нижний-правый: 270→360
            (x2 - r, y1 - r,   0,  90),  # верхний-правый:  0→90
            (x1 + r, y1 - r,  90, 180),  # верхний-левый:  90→180
        ]
        pts: list[tuple[float, float]] = []
        for cx, cy, a0, a1 in corners:
            for i in range(seg + 1):
                a = math.radians(a0 + (a1 - a0) * i / seg)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def _ellipse(self, msp, obj) -> None:
        attribs = self._attribs(obj)
        rot = obj.rotation_angle
        rx, ry = obj.radius_x, obj.radius_y

        if rx >= ry:
            major = (rx * math.cos(rot), rx * math.sin(rot), 0.0)
            ratio = ry / rx if rx > 1e-9 else 1.0
        else:
            # Главная ось — Y-направление (поворот на 90°)
            major = (
                ry * math.cos(rot + math.pi / 2),
                ry * math.sin(rot + math.pi / 2),
                0.0,
            )
            ratio = rx / ry if ry > 1e-9 else 1.0

        ratio = max(1e-6, min(ratio, 1.0))

        msp.add_ellipse(
            center=_p3(obj.center),
            major_axis=major,
            ratio=ratio,
            start_param=0.0,
            end_param=math.pi * 2,
            dxfattribs=attribs,
        )

    def _polygon(self, msp, obj) -> None:
        attribs = self._attribs(obj)
        verts = obj.get_vertices()
        if len(verts) < 2:
            return
        pts = [(v.x(), v.y()) for v in verts]
        msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)

    def _spline(self, msp, obj) -> None:
        attribs = self._attribs(obj)
        cps = obj.control_points
        if len(cps) < 2:
            return
        pts3 = [_p3(p) for p in cps]
        try:
            msp.add_spline(
                fit_points=pts3,
                degree=min(3, len(pts3) - 1),
                dxfattribs=attribs,
            )
        except Exception:
            # Fallback: POLYLINE-аппроксимация
            msp.add_polyline3d(pts3, dxfattribs=attribs)

    def _point(self, msp, obj) -> None:
        msp.add_point(
            location=_p3(obj.point),
            dxfattribs=self._attribs(obj),
        )

    # ------------------------------------------------------------------
    # Размеры (Dimensions)
    # ------------------------------------------------------------------

    def _try_dimension(self, msp, obj) -> None:
        try:
            from widgets.dimensions import (
                LinearDimension, RadialDimension, AngularDimension,
            )
        except ImportError:
            return

        if isinstance(obj, LinearDimension):
            self._dim_linear(msp, obj)
        elif isinstance(obj, RadialDimension):
            self._dim_radial(msp, obj)
        elif isinstance(obj, AngularDimension):
            self._dim_angular(msp, obj)

    def _dim_layer_attribs(self, obj) -> dict:
        return {"layer": getattr(obj, "layer_name", "0")}

    def _dim_linear(self, msp, obj) -> None:
        attribs = self._dim_layer_attribs(obj)
        geom = obj._geometry()
        (
            ext1_s, ext1_e, ext2_s, ext2_e,
            line_s, line_e, arrow1, arrow2,
            text_pos, tangent, _
        ) = geom

        # Выносные линии
        msp.add_line(_p3(ext1_s), _p3(ext1_e), dxfattribs=attribs)
        msp.add_line(_p3(ext2_s), _p3(ext2_e), dxfattribs=attribs)
        # Линия размера
        msp.add_line(_p3(line_s), _p3(line_e), dxfattribs=attribs)
        # Стрелки (маленькие линии)
        self._draw_arrow_lines(msp, arrow1, arrow2, obj.style.arrows.size, attribs)
        # Текст
        self._add_text(msp, obj.display_text, text_pos,
                       obj.style.text.height, attribs, rotation=obj.get_text_angle())

    def _dim_radial(self, msp, obj) -> None:
        attribs = self._dim_layer_attribs(obj)
        ux, uy = obj._axis_direction()
        r = obj.radius
        tip = QPointF(obj.center.x() + ux * r, obj.center.y() + uy * r)
        end = obj._line_end(tip, ux, uy)

        msp.add_line(_p3(obj.center), _p3(end), dxfattribs=attribs)
        # Стрелка на кончике
        self._draw_single_arrow(msp, tip, (-ux, -uy),
                                obj.style.arrows.size, attribs)
        text_pos = obj.get_default_text_position()
        self._add_text(msp, obj.display_text, text_pos,
                       obj.style.text.height, attribs,
                       rotation=obj.get_text_angle())

    def _dim_angular(self, msp, obj) -> None:
        attribs = self._dim_layer_attribs(obj)
        a1, a2, span = obj._angles()

        # Дуга как полилиния
        n = max(32, int(math.degrees(span)))
        arc_pts = []
        for i in range(n + 1):
            angle = a1 + span * i / n
            p = QPointF(
                obj.vertex.x() + obj.radius * math.cos(angle),
                obj.vertex.y() + obj.radius * math.sin(angle),
            )
            arc_pts.append(_p3(p))
        if len(arc_pts) >= 2:
            msp.add_polyline3d(arc_pts, dxfattribs=attribs)

        # Выносные линии
        ext_len = obj.radius + obj.style.extension_lines.overshoot
        for angle in (a1, a2):
            end_pt = QPointF(
                obj.vertex.x() + ext_len * math.cos(angle),
                obj.vertex.y() + ext_len * math.sin(angle),
            )
            msp.add_line(_p3(obj.vertex), _p3(end_pt), dxfattribs=attribs)

        # Текст
        text_pos = obj.get_default_text_position()
        self._add_text(msp, obj.display_text, text_pos,
                       obj.style.text.height, attribs,
                       rotation=math.degrees(obj.get_text_angle()))

    # ------------------------------------------------------------------
    # Вспомогательные методы для размеров
    # ------------------------------------------------------------------

    def _draw_arrow_lines(
        self, msp, p1: QPointF, p2: QPointF, size: float, attribs: dict
    ) -> None:
        """Рисует стрелки как пары коротких линий (для DXF без заполненных треугольников)."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return
        ux, uy = dx / dist, dy / dist
        half = size * math.tan(math.radians(10.0)) * 1.45

        for tip, direction in [(p1, (ux, uy)), (p2, (-ux, -uy))]:
            base = QPointF(tip.x() + direction[0] * size, tip.y() + direction[1] * size)
            nx, ny = -direction[1], direction[0]
            left = QPointF(base.x() + nx * half, base.y() + ny * half)
            right = QPointF(base.x() - nx * half, base.y() - ny * half)
            msp.add_line(_p3(tip), _p3(left), dxfattribs=attribs)
            msp.add_line(_p3(tip), _p3(right), dxfattribs=attribs)

    def _draw_single_arrow(
        self, msp, tip: QPointF, direction: tuple[float, float],
        size: float, attribs: dict
    ) -> None:
        ux, uy = direction
        dist = math.hypot(ux, uy)
        if dist < 1e-9:
            return
        ux, uy = ux / dist, uy / dist
        half = size * math.tan(math.radians(10.0)) * 1.45
        base = QPointF(tip.x() + ux * size, tip.y() + uy * size)
        nx, ny = -uy, ux
        left = QPointF(base.x() + nx * half, base.y() + ny * half)
        right = QPointF(base.x() - nx * half, base.y() - ny * half)
        msp.add_line(_p3(tip), _p3(left), dxfattribs=attribs)
        msp.add_line(_p3(tip), _p3(right), dxfattribs=attribs)

    def _add_text(
        self, msp, text: str, pos: QPointF,
        height: float, attribs: dict, rotation: float = 0.0
    ) -> None:
        text_attribs = {
            **attribs,
            "height": max(height, 2.5),
            "rotation": rotation,
        }
        try:
            t = msp.add_text(text, dxfattribs=text_attribs)
            t.set_placement(_p2(pos), align=ezdxf.enums.TextEntityAlignment.CENTER)
        except Exception:
            try:
                t = msp.add_text(text, dxfattribs=text_attribs)
                t.dxf.insert = _p2(pos)
            except Exception:
                pass
