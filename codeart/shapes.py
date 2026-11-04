"""B (v2): pattern generation — shape masks for the code-art layout engine.

The layout engine (C) asks B for a :class:`Mask`: a grid of cells that the
renderer may fill, plus the geometry metadata the verifier (F) needs.  B only
decides *where ink may go*; it never emits source code.

Public API::

    from codeart import build_mask, FontMetrics, SizeRequest, ShapeSpec
    mask = build_mask(ShapeSpec("cat"), SizeRequest(height_rows=32),
                      FontMetrics(cell_aspect=0.5))

Three shapes are supported:

``circle``
    Solid disk inscribed in the requested rectangle.

``cat``
    Cat head: elliptical head plus two triangular ears, with two eye holes and
    one nose hole punched through the fillable area.

``code``
    A solid rectangle with the word ``CODE`` hollowed out, using a built-in
    5x7 bitmap font (one unit of letter spacing, one unit of margin).

Coordinates: ``(row, col)``, 0-based.  ``allowed[row][col]`` is ``True`` when the
cell may be filled; ``spans[row]`` lists the maximal ``(start, end)`` half-open
ranges of allowed cells on that row (ordered, non-overlapping, holes split a
row into several spans).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

__all__ = [
    "CELL_ASPECT_DEFAULT",
    "FontMetrics",
    "Mask",
    "ShapeError",
    "ShapeSpec",
    "SizeRequest",
    "build_mask",
    "geometry_metrics",
]

#: Fixed cell aspect ratio: ``cell_width_px / cell_height_px`` (see plan v1.4).
CELL_ASPECT_DEFAULT = 0.5

_SHAPE_KINDS = ("circle", "cat", "code")

# ---------------------------------------------------------------------------
# built-in 5x7 bitmap font for the hollow CODE shape ('#' = stroke, '.' = gap)
# ---------------------------------------------------------------------------

_GLYPH_W = 5
_GLYPH_H = 7
_GLYPH_GAP = 1          # one unit of letter spacing
_GLYPH_MARGIN = 1       # border so strokes never touch the mask edge
_GLYPHS: Mapping[str, Sequence[str]] = {
    "C": (
        ".###.",
        "#...#",
        "#....",
        "#....",
        "#....",
        "#...#",
        ".###.",
    ),
    "O": (
        ".###.",
        "#...#",
        "#...#",
        "#...#",
        "#...#",
        "#...#",
        ".###.",
    ),
    "D": (
        "####.",
        "#...#",
        "#...#",
        "#...#",
        "#...#",
        "#...#",
        "####.",
    ),
    "E": (
        "#####",
        "#....",
        "#....",
        "####.",
        "#....",
        "#....",
        "#####",
    ),
}
_CODE_TEXT = "CODE"
#: Shape width/height in font units, including margins and spacing.
CODE_UNITS_W = _GLYPH_MARGIN * 2 + len(_CODE_TEXT) * _GLYPH_W + (
    len(_CODE_TEXT) - 1) * _GLYPH_GAP
CODE_UNITS_H = _GLYPH_MARGIN * 2 + _GLYPH_H

# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------


class ShapeError(ValueError):
    """Raised when a shape request cannot be honoured.

    ``code`` is a stable machine-readable string (``INVALID_SHAPE`` or
    ``INVALID_SIZE``) so callers can map errors without parsing messages.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FontMetrics:
    """Metrics of the target font/cell.

    ``cell_aspect`` is ``cell_width_px / cell_height_px`` and is fixed to 0.5
    for the project (a monospace cell is twice as tall as it is wide).
    """

    cell_aspect: float = CELL_ASPECT_DEFAULT

    def __post_init__(self) -> None:
        if not isinstance(self.cell_aspect, (int, float)) or isinstance(
                self.cell_aspect, bool) or not self.cell_aspect > 0:
            raise ShapeError(
                "INVALID_SIZE",
                f"cell_aspect must be a positive number, got "
                f"{self.cell_aspect!r}")


@dataclass(frozen=True)
class SizeRequest:
    """Requested mask height in rows; C decides this before asking for a mask."""

    height_rows: int


@dataclass(frozen=True)
class ShapeSpec:
    """Which pattern to build.

    ``kind`` is ``"circle"``, ``"cat"`` or ``"code"``.  ``text`` is only used by
    the ``code`` shape and must be ``"CODE"``.  ``inner_radius`` is reserved for
    ring shapes and currently must stay ``None``.
    """

    kind: str
    text: str | None = None
    font_id: str | None = None
    inner_radius: float | None = None


@dataclass(frozen=True)
class Mask:
    """Fillable-cell grid produced by :func:`build_mask`.

    Attributes:
        width: number of columns.
        height: number of rows (equals ``SizeRequest.height_rows``).
        allowed: ``allowed[row][col]`` — may the renderer put ink here?
        spans: per row, ordered non-overlapping ``(start, end)`` half-open
            intervals of allowed cells.
        scale: rows per shape unit (the shape is normalised to v ∈ [-1, 1]).
        font_metrics: the metrics the mask was built for.
        features: named geometry, e.g. ``eye_left`` / ``nose`` / ``code_strokes``.
        inner_radius: always ``None`` for now (rings are not supported).
        kind: the shape kind this mask was built from.
    """

    kind: str
    width: int
    height: int
    allowed: tuple[tuple[bool, ...], ...]
    spans: tuple[tuple[tuple[int, int], ...], ...]
    scale: float
    font_metrics: FontMetrics
    features: Mapping[str, frozenset[tuple[int, int]]] = field(default_factory=dict)
    inner_radius: None = None

    def row_spans(self, row: int) -> tuple[tuple[int, int], ...]:
        """Return the spans of ``row`` (convenience alias for ``spans[row]``)."""
        return self.spans[row]


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _cell_uv(col: int, row: int, cols: int, rows: int, aspect: float) -> tuple[float, float]:
    """Map a cell centre to normalised coordinates (v ∈ [-1, 1], u scaled by aspect)."""
    v = (row + 0.5) * 2.0 / rows - 1.0
    u = ((col + 0.5) - cols / 2.0) * aspect * 2.0 / rows
    return u, v


def _in_ellipse(u: float, v: float, cx: float, cy: float, rx: float, ry: float) -> bool:
    if rx <= 0 or ry <= 0:
        return False
    du = (u - cx) / rx
    dv = (v - cy) / ry
    return du * du + dv * dv <= 1.0 + 1e-12


def _in_triangle(u: float, v: float, tri: Sequence[tuple[float, float]]) -> bool:
    (x1, y1), (x2, y2), (x3, y3) = tri

    def sign(ax: float, ay: float, bx: float, by: float) -> float:
        return (ax - u) * (by - v) - (bx - u) * (ay - v)

    d1 = sign(x1, y1, x2, y2)
    d2 = sign(x2, y2, x3, y3)
    d3 = sign(x3, y3, x1, y1)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


# cat geometry (normalised u/v; v = -1 is the top edge)
_CAT_HEAD = (0.0, 0.12, 0.95, 0.80)          # cx, cy, rx, ry
_CAT_EARS = (
    ((-0.62, -1.05), (-0.98, -0.28), (-0.24, -0.46)),
    ((0.62, -1.05), (0.98, -0.28), (0.24, -0.46)),
)
_CAT_EYES = ((-0.33, -0.02, 0.17, 0.15), (0.33, -0.02, 0.17, 0.15))
_CAT_NOSE = (0.0, 0.30, 0.09, 0.06)


def _shape_ratio(kind: str) -> float:
    """Physical width/height ratio ``r`` used by ``columns = ceil(rows*r/aspect)``."""
    if kind == "circle":
        return 1.0
    if kind == "cat":
        return 1.0
    return CODE_UNITS_W / CODE_UNITS_H


def _circle_rows(cols: int, rows: int, aspect: float, ctx) -> list[list[bool]]:
    allowed = []
    for y in range(rows):
        _check_ctx(ctx)
        row = []
        for x in range(cols):
            u, v = _cell_uv(x, y, cols, rows, aspect)
            row.append(u * u + v * v <= 1.0 + 1e-9)
        allowed.append(row)
    return allowed


def _cat_rows(cols: int, rows: int, aspect: float, ctx) -> tuple[list[list[bool]], dict]:
    features: dict[str, set] = {
        "eye_left": set(), "eye_right": set(), "nose": set(),
        "ear_left": set(), "ear_right": set(),
    }
    allowed = []
    for y in range(rows):
        _check_ctx(ctx)
        row = []
        for x in range(cols):
            u, v = _cell_uv(x, y, cols, rows, aspect)
            body = _in_ellipse(u, v, *_CAT_HEAD)
            ear_l = _in_triangle(u, v, _CAT_EARS[0])
            ear_r = _in_triangle(u, v, _CAT_EARS[1])
            eye_l = _in_ellipse(u, v, *_CAT_EYES[0])
            eye_r = _in_ellipse(u, v, *_CAT_EYES[1])
            nose = _in_ellipse(u, v, *_CAT_NOSE)
            # holes punch through the solid silhouette
            ok = (body or ear_l or ear_r) and not (eye_l or eye_r or nose)
            row.append(ok)
            # features describe geometry, not fillability: the eyes and nose are
            # always holes, so they must be recorded regardless of `ok`.
            if eye_l:
                features["eye_left"].add((y, x))
            if eye_r:
                features["eye_right"].add((y, x))
            if nose:
                features["nose"].add((y, x))
            if ear_l:
                features["ear_left"].add((y, x))
            if ear_r:
                features["ear_right"].add((y, x))
        allowed.append(row)
    merged = dict(features)
    merged["eyes"] = features["eye_left"] | features["eye_right"]
    merged["ears"] = features["ear_left"] | features["ear_right"]
    return allowed, merged


def _code_rows(cols: int, rows: int, aspect: float, ctx) -> tuple[list[list[bool]], dict]:
    strokes: set[tuple[int, int]] = set()
    allowed = []
    for y in range(rows):
        _check_ctx(ctx)
        row = []
        for x in range(cols):
            ux = (x + 0.5) * CODE_UNITS_W / cols
            uy = (y + 0.5) * CODE_UNITS_H / rows
            inside = (_GLYPH_MARGIN <= ux < CODE_UNITS_W - _GLYPH_MARGIN
                      and _GLYPH_MARGIN <= uy < CODE_UNITS_H - _GLYPH_MARGIN)
            stroke = False
            if inside:
                gx = int(ux - _GLYPH_MARGIN)
                gy = int(uy - _GLYPH_MARGIN)
                letter_index, pos = divmod(gx, _GLYPH_W + _GLYPH_GAP)
                if pos < _GLYPH_W and 0 <= gy < _GLYPH_H:
                    glyph = _GLYPHS[_CODE_TEXT[letter_index]]
                    stroke = glyph[gy][pos] == "#"
            row.append(not stroke)
            if stroke:
                strokes.add((y, x))
        allowed.append(row)
    return allowed, {"code_strokes": strokes}


def _check_ctx(ctx) -> None:
    """Best-effort cancellation hook (duck-typed, no hard dependency on F)."""
    if ctx is None:
        return
    for name in ("raise_if_cancelled", "check"):
        hook = getattr(ctx, name, None)
        if callable(hook):
            hook()
            return


def _spans_from_rows(allowed: Sequence[Sequence[bool]]) -> tuple[tuple[tuple[int, int], ...], ...]:
    spans = []
    for row in allowed:
        row_spans = []
        start = None
        for col, ok in enumerate(row):
            if ok and start is None:
                start = col
            elif not ok and start is not None:
                row_spans.append((start, col))
                start = None
        if start is not None:
            row_spans.append((start, len(row)))
        spans.append(tuple(row_spans))
    return tuple(spans)


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------


def build_mask(
    shape_spec: ShapeSpec,
    size_request: SizeRequest,
    font_metrics: FontMetrics,
    *,
    ctx=None,
) -> Mask:
    """Build the fillable-cell mask for ``shape_spec``.

    Args:
        shape_spec: which pattern (``circle`` / ``cat`` / ``code``).
        size_request: requested height in rows; C owns this decision.
        font_metrics: cell metrics, ``cell_aspect`` is fixed at 0.5.
        ctx: optional cancellation context exposing ``raise_if_cancelled()`` or
            ``check()``; called once per row.

    Raises:
        ShapeError: ``INVALID_SHAPE`` for unknown kinds, ``text != "CODE"`` or a
            non-``None`` ``inner_radius``; ``INVALID_SIZE`` for a non-positive or
            non-integer ``height_rows`` / a bad ``cell_aspect``.
    """
    if not isinstance(shape_spec, ShapeSpec):
        raise ShapeError("INVALID_SHAPE", f"shape_spec must be a ShapeSpec, got {type(shape_spec).__name__}")
    if not isinstance(size_request, SizeRequest):
        raise ShapeError("INVALID_SIZE", f"size_request must be a SizeRequest, got {type(size_request).__name__}")
    if not isinstance(font_metrics, FontMetrics):
        raise ShapeError("INVALID_SIZE", f"font_metrics must be a FontMetrics, got {type(font_metrics).__name__}")

    rows = size_request.height_rows
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
        raise ShapeError("INVALID_SIZE", f"height_rows must be a positive integer, got {rows!r}")

    kind = shape_spec.kind
    if kind not in _SHAPE_KINDS:
        raise ShapeError("INVALID_SHAPE", f"unknown shape kind {kind!r}; expected one of {_SHAPE_KINDS}")

    if shape_spec.inner_radius is not None:
        raise ShapeError(
            "INVALID_SHAPE",
            "ring shapes are not supported yet (inner_radius must be None)")

    if kind == "code" and shape_spec.text not in (None, _CODE_TEXT):
        raise ShapeError(
            "INVALID_SHAPE",
            f"code shape only supports text='CODE', got {shape_spec.text!r}")

    aspect = font_metrics.cell_aspect
    cols = max(1, math.ceil(rows * _shape_ratio(kind) / aspect))

    if kind == "circle":
        allowed = _circle_rows(cols, rows, aspect, ctx)
        features: Mapping[str, Iterable] = {}
    elif kind == "cat":
        allowed, features = _cat_rows(cols, rows, aspect, ctx)
    else:
        allowed, features = _code_rows(cols, rows, aspect, ctx)

    allowed_t = tuple(tuple(bool(v) for v in row) for row in allowed)
    spans = _spans_from_rows(allowed_t)
    frozen_features = {name: frozenset(cells) for name, cells in features.items()}

    return Mask(
        kind=kind,
        width=cols,
        height=rows,
        allowed=allowed_t,
        spans=spans,
        scale=rows / 2.0,
        font_metrics=font_metrics,
        features=frozen_features,
        inner_radius=None,
    )


# ---------------------------------------------------------------------------
# metrics for the verifier (E)
# ---------------------------------------------------------------------------


def _holes(mask: Mask) -> list[dict]:
    """Connected components of disallowed cells that do not touch the border."""
    rows, cols = mask.height, mask.width
    seen = [[False] * cols for _ in range(rows)]
    holes = []
    for r in range(rows):
        for c in range(cols):
            if mask.allowed[r][c] or seen[r][c]:
                continue
            stack = [(r, c)]
            seen[r][c] = True
            cells = []
            border = False
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                if y in (0, rows - 1) or x in (0, cols - 1):
                    border = True
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < rows and 0 <= nx < cols and not seen[ny][nx] \
                            and not mask.allowed[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            if not border:
                holes.append({
                    "cells": len(cells),
                    "centroid": {
                        "row": sum(y for y, _ in cells) / len(cells),
                        "col": sum(x for _, x in cells) / len(cells),
                    },
                })
    return holes


def geometry_metrics(mask: Mask) -> dict:
    """Return the measurable geometry of ``mask`` (consumed by the verifier)."""
    rows, cols = mask.height, mask.width
    aspect = mask.font_metrics.cell_aspect

    occupied_rows = [r for r in range(rows) if any(mask.allowed[r])]
    occupied_cols = [c for c in range(cols) if any(mask.allowed[r][c] for r in range(rows))]
    bbox_h = (max(occupied_rows) - min(occupied_rows) + 1) if occupied_rows else 0
    bbox_w = (max(occupied_cols) - min(occupied_cols) + 1) if occupied_cols else 0

    eye_left = len(mask.features.get("eye_left", ()))
    eye_right = len(mask.features.get("eye_right", ()))
    nose = len(mask.features.get("nose", ()))

    ear_gap_rows = 0
    ears = mask.features.get("ears")
    if ears:
        # top_row[c] = first fillable row in column c (None if the column is empty)
        top_row = []
        for c in range(cols):
            top_row.append(next((r for r in range(rows) if mask.allowed[r][c]), None))
        peak_row = min(r for r, _ in ears)
        left = mask.features.get("ear_left", frozenset())
        right = mask.features.get("ear_right", frozenset())
        left_apex = {c for r, c in left if r == peak_row}
        right_apex = {c for r, c in right if r == peak_row}
        if left_apex and right_apex:
            # The dip between the peaks is measured on the centre line between
            # the two ear tips (the sag between the ears), not over the whole
            # gap — the ears slope outward, so their bases would mask the dip.
            mid = round((sum(left_apex) / len(left_apex)
                         + sum(right_apex) / len(right_apex)) / 2)
            if 0 <= mid < cols and top_row[mid] is not None:
                ear_gap_rows = top_row[mid] - peak_row

    return {
        "kind": mask.kind,
        "cols": cols,
        "rows": rows,
        "cell_aspect": aspect,
        "bbox": {
            "cols": bbox_w,
            "rows": bbox_h,
            "ratio": (bbox_w * aspect / bbox_h) if bbox_h else 0.0,
        },
        "allowed_cells": sum(sum(1 for v in row if v) for row in mask.allowed),
        "spans_total": sum(len(s) for s in mask.spans),
        "rows_with_multiple_spans": sum(1 for s in mask.spans if len(s) > 1),
        "eye_cells": {"left": eye_left, "right": eye_right},
        "nose_cells": nose,
        "ear_gap_rows": ear_gap_rows,
        "holes": _holes(mask),
        "code_stroke_cells": len(mask.features.get("code_strokes", ())),
    }
