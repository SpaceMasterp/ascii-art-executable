"""codeart — code-art layout toolkit.

B's module lives in :mod:`codeart.shapes`: it turns a shape request into a
:class:`~codeart.shapes.Mask` describing which cells the renderer may fill.
"""

from .shapes import (
    CELL_ASPECT_DEFAULT,
    CELL_ASPECT_TOLERANCE,
    FontMetrics,
    Mask,
    ShapeError,
    ShapeSpec,
    SizeRequest,
    build_mask,
    geometry_metrics,
)

__all__ = [
    "CELL_ASPECT_DEFAULT",
    "CELL_ASPECT_TOLERANCE",
    "FontMetrics",
    "Mask",
    "ShapeError",
    "ShapeSpec",
    "SizeRequest",
    "build_mask",
    "geometry_metrics",
]

__version__ = "0.2.0"
