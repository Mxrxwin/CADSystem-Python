from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:  # pragma: no cover
    QSvgRenderer = None  # type: ignore


def _svg_icon(svg: str, size: int = 24, background: Qt.GlobalColor | None = None) -> QIcon:
    """
    Render inline SVG to QIcon.

    - Uses QtSvg (QSvgRenderer) to ensure consistent rendering.
    - Keeps icon background transparent by default (buttons already have white background).
    """
    if QSvgRenderer is None:  # pragma: no cover
        return QIcon()

    renderer = QSvgRenderer(bytearray(svg, "utf-8"))
    pixmap = QPixmap(size, size)
    if background is None:
        pixmap.fill(Qt.transparent)
    else:
        pixmap.fill(background)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def toolbar_icons(size: int = 24) -> Dict[str, QIcon]:
    """
    Thick black icons (stroke-based) in one style.
    Stroke width tuned for 24x24.
    """
    # Shared SVG header for consistent style
    base = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="1.4" '
        f'stroke-linecap="round" stroke-linejoin="round">'
    )

    # Simple, readable, “internet-style” icons (Feather-like but thicker)
    svgs: Dict[str, str] = {
        # Hand (pan)
        "pan": base
        # Classic “hand” (panning) – clearer silhouette
        + '<path d="M7 12V6.5a1.8 1.8 0 0 1 3.6 0V12"/>'
        + '<path d="M10.6 12V5.5a1.8 1.8 0 0 1 3.6 0V12"/>'
        + '<path d="M14.2 12V7.5a1.8 1.8 0 0 1 3.6 0V14"/>'
        + '<path d="M6.5 12.5c-1.4-1-3.5-.1-3.5 1.7V16c0 3.3 2.7 6 6 6h5.8c2.6 0 4.2-1.8 4.2-4.2V14"/>'
        + "</svg>",

        # Zoom in: magnifier + plus
        "zoom_in": base
        + '<circle cx="11" cy="11" r="6"/>'
        + '<path d="M20 20l-3.5-3.5"/>'
        + '<path d="M11 8.8v4.4"/>'
        + '<path d="M8.8 11h4.4"/>'
        + "</svg>",

        # Zoom out: magnifier + minus
        "zoom_out": base
        + '<circle cx="11" cy="11" r="6"/>'
        + '<path d="M20 20l-3.5-3.5"/>'
        + '<path d="M8.8 11h4.4"/>'
        + "</svg>",

        # Fit/show all: corners + outward arrows
        "show_all": base
        + '<path d="M8 3H3v5"/>'
        + '<path d="M16 3h5v5"/>'
        + '<path d="M21 16v5h-5"/>'
        + '<path d="M3 16v5h5"/>'
        + '<path d="M12 9v6"/>'
        + '<path d="M9 12h6"/>'
        + "</svg>",

        # Rotate left
        "rotate_left": base
        # Clear circular arrow (CCW)
        + '<path d="M8.2 6.2a8 8 0 1 1-2.2 5.8"/>'
        + '<path d="M6 4v4h4"/>'
        + "</svg>",

        # Rotate right
        "rotate_right": base
        # Clear circular arrow (CW)
        + '<path d="M15.8 6.2a8 8 0 1 0 2.2 5.8"/>'
        + '<path d="M18 4v4h-4"/>'
        + "</svg>",

        # Reset view: refresh arrow
        "reset_view": base
        + '<path d="M21 12a9 9 0 1 1-2.6-6.4"/>'
        + '<path d="M21 3v6h-6"/>'
        + "</svg>",

        # Edit: pencil
        "edit": base
        # Pencil (edit) – classic icon with clearer shape
        + '<path d="M12 20h9"/>'
        + '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>'
        + "</svg>",

        # Erase all: trash (clear)
        "erase": base
        + '<path d="M4 7h16"/>'
        + '<path d="M6 7l1 14h10l1-14"/>'
        + '<path d="M9 7V4h6v3"/>'
        + "</svg>",

        # Undo: curved arrow left
        "undo": base
        + '<path d="M9 14l-4-4 4-4"/>'
        + '<path d="M5 10h8a6 6 0 1 1 0 12h-2"/>'
        + "</svg>",
    }

    return {k: _svg_icon(v, size=size) for k, v in svgs.items()}


