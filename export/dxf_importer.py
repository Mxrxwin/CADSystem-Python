"""
Импорт геометрии из DXF с переносом HEADER, TABLES, BLOCKS и ENTITIES
во внутренние структуры приложения.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

import ezdxf
from ezdxf.colors import aci2rgb

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from core.geometry import Point
from core.layer import Layer
from widgets.line_segment import LineSegment
from widgets.line_style import LineStyle
from widgets.primitives import Arc, Circle, Ellipse, Polygon, Rectangle, Spline


_THICK_THRESHOLD_MM = 0.6
_BY_LAYER_MARKERS = {"BYLAYER", "BYLAYER ", ""}

_INSUNITS_LABELS = {
    0: "Unitless",
    1: "Inches",
    2: "Feet",
    3: "Miles",
    4: "Millimeters",
    5: "Centimeters",
    6: "Meters",
    7: "Kilometers",
    8: "Microinches",
    9: "Mils",
    10: "Yards",
    11: "Angstroms",
    12: "Nanometers",
    13: "Microns",
    14: "Decimeters",
    15: "Decameters",
    16: "Hectometers",
    17: "Gigameters",
    18: "Astronomical units",
    19: "Light years",
    20: "Parsecs",
}


def _qpointf(point) -> QPointF:
    return QPointF(float(point.x), float(point.y))


def _wcs_point(point, ocs=None) -> QPointF:
    if ocs is not None:
        point = ocs.to_wcs(point)
    return _qpointf(point)


def _vec_tuple(value) -> Optional[tuple[float, float, float]]:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return (float(value.x), float(value.y), float(value.z))
    try:
        if len(value) >= 3:
            return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        pass
    return None


def _close_points(p1: QPointF, p2: QPointF, eps: float = 1e-6) -> bool:
    return abs(p1.x() - p2.x()) <= eps and abs(p1.y() - p2.y()) <= eps


def _raw_entity_layer_name(entity) -> str:
    return str(getattr(entity.dxf, "layer", "0") or "0")


def _effective_layer_name(entity, inherited_layer: Optional[str] = None) -> str:
    layer_name = _raw_entity_layer_name(entity)
    if inherited_layer and layer_name == "0":
        return inherited_layer
    return layer_name


def _layer_qcolor(doc, layer_name: str) -> QColor:
    try:
        layer = doc.layers.get(layer_name)
    except Exception:
        return QColor(0, 0, 0)

    try:
        if hasattr(layer, "rgb") and layer.rgb is not None:
            rgb = layer.rgb
            if hasattr(rgb, "r"):
                return QColor(int(rgb.r), int(rgb.g), int(rgb.b))
            return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:
        pass

    try:
        aci = layer.get_color()
        rgb = aci2rgb(aci if 0 < aci <= 255 else 7)
        if hasattr(rgb, "r"):
            return QColor(int(rgb.r), int(rgb.g), int(rgb.b))
    except Exception:
        pass
    return QColor(0, 0, 0)


def _entity_qcolor(doc, entity, effective_layer_name: Optional[str] = None) -> QColor:
    try:
        true_color = getattr(entity.dxf, "true_color", None)
        if true_color:
            from ezdxf import colors as ezdxf_colors

            r, g, b = ezdxf_colors.int2rgb(int(true_color))
            return QColor(int(r), int(g), int(b))
    except Exception:
        pass

    try:
        if hasattr(entity, "rgb") and entity.rgb is not None:
            rgb = entity.rgb
            if hasattr(rgb, "r"):
                return QColor(int(rgb.r), int(rgb.g), int(rgb.b))
            return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:
        pass

    aci = getattr(entity.dxf, "color", 256)
    if aci == 256:
        return _layer_qcolor(doc, effective_layer_name or _raw_entity_layer_name(entity))

    try:
        rgb = aci2rgb(aci if 0 < aci <= 255 else 7)
        if hasattr(rgb, "r"):
            return QColor(int(rgb.r), int(rgb.g), int(rgb.b))
    except Exception:
        pass
    return QColor(0, 0, 0)


def _entity_linetype(doc, entity, effective_layer_name: Optional[str] = None) -> str:
    linetype = str(getattr(entity.dxf, "linetype", "Continuous") or "Continuous").strip()
    if linetype.upper() in _BY_LAYER_MARKERS:
        try:
            layer = doc.layers.get(effective_layer_name or _raw_entity_layer_name(entity))
            linetype = getattr(layer.dxf, "linetype", "Continuous") or "Continuous"
        except Exception:
            linetype = "Continuous"
    return str(linetype).strip() or "Continuous"


def _entity_uses_bylayer_linetype(entity) -> bool:
    raw = str(getattr(entity.dxf, "linetype", "BYLAYER") or "BYLAYER").strip().upper()
    return raw in _BY_LAYER_MARKERS


def _entity_lineweight_mm(doc, entity, effective_layer_name: Optional[str] = None) -> float:
    lineweight = getattr(entity.dxf, "lineweight", -3)
    if lineweight == -1:
        try:
            layer = doc.layers.get(effective_layer_name or _raw_entity_layer_name(entity))
            lineweight = getattr(layer.dxf, "lineweight", -3)
        except Exception:
            lineweight = -3
    if lineweight < 0:
        lineweight = 25
    if lineweight == 0:
        lineweight = 25
    return float(lineweight) / 100.0


def _style_name_from_entity(doc, entity, effective_layer_name: Optional[str] = None) -> str:
    if _entity_uses_bylayer_linetype(entity):
        return "По слою"

    linetype = _entity_linetype(doc, entity, effective_layer_name).strip().upper()
    thickness_mm = _entity_lineweight_mm(doc, entity, effective_layer_name)

    if linetype in {"CAD_DASHED", "DASHED"} or "HIDDEN" in linetype:
        return "Штриховая"
    if linetype in {"CAD_CENTER", "CENTER"}:
        return "Штрихпунктирная утолщенная"
    if linetype in {"CAD_DASHDOT", "DASHDOT"}:
        if thickness_mm >= _THICK_THRESHOLD_MM:
            return "Штрихпунктирная утолщенная"
        return "Штрихпунктирная тонкая"
    if linetype in {"CAD_PHANTOM", "DASHDOT2", "PHANTOM"}:
        return "Штрихпунктирная с двумя точками"
    if thickness_mm >= _THICK_THRESHOLD_MM:
        return "Сплошная основная"
    return "Сплошная тонкая"


def _style_for_entity(doc, entity, style_manager, effective_layer_name: Optional[str] = None) -> Optional[LineStyle]:
    if style_manager is None:
        return None

    base_name = _style_name_from_entity(doc, entity, effective_layer_name)
    base_style = style_manager.get_style(base_name)
    if base_style is None:
        return None

    thickness_mm = min(max(_entity_lineweight_mm(doc, entity, effective_layer_name), 0.25), 1.4)
    if abs(thickness_mm - getattr(base_style, "thickness_mm", thickness_mm)) < 1e-9:
        return base_style

    cloned = base_style.clone(new_name=base_style.name)
    cloned._is_gost_base = True
    cloned.thickness_mm = thickness_mm
    return cloned


def _apply_common_properties(doc, entity, obj, style_manager, inherited_layer: Optional[str] = None) -> None:
    layer_name = _effective_layer_name(entity, inherited_layer)
    obj.layer_name = layer_name
    if hasattr(obj, "style"):
        obj.style = _style_for_entity(doc, entity, style_manager, layer_name)
    if hasattr(obj, "_legacy_color"):
        obj._legacy_color = _entity_qcolor(doc, entity, layer_name)
    if hasattr(obj, "_legacy_width"):
        obj._legacy_width = (_entity_lineweight_mm(doc, entity, layer_name) * 96.0) / 25.4
    obj._from_dxf_import = True


def _normalize_polyline_points(points: list[QPointF]) -> list[QPointF]:
    if len(points) > 1 and _close_points(points[0], points[-1]):
        return points[:-1]
    return points


def _is_axis_aligned_rectangle(points: list[QPointF]) -> bool:
    points = _normalize_polyline_points(points)
    if len(points) != 4:
        return False
    xs = {round(point.x(), 6) for point in points}
    ys = {round(point.y(), 6) for point in points}
    return len(xs) == 2 and len(ys) == 2


def _rectangle_from_points(points: list[QPointF]) -> Rectangle:
    normalized = _normalize_polyline_points(points)
    min_x = min(point.x() for point in normalized)
    max_x = max(point.x() for point in normalized)
    min_y = min(point.y() for point in normalized)
    max_y = max(point.y() for point in normalized)
    return Rectangle(QPointF(min_x, max_y), QPointF(max_x, min_y), style=None)


def _regular_polygon_from_points(points: list[QPointF]) -> Optional[Polygon]:
    normalized = _normalize_polyline_points(points)
    if len(normalized) < 3:
        return None

    center_x = sum(point.x() for point in normalized) / len(normalized)
    center_y = sum(point.y() for point in normalized) / len(normalized)
    center = QPointF(center_x, center_y)

    radii = [
        math.hypot(point.x() - center_x, point.y() - center_y)
        for point in normalized
    ]
    if min(radii) <= 1e-6:
        return None

    radius_avg = sum(radii) / len(radii)
    if max(abs(radius - radius_avg) for radius in radii) > radius_avg * 0.03:
        return None

    sides = []
    for index in range(len(normalized)):
        p1 = normalized[index]
        p2 = normalized[(index + 1) % len(normalized)]
        sides.append(math.hypot(p2.x() - p1.x(), p2.y() - p1.y()))
    side_avg = sum(sides) / len(sides)
    if side_avg <= 1e-6:
        return None
    if max(abs(side - side_avg) for side in sides) > side_avg * 0.03:
        return None

    start_angle = math.atan2(normalized[0].y() - center_y, normalized[0].x() - center_x)
    return Polygon(center, radius_avg, len(normalized), style=None, start_angle=start_angle)


def _segments_from_points(points: list[QPointF], closed: bool) -> list[LineSegment]:
    normalized = _normalize_polyline_points(points)
    segments = []
    if len(normalized) < 2:
        return segments
    for index in range(len(normalized) - 1):
        segments.append(LineSegment(normalized[index], normalized[index + 1], style=None))
    if closed and len(normalized) > 2:
        segments.append(LineSegment(normalized[-1], normalized[0], style=None))
    return segments


def _import_line(doc, entity, style_manager, inherited_layer=None):
    line = LineSegment(_qpointf(entity.dxf.start), _qpointf(entity.dxf.end), style=None)
    _apply_common_properties(doc, entity, line, style_manager, inherited_layer)
    return line


def _import_circle(doc, entity, style_manager, inherited_layer=None):
    center = _wcs_point(entity.dxf.center, entity.ocs())
    circle = Circle(center, float(entity.dxf.radius), style=None)
    _apply_common_properties(doc, entity, circle, style_manager, inherited_layer)
    return circle


def _import_arc(doc, entity, style_manager, inherited_layer=None):
    center = _wcs_point(entity.dxf.center, entity.ocs())
    radius = float(entity.dxf.radius)
    arc = Arc(
        center,
        radius,
        radius,
        float(entity.dxf.start_angle) % 360.0,
        float(entity.dxf.end_angle) % 360.0,
        style=None,
        rotation_angle=0.0,
    )
    _apply_common_properties(doc, entity, arc, style_manager, inherited_layer)
    return arc


def _import_ellipse(doc, entity, style_manager, inherited_layer=None):
    center = _qpointf(entity.dxf.center)
    major = entity.dxf.major_axis
    radius_x = math.hypot(float(major.x), float(major.y))
    radius_y = radius_x * float(entity.dxf.ratio)
    rotation_angle = math.atan2(float(major.y), float(major.x))
    ellipse = Ellipse(
        center,
        radius_x,
        radius_y,
        style=None,
        rotation_angle=rotation_angle,
    )
    _apply_common_properties(doc, entity, ellipse, style_manager, inherited_layer)
    return ellipse


def _import_lwpolyline(doc, entity, style_manager, inherited_layer=None):
    points = [_qpointf(point) for point in entity.vertices_in_wcs()]
    if not points:
        return None

    closed = bool(entity.closed)
    if closed and _is_axis_aligned_rectangle(points):
        rectangle = _rectangle_from_points(points)
        _apply_common_properties(doc, entity, rectangle, style_manager, inherited_layer)
        return rectangle

    if closed:
        polygon = _regular_polygon_from_points(points)
        if polygon is not None:
            _apply_common_properties(doc, entity, polygon, style_manager, inherited_layer)
            return polygon

    objects = _segments_from_points(points, closed)
    for obj in objects:
        _apply_common_properties(doc, entity, obj, style_manager, inherited_layer)
    return objects


def _polyline_vertices(entity) -> list[QPointF]:
    points = []
    try:
        points = [_qpointf(point) for point in entity.points_in_wcs()]
    except Exception:
        pass
    return points


def _import_polyline(doc, entity, style_manager, inherited_layer=None):
    points = _polyline_vertices(entity)
    if not points:
        return None

    closed = bool(getattr(entity, "is_closed", False))
    if closed and _is_axis_aligned_rectangle(points):
        rectangle = _rectangle_from_points(points)
        _apply_common_properties(doc, entity, rectangle, style_manager, inherited_layer)
        return rectangle

    if closed:
        polygon = _regular_polygon_from_points(points)
        if polygon is not None:
            _apply_common_properties(doc, entity, polygon, style_manager, inherited_layer)
            return polygon

    objects = _segments_from_points(points, closed)
    for obj in objects:
        _apply_common_properties(doc, entity, obj, style_manager, inherited_layer)
    return objects


def _spline_point_to_xy(point) -> QPointF:
    if hasattr(point, "x") and hasattr(point, "y"):
        return QPointF(float(point.x), float(point.y))
    return QPointF(float(point[0]), float(point[1]))


def _import_spline(doc, entity, style_manager, inherited_layer=None):
    points = []
    try:
        if getattr(entity, "fit_point_count", lambda: 0)() > 0:
            points = list(entity.fit_points)
        if not points and getattr(entity, "control_point_count", lambda: 0)() > 0:
            points = list(entity.control_points)
    except Exception:
        pass

    if len(points) < 2:
        return None

    spline = Spline([_spline_point_to_xy(point) for point in points], style=None)
    _apply_common_properties(doc, entity, spline, style_manager, inherited_layer)
    return spline


def _import_point(doc, entity, style_manager, inherited_layer=None):
    point = Point(entity.dxf.location.x, entity.dxf.location.y)
    point.layer_name = _effective_layer_name(entity, inherited_layer)
    point._from_dxf_import = True
    return point


def _extract_header_metadata(doc) -> dict:
    header = doc.header
    units_code = int(header.get("$INSUNITS", 0) or 0)
    return {
        "version": str(header.get("$ACADVER", "UNKNOWN")),
        "units_code": units_code,
        "units_name": _INSUNITS_LABELS.get(units_code, f"Code {units_code}"),
        "extmin": _vec_tuple(header.get("$EXTMIN")),
        "extmax": _vec_tuple(header.get("$EXTMAX")),
        "limmin": _vec_tuple(header.get("$LIMMIN")),
        "limmax": _vec_tuple(header.get("$LIMMAX")),
    }


def _extract_linetype_metadata(doc) -> list[dict]:
    linetypes = []
    for linetype in doc.linetypes:
        try:
            linetypes.append(
                {
                    "name": str(getattr(linetype.dxf, "name", "")),
                    "description": str(getattr(linetype.dxf, "description", "")),
                }
            )
        except Exception:
            continue
    return linetypes


def _extract_block_metadata(doc) -> list[str]:
    names = []
    for block in doc.blocks:
        try:
            name = str(getattr(block.block.dxf, "name", "") or "")
            if name and not name.startswith("*"):
                names.append(name)
        except Exception:
            continue
    return names


def _ensure_layers_from_dxf(doc, layer_manager) -> None:
    if layer_manager is None:
        return

    for dxf_layer in doc.layers:
        name = str(getattr(dxf_layer.dxf, "name", "") or "").strip()
        if not name:
            continue

        color = _layer_qcolor(doc, name)
        linetype = str(getattr(dxf_layer.dxf, "linetype", "Continuous") or "Continuous")
        visible = not bool(getattr(dxf_layer, "is_off", lambda: False)())
        existing = layer_manager.get_layer(name)
        if existing is None:
            layer_manager.add_layer(
                Layer(
                    name=name,
                    color=color,
                    line_type=linetype,
                    visible=visible,
                )
            )
        else:
            layer_manager.update_layer(
                name,
                color=color,
                line_type=linetype,
                visible=visible,
            )


def _flatten_result(result) -> Iterable:
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


def import_dxf_from_file(filepath: str, scene, layer_manager=None, style_manager=None) -> int:
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    _ensure_layers_from_dxf(doc, layer_manager)
    if hasattr(scene, "set_dxf_metadata"):
        scene.set_dxf_metadata(
            {
                "header": _extract_header_metadata(doc),
                "linetypes": _extract_linetype_metadata(doc),
                "blocks": _extract_block_metadata(doc),
            }
        )

    handlers = {
        "LINE": _import_line,
        "CIRCLE": _import_circle,
        "ARC": _import_arc,
        "ELLIPSE": _import_ellipse,
        "LWPOLYLINE": _import_lwpolyline,
        "POLYLINE": _import_polyline,
        "SPLINE": _import_spline,
        "POINT": _import_point,
    }

    def process_entity(entity, inherited_layer: Optional[str] = None):
        if entity.dxftype() == "INSERT":
            insert_layer = _effective_layer_name(entity, inherited_layer)
            objects = []
            try:
                for virtual_entity in entity.virtual_entities(redraw_order=True):
                    objects.extend(_flatten_result(process_entity(virtual_entity, insert_layer)))
            except Exception:
                return None
            return objects

        handler = handlers.get(entity.dxftype())
        if handler is None:
            return None
        return handler(doc, entity, style_manager, inherited_layer)

    imported = []
    for entity in msp:
        try:
            imported.extend(_flatten_result(process_entity(entity)))
        except Exception:
            continue

    for obj in imported:
        scene.add_object(obj)

    return len(imported)
