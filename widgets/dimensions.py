import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QBrush, QPolygonF

from core.geometry import Drawable, GeometricObject


def _point_distance(a: QPointF, b: QPointF) -> float:
    return math.hypot(b.x() - a.x(), b.y() - a.y())


def _normalize(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return 0.0, 0.0
    return dx / length, dy / length


def _offset_point(point: QPointF, dx: float, dy: float) -> QPointF:
    return QPointF(point.x() + dx, point.y() + dy)


def _copy_point(point: QPointF) -> QPointF:
    return QPointF(point)


def _midpoint(a: QPointF, b: QPointF) -> QPointF:
    return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)


def _angle_degrees(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dy, dx)) if abs(dx) > 1e-9 or abs(dy) > 1e-9 else 0.0


def _scaled_width(width_px: float, scale_factor: float) -> float:
    return width_px / max(scale_factor, 1e-6)


def _bounding_rect(points: list[QPointF]) -> QRectF:
    min_x = min(p.x() for p in points)
    min_y = min(p.y() for p in points)
    max_x = max(p.x() for p in points)
    max_y = max(p.y() for p in points)
    return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)


def _line_pen(color: QColor, line_type: str, width_px: float = 1.0) -> QPen:
    style_map = {
        "solid": Qt.SolidLine,
        "dashed": Qt.DashLine,
        "dash_dot": Qt.DashDotLine,
        "dot": Qt.DotLine,
    }
    return QPen(color, width_px, style_map.get(line_type, Qt.SolidLine))


def _format_value(value: float, suffix: str = "") -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _resolve_dimension_font_family() -> str:
    candidates = (
        "Gost Type A",
        "GOST Type A",
        "GOST type A",
        "GOST Common",
        "ISOCPEUR",
    )
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return candidates[0]
        font_db = QFontDatabase()
        available = {family.lower(): family for family in font_db.families()}
        for candidate in candidates:
            match = available.get(candidate.lower())
            if match:
                return match
    except Exception:
        pass
    return candidates[0]


@dataclass
class ExtensionLineParams:
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    line_type: str = "solid"
    width_px: float = 1.0
    gap_from_object: float = 2.0
    overshoot: float = 2.5


@dataclass
class DimensionLineParams:
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    line_type: str = "solid"
    width_px: float = 1.0
    extension: float = 2.0


@dataclass
class ArrowParams:
    arrow_type: str = "closed_filled"
    size: float = 3.5
    filled: bool = True
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0))


@dataclass
class DimensionTextParams:
    font_family: str = field(default_factory=_resolve_dimension_font_family)
    height: float = 4.0
    color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    position: str = "above"
    gap: float = 4.5


@dataclass
class DimensionStyle:
    extension_lines: ExtensionLineParams = field(default_factory=ExtensionLineParams)
    dimension_line: DimensionLineParams = field(default_factory=DimensionLineParams)
    arrows: ArrowParams = field(default_factory=ArrowParams)
    text: DimensionTextParams = field(default_factory=DimensionTextParams)


class DimensionBase(GeometricObject, Drawable):
    def __init__(self, style: DimensionStyle | None = None):
        super().__init__()
        self.style = style or DimensionStyle()
        self.text_override: str | None = None
        self.text_position_override: QPointF | None = None

    def contains_point(self, point: QPointF, tolerance: float = 5.0) -> bool:
        bbox = self.get_bounding_box()
        expanded = QRectF(
            bbox.x() - tolerance,
            bbox.y() - tolerance,
            bbox.width() + tolerance * 2,
            bbox.height() + tolerance * 2,
        )
        return expanded.contains(point)

    def intersects_rect(self, rect: QRectF) -> bool:
        return rect.intersects(self.get_bounding_box())

    def _draw_arrow(self, painter: QPainter, tip: QPointF, direction: tuple[float, float]):
        ux, uy = _normalize(direction[0], direction[1])
        if abs(ux) < 1e-9 and abs(uy) < 1e-9:
            return
        size = self.style.arrows.size
        back = QPointF(tip.x() + ux * size, tip.y() + uy * size)
        perp_x, perp_y = -uy, ux
        half_width = size * math.tan(math.radians(10.0)) * 1.45
        left = QPointF(back.x() + perp_x * half_width, back.y() + perp_y * half_width)
        right = QPointF(back.x() - perp_x * half_width, back.y() - perp_y * half_width)

        painter.save()
        painter.setPen(QPen(self.style.arrows.color, 1.0))
        if self.style.arrows.arrow_type == "open":
            painter.drawLine(tip, left)
            painter.drawLine(tip, right)
        else:
            polygon = QPolygonF([tip, left, right])
            painter.setBrush(QBrush(self.style.arrows.color if self.style.arrows.filled else Qt.NoBrush))
            painter.drawPolygon(polygon)
        painter.restore()

    def _text_screen_metrics(self, painter: QPainter, text: str, scale_factor: float = 1.0):
        font = QFont(self.style.text.font_family)
        font.setPixelSize(int(round(max(18.0, self.style.text.height * max(scale_factor, 1.0) * 4.4))))
        font.setWeight(QFont.Light)
        font.setStyleStrategy(QFont.PreferOutline)
        metrics = QFontMetricsF(font)
        rect = metrics.boundingRect(text)
        return font, rect

    def _text_screen_gap(self, scale_factor: float = 1.0) -> float:
        return max(8.0, self.style.text.gap * max(scale_factor, 1.0) * 1.15)

    def _draw_text(
        self,
        painter: QPainter,
        position_world: QPointF,
        text: str,
        scale_factor: float = 1.0,
        angle_degrees: float = 0.0,
    ):
        screen_pos = painter.transform().map(position_world)
        angle_rad = math.radians(angle_degrees)
        ref_world = QPointF(position_world.x() + math.cos(angle_rad), position_world.y() + math.sin(angle_rad))
        ref_screen = painter.transform().map(ref_world)
        screen_angle = math.degrees(math.atan2(ref_screen.y() - screen_pos.y(), ref_screen.x() - screen_pos.x()))
        painter.save()
        painter.resetTransform()
        font, rect = self._text_screen_metrics(painter, text, scale_factor)
        painter.setFont(font)
        painter.setPen(QPen(self.style.text.color))
        normalized_angle = ((screen_angle + 180.0) % 360.0) - 180.0
        if normalized_angle > 90.0:
            normalized_angle -= 180.0
        elif normalized_angle < -90.0:
            normalized_angle += 180.0
        painter.translate(screen_pos)
        painter.rotate(normalized_angle)
        gap_px = self._text_screen_gap(scale_factor)
        if self.style.text.position == "above":
            painter.translate(0.0, -(rect.height() / 2.0 + gap_px))
            draw_rect = QRectF(-rect.width() / 2, -rect.height() / 2, rect.width(), rect.height())
        else:
            draw_rect = QRectF(-rect.width() / 2, -rect.height() / 2, rect.width(), rect.height())
        painter.drawText(draw_rect, Qt.AlignCenter, text)
        painter.restore()

    def _default_text(self) -> str:
        return ""

    def _resolve_text_position(self, default_position: QPointF) -> QPointF:
        if self.text_position_override is None:
            return _copy_point(default_position)
        return QPointF(default_position.x() + self.text_position_override.x(), default_position.y() + self.text_position_override.y())

    def set_text_position(self, position: QPointF | None, default_position: QPointF | None = None):
        if position is None:
            self.text_position_override = None
            return
        if default_position is None:
            self.text_position_override = _copy_point(position)
            return
        self.text_position_override = QPointF(position.x() - default_position.x(), position.y() - default_position.y())

    def get_text_position(self) -> QPointF:
        return self._resolve_text_position(self.get_default_text_position())

    def get_default_text_position(self) -> QPointF:
        return QPointF()

    def get_text_angle(self) -> float:
        return 0.0

    def _line_angle(self, start: QPointF, end: QPointF) -> float:
        return _angle_degrees(end.x() - start.x(), end.y() - start.y())

    def _draw_display_text(
        self,
        painter: QPainter,
        default_position: QPointF,
        scale_factor: float = 1.0,
        angle_degrees: float = 0.0,
    ):
        text_pos = self._resolve_text_position(default_position)
        self._draw_text(
            painter,
            text_pos,
            self.display_text,
            scale_factor=scale_factor,
            angle_degrees=angle_degrees,
        )

    @property
    def display_text(self) -> str:
        if self.text_override is not None and self.text_override.strip():
            return self.text_override.strip()
        return self._default_text()


class LinearDimension(DimensionBase):
    def __init__(
        self,
        start: QPointF,
        end: QPointF,
        dimension_type: str = "horizontal",
        offset: float = 10.0,
        style: DimensionStyle | None = None,
    ):
        super().__init__(style=style)
        self.start = QPointF(start)
        self.end = QPointF(end)
        self.dimension_type = dimension_type
        self.offset = offset

    @property
    def value(self) -> float:
        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        if self.dimension_type == "horizontal":
            return abs(dx)
        if self.dimension_type == "vertical":
            return abs(dy)
        return math.hypot(dx, dy)

    def _geometry(self):
        ext = self.style.extension_lines
        dim = self.style.dimension_line

        if self.dimension_type == "horizontal":
            reference = max(self.start.y(), self.end.y()) if self.offset >= 0 else min(self.start.y(), self.end.y())
            y_base = reference + self.offset
            outward = 1.0 if self.offset >= 0 else -1.0
            p1 = QPointF(self.start.x(), y_base)
            p2 = QPointF(self.end.x(), y_base)
            ext1_start = QPointF(self.start.x(), self.start.y() + outward * ext.gap_from_object)
            ext2_start = QPointF(self.end.x(), self.end.y() + outward * ext.gap_from_object)
            ext1_end = QPointF(p1.x(), p1.y() + outward * ext.overshoot)
            ext2_end = QPointF(p2.x(), p2.y() + outward * ext.overshoot)
            line_start = QPointF(p1.x() - dim.extension, p1.y())
            line_end = QPointF(p2.x() + dim.extension, p2.y())
            text_pos = _midpoint(p1, p2)
            return ext1_start, ext1_end, ext2_start, ext2_end, line_start, line_end, p1, p2, text_pos, (1.0, 0.0), (0.0, outward)

        if self.dimension_type == "vertical":
            reference = max(self.start.x(), self.end.x()) if self.offset >= 0 else min(self.start.x(), self.end.x())
            x_base = reference + self.offset
            outward = 1.0 if self.offset >= 0 else -1.0
            p1 = QPointF(x_base, self.start.y())
            p2 = QPointF(x_base, self.end.y())
            ext1_start = QPointF(self.start.x() + outward * ext.gap_from_object, self.start.y())
            ext2_start = QPointF(self.end.x() + outward * ext.gap_from_object, self.end.y())
            ext1_end = QPointF(p1.x() + outward * ext.overshoot, p1.y())
            ext2_end = QPointF(p2.x() + outward * ext.overshoot, p2.y())
            line_start = QPointF(p1.x(), p1.y() - dim.extension)
            line_end = QPointF(p2.x(), p2.y() + dim.extension)
            text_pos = _midpoint(p1, p2)
            return ext1_start, ext1_end, ext2_start, ext2_end, line_start, line_end, p1, p2, text_pos, (0.0, 1.0), (outward, 0.0)

        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        ux, uy = _normalize(dx, dy)
        nx, ny = -uy, ux
        shift_x = nx * self.offset
        shift_y = ny * self.offset
        normal_sign = 1.0 if self.offset >= 0 else -1.0
        p1 = _offset_point(self.start, shift_x, shift_y)
        p2 = _offset_point(self.end, shift_x, shift_y)
        ext1_start = _offset_point(self.start, nx * self.style.extension_lines.gap_from_object * normal_sign, ny * self.style.extension_lines.gap_from_object * normal_sign)
        ext2_start = _offset_point(self.end, nx * self.style.extension_lines.gap_from_object * normal_sign, ny * self.style.extension_lines.gap_from_object * normal_sign)
        ext1_end = _offset_point(p1, nx * self.style.extension_lines.overshoot * normal_sign, ny * self.style.extension_lines.overshoot * normal_sign)
        ext2_end = _offset_point(p2, nx * self.style.extension_lines.overshoot * normal_sign, ny * self.style.extension_lines.overshoot * normal_sign)
        line_start = _offset_point(p1, -ux * self.style.dimension_line.extension, -uy * self.style.dimension_line.extension)
        line_end = _offset_point(p2, ux * self.style.dimension_line.extension, uy * self.style.dimension_line.extension)
        text_pos = _midpoint(p1, p2)
        return ext1_start, ext1_end, ext2_start, ext2_end, line_start, line_end, p1, p2, text_pos, (ux, uy), (nx * normal_sign, ny * normal_sign)

    def get_bounding_box(self) -> QRectF:
        geom = self._geometry()
        return _bounding_rect(list(geom[:8]) + [geom[8]])

    def _is_small_dimension(self, arrow1_tip: QPointF, arrow2_tip: QPointF) -> bool:
        return _point_distance(arrow1_tip, arrow2_tip) < 5.0

    def _small_dimension_text_position(self, arrow_tip: QPointF, tangent: tuple[float, float]) -> QPointF:
        ux, uy = tangent
        side_offset = self.style.text.gap + self.style.arrows.size * 3.5
        return _offset_point(arrow_tip, ux * side_offset, uy * side_offset * 0.25)

    def _draw_inside_arrows(self, painter: QPainter, arrow1_tip: QPointF, arrow2_tip: QPointF):
        self._draw_arrow(painter, arrow1_tip, (arrow2_tip.x() - arrow1_tip.x(), arrow2_tip.y() - arrow1_tip.y()))
        self._draw_arrow(painter, arrow2_tip, (arrow1_tip.x() - arrow2_tip.x(), arrow1_tip.y() - arrow2_tip.y()))

    def _draw_outside_arrows(self, painter: QPainter, arrow1_tip: QPointF, arrow2_tip: QPointF, ux: float, uy: float):
        tail_1 = _offset_point(arrow1_tip, -ux * self.style.arrows.size * 2.8, -uy * self.style.arrows.size * 2.8)
        tail_2 = _offset_point(arrow2_tip, ux * self.style.arrows.size * 2.8, uy * self.style.arrows.size * 2.8)
        painter.drawLine(arrow1_tip, tail_1)
        painter.drawLine(arrow2_tip, tail_2)
        self._draw_arrow(painter, arrow1_tip, (tail_1.x() - arrow1_tip.x(), tail_1.y() - arrow1_tip.y()))
        self._draw_arrow(painter, arrow2_tip, (tail_2.x() - arrow2_tip.x(), tail_2.y() - arrow2_tip.y()))

    def draw(self, painter, scale_factor: float = 1.0):
        ext1_start, ext1_end, ext2_start, ext2_end, line_start, line_end, arrow1_tip, arrow2_tip, text_pos, tangent, _ = self._geometry()
        ux, uy = tangent
        dim_len_world = _point_distance(arrow1_tip, arrow2_tip)
        arrow_room = self.style.arrows.size * 2.4 + 1.0
        is_small_dimension = self._is_small_dimension(arrow1_tip, arrow2_tip)
        inside_arrows = not is_small_dimension and dim_len_world >= arrow_room
        text_angle = self._line_angle(line_start, line_end)
        if is_small_dimension:
            text_pos = self._small_dimension_text_position(arrow2_tip, tangent)

        ext_width = _scaled_width(self.style.extension_lines.width_px, scale_factor)
        dim_width = _scaled_width(self.style.dimension_line.width_px, scale_factor)
        painter.save()
        painter.setPen(_line_pen(self.style.extension_lines.color, self.style.extension_lines.line_type, ext_width))
        painter.drawLine(ext1_start, ext1_end)
        painter.drawLine(ext2_start, ext2_end)
        painter.setPen(_line_pen(self.style.dimension_line.color, self.style.dimension_line.line_type, dim_width))
        painter.drawLine(line_start, line_end)
        if inside_arrows:
            self._draw_inside_arrows(painter, arrow1_tip, arrow2_tip)
        else:
            self._draw_outside_arrows(painter, arrow1_tip, arrow2_tip, ux, uy)
        painter.restore()
        self._draw_display_text(
            painter,
            text_pos,
            scale_factor=scale_factor,
            angle_degrees=text_angle,
        )

    def _default_text(self) -> str:
        return _format_value(self.value)

    def get_default_text_position(self) -> QPointF:
        _, _, _, _, _, _, arrow1_tip, arrow2_tip, text_pos, tangent, _ = self._geometry()
        if self._is_small_dimension(arrow1_tip, arrow2_tip):
            text_pos = self._small_dimension_text_position(arrow2_tip, tangent)
        return _copy_point(text_pos)

    def get_text_angle(self) -> float:
        geom = self._geometry()
        line_start = geom[4]
        line_end = geom[5]
        return self._line_angle(line_start, line_end)


class RadialDimension(DimensionBase):
    def __init__(
        self,
        center: QPointF,
        radius_point: QPointF,
        dimension_type: str = "radius",
        leader_point: QPointF | None = None,
        style: DimensionStyle | None = None,
    ):
        super().__init__(style=style)
        self.center = QPointF(center)
        self.radius_point = QPointF(radius_point)
        self.dimension_type = dimension_type
        self.leader_point = QPointF(leader_point) if leader_point is not None else None

    @property
    def radius(self) -> float:
        return _point_distance(self.center, self.radius_point)

    @property
    def value(self) -> float:
        return self.radius * 2 if self.dimension_type == "diameter" else self.radius

    def _axis_direction(self) -> tuple[float, float]:
        axis_dx = self.radius_point.x() - self.center.x()
        axis_dy = self.radius_point.y() - self.center.y()
        if self.leader_point is not None:
            leader_dx = self.leader_point.x() - self.center.x()
            leader_dy = self.leader_point.y() - self.center.y()
            if abs(leader_dx) > 1e-9 or abs(leader_dy) > 1e-9:
                axis_dx, axis_dy = leader_dx, leader_dy
        return _normalize(axis_dx, axis_dy)

    def _axis_points(self) -> tuple[QPointF, QPointF, float, float]:
        ux, uy = self._axis_direction()
        radius_tip = QPointF(self.center.x() + ux * self.radius, self.center.y() + uy * self.radius)
        opposite_tip = QPointF(self.center.x() - ux * self.radius, self.center.y() - uy * self.radius)
        return radius_tip, opposite_tip, ux, uy

    def _line_end(self, radius_tip: QPointF, ux: float, uy: float) -> QPointF:
        if self.leader_point is not None:
            return QPointF(self.leader_point)
        return _offset_point(
            radius_tip,
            ux * self.style.dimension_line.extension,
            uy * self.style.dimension_line.extension,
        )

    def _text_direction_offset(self, ux: float, uy: float) -> QPointF:
        return QPointF(ux * self.style.text.gap, uy * self.style.text.gap)

    def _normal_text_offset(self, ux: float, uy: float) -> QPointF:
        return QPointF(-uy * self.style.text.gap, ux * self.style.text.gap)

    def _dimension_pen(self, scale_factor: float) -> QPen:
        return _line_pen(
            self.style.dimension_line.color,
            self.style.dimension_line.line_type,
            _scaled_width(self.style.dimension_line.width_px, scale_factor),
        )

    def _draw_dimension_geometry(self, painter: QPainter, radius_tip: QPointF, opposite_tip: QPointF, line_end: QPointF):
        if self.dimension_type == "diameter":
            painter.drawLine(opposite_tip, line_end)
            self._draw_arrow(painter, radius_tip, (opposite_tip.x() - radius_tip.x(), opposite_tip.y() - radius_tip.y()))
            self._draw_arrow(painter, opposite_tip, (radius_tip.x() - opposite_tip.x(), radius_tip.y() - opposite_tip.y()))
            return
        painter.drawLine(self.center, line_end)
        self._draw_arrow(painter, radius_tip, (self.center.x() - radius_tip.x(), self.center.y() - radius_tip.y()))

    def _default_text_position(self) -> QPointF:
        radius_tip, opposite_tip, ux, uy = self._axis_points()
        if self.dimension_type == "diameter":
            if self.leader_point is not None:
                offset = self._text_direction_offset(ux, uy)
                return _offset_point(self.leader_point, offset.x(), offset.y())
            normal_offset = self._normal_text_offset(ux, uy)
            return _offset_point(
                _midpoint(opposite_tip, radius_tip),
                normal_offset.x(),
                normal_offset.y(),
            )
        if self.leader_point is not None:
            offset = self._text_direction_offset(ux, uy)
            return _offset_point(self.leader_point, offset.x(), offset.y())
        normal_offset = self._normal_text_offset(ux, uy)
        return _offset_point(
            _midpoint(self.center, radius_tip),
            normal_offset.x(),
            normal_offset.y(),
        )

    def get_bounding_box(self) -> QRectF:
        points = [self.center, self.radius_point]
        if self.dimension_type == "diameter":
            dx = self.radius_point.x() - self.center.x()
            dy = self.radius_point.y() - self.center.y()
            points.append(QPointF(self.center.x() - dx, self.center.y() - dy))
        if self.leader_point is not None:
            points.append(self.leader_point)
        return _bounding_rect(points)

    def draw(self, painter, scale_factor: float = 1.0):
        painter.save()
        painter.setPen(self._dimension_pen(scale_factor))

        radius_tip, opposite_tip, ux, uy = self._axis_points()
        text_angle = self.get_text_angle()
        line_end = self._line_end(radius_tip, ux, uy)
        text_pos = self.get_default_text_position()
        self._draw_dimension_geometry(painter, radius_tip, opposite_tip, line_end)
        painter.restore()
        self._draw_display_text(painter, text_pos, scale_factor=scale_factor, angle_degrees=text_angle)

    def _default_text(self) -> str:
        prefix = "⌀" if self.dimension_type == "diameter" else "R"
        return f"{prefix}{_format_value(self.value)}"

    def get_default_text_position(self) -> QPointF:
        return _copy_point(self._default_text_position())

    def get_text_angle(self) -> float:
        ux, uy = self._axis_direction()
        return _angle_degrees(ux, uy)


class AngularDimension(DimensionBase):
    def __init__(
        self,
        vertex: QPointF,
        ray_start: QPointF,
        ray_end: QPointF,
        radius: float = 20.0,
        style: DimensionStyle | None = None,
    ):
        super().__init__(style=style)
        self.vertex = QPointF(vertex)
        self.ray_start = QPointF(ray_start)
        self.ray_end = QPointF(ray_end)
        self.radius = radius

    @property
    def value(self) -> float:
        a1, a2, span = self._angles()
        return math.degrees(span)

    def _angles(self) -> tuple[float, float, float]:
        a1 = math.atan2(self.ray_start.y() - self.vertex.y(), self.ray_start.x() - self.vertex.x())
        a2 = math.atan2(self.ray_end.y() - self.vertex.y(), self.ray_end.x() - self.vertex.x())
        span = (a2 - a1) % (2 * math.pi)
        if span > math.pi:
            a1, a2 = a2, a1
            span = (a2 - a1) % (2 * math.pi)
        return a1, a2, span

    def _mid_angle(self) -> float:
        a1, _, span = self._angles()
        return a1 + span / 2.0

    def _arc_point(self, angle: float) -> QPointF:
        return QPointF(
            self.vertex.x() + self.radius * math.cos(angle),
            self.vertex.y() + self.radius * math.sin(angle),
        )

    def _text_radius(self) -> float:
        return self.radius

    def _extension_pen(self, scale_factor: float) -> QPen:
        return _line_pen(
            self.style.extension_lines.color,
            self.style.extension_lines.line_type,
            _scaled_width(self.style.extension_lines.width_px, scale_factor),
        )

    def _dimension_pen(self, scale_factor: float) -> QPen:
        return _line_pen(
            self.style.dimension_line.color,
            self.style.dimension_line.line_type,
            _scaled_width(self.style.dimension_line.width_px, scale_factor),
        )

    def _extension_length(self) -> float:
        return self.radius + self.style.extension_lines.overshoot

    def _extension_end(self, angle: float) -> QPointF:
        ext_len = self._extension_length()
        return QPointF(
            self.vertex.x() + ext_len * math.cos(angle),
            self.vertex.y() + ext_len * math.sin(angle),
        )

    def _arc_path(self, a1: float, span: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(self._arc_point(a1))
        steps = max(24, int(math.degrees(span)))
        for i in range(1, steps + 1):
            angle = a1 + span * (i / steps)
            path.lineTo(self._arc_point(angle))
        return path

    def _draw_extensions(self, painter: QPainter, a1: float, a2: float):
        for angle in (a1, a2):
            painter.drawLine(self.vertex, self._extension_end(angle))

    def _draw_arc_with_arrows(self, painter: QPainter, a1: float, a2: float, span: float):
        painter.drawPath(self._arc_path(a1, span))
        start_tip = self._arc_point(a1)
        end_tip = self._arc_point(a2)
        self._draw_arrow(painter, start_tip, (-math.sin(a1), math.cos(a1)))
        self._draw_arrow(painter, end_tip, (math.sin(a2), -math.cos(a2)))

    def _default_text_position(self) -> QPointF:
        mid_angle = self._mid_angle()
        text_radius = self._text_radius()
        return QPointF(
            self.vertex.x() + text_radius * math.cos(mid_angle),
            self.vertex.y() + text_radius * math.sin(mid_angle),
        )

    def get_bounding_box(self) -> QRectF:
        a1, _, span = self._angles()
        points = [self.vertex, self.ray_start, self.ray_end]
        for i in range(17):
            angle = a1 + span * (i / 16.0)
            points.append(self._arc_point(angle))
        return _bounding_rect(points)

    def draw(self, painter, scale_factor: float = 1.0):
        a1, a2, span = self._angles()
        painter.save()
        painter.setPen(self._extension_pen(scale_factor))
        self._draw_extensions(painter, a1, a2)
        painter.setPen(self._dimension_pen(scale_factor))
        self._draw_arc_with_arrows(painter, a1, a2, span)
        painter.restore()
        text_angle = self.get_text_angle()
        self._draw_display_text(
            painter,
            self.get_default_text_position(),
            scale_factor=scale_factor,
            angle_degrees=text_angle,
        )

    def _default_text(self) -> str:
        return _format_value(self.value, "°")

    def get_default_text_position(self) -> QPointF:
        return _copy_point(self._default_text_position())

    def get_text_angle(self) -> float:
        mid_angle = self._mid_angle()
        return _angle_degrees(math.cos(mid_angle), math.sin(mid_angle)) - 90.0
