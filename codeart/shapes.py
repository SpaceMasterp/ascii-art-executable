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
    "CELL_ASPECT_TOLERANCE",
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

#: Absolute tolerance accepted for a caller-supplied cell aspect ratio.
CELL_ASPECT_TOLERANCE = 1e-9

#: Normalised units spanned by the full mask height (``v ∈ [-1, 1]``).
_SHAPE_V_SPAN = 2.0

_SHAPE_KINDS = ("circle", "cat", "code")


def _error(code: ErrorCode, message: str, location: str | None = None) -> PipelineError:
    """Build B's diagnosed failure.

    ``Diagnostic``/``ErrorCode``/``PipelineError`` are imported at the end of
    this module (``codeart.contracts`` re-exports B's types, so the import only
    works once those types exist); they are resolved at call time.
    """
    return PipelineError(Diagnostic(code, "shape", message, location=location))


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


def _validate_cell_metrics(
    cell_aspect: float | None,
    cell_width_px: float | None,
    cell_height_px: float | None,
) -> None:
    """Reject a cell metric set the project cannot honour.

    The project fixes ``cell_width_px / cell_height_px`` at
    :data:`CELL_ASPECT_DEFAULT`, so both an explicit ``cell_aspect`` and a
    width/height pair are accepted only when they resolve to that value within
    :data:`CELL_ASPECT_TOLERANCE`.
    """

    def positive(source: str, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value):
            raise _error(
                ErrorCode.INVALID_SIZE,
                f"{source} must be a finite number, got {value!r}",
                f"FontMetrics.{source}")
        if value <= 0:
            raise _error(
                ErrorCode.INVALID_SIZE,
                f"{source} must be positive, got {value!r}",
                f"FontMetrics.{source}")
        return float(value)

    if (cell_width_px is None) != (cell_height_px is None):
        raise _error(
            ErrorCode.INVALID_SIZE,
            "cell_width_px and cell_height_px must be given together",
            "FontMetrics.cell_width_px")

    ratios: list[tuple[str, float]] = []
    if cell_aspect is not None:
        ratios.append(("cell_aspect", positive("cell_aspect", cell_aspect)))
    if cell_width_px is not None:
        width = positive("cell_width_px", cell_width_px)
        height = positive("cell_height_px", cell_height_px)
        ratios.append(("cell_width_px / cell_height_px", width / height))

    for source, ratio in ratios:
        if not math.isclose(ratio, CELL_ASPECT_DEFAULT,
                            rel_tol=0.0, abs_tol=CELL_ASPECT_TOLERANCE):
            raise _error(
                ErrorCode.INVALID_SHAPE,
                f"{source} must be {CELL_ASPECT_DEFAULT} for this project, "
                f"got {ratio!r}",
                "FontMetrics.cell_aspect")


@dataclass(frozen=True, init=False)
class FontMetrics:
    """Metrics of the target font/cell.

    ``cell_aspect`` (``cell_width_px / cell_height_px``) is **derived**, never
    an independent field. The project fixes the ratio at
    :data:`CELL_ASPECT_DEFAULT` (a monospace cell is twice as tall as it is
    wide), so

    * ``FontMetrics()`` and ``FontMetrics(0.5)`` describe the same metrics;
    * ``FontMetrics(cell_width_px=8, cell_height_px=16)`` derives ``0.5`` from
      the pixel size;
    * any ratio other than that fixed value raises
      ``PipelineError(INVALID_SHAPE)`` when the metrics are constructed.

    ``cell_aspect`` stays the first parameter so ``FontMetrics(0.5)`` keeps
    working; ``font_id`` and the cell pixel size are keyword-only.
    """

    font_id: str | None = None
    cell_width_px: float | None = None
    cell_height_px: float | None = None

    def __init__(
        self,
        cell_aspect: float | None = None,
        *,
        font_id: str | None = None,
        cell_width_px: float | None = None,
        cell_height_px: float | None = None,
    ) -> None:
        _validate_cell_metrics(cell_aspect, cell_width_px, cell_height_px)
        object.__setattr__(self, "font_id", font_id)
        object.__setattr__(self, "cell_width_px", cell_width_px)
        object.__setattr__(self, "cell_height_px", cell_height_px)

    @property
    def cell_aspect(self) -> float:
        """Derived cell width / cell height; fixed at 0.5 for the project."""
        if self.cell_width_px is not None and self.cell_height_px is not None:
            return self.cell_width_px / self.cell_height_px
        return CELL_ASPECT_DEFAULT


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
    inner_radius: float | None = None


@dataclass(frozen=True)
class Mask:
    """Fillable-cell grid produced by :func:`build_mask`.

    Attributes:
        kind: the shape kind this mask was built from.
        width: number of columns (a size authority).
        height: number of rows, equals ``SizeRequest.height_rows`` (a size
            authority).
        allowed: ``allowed[row][col]`` — may the renderer put ink here?
        spans: per row, ordered non-overlapping ``(start, end)`` half-open
            intervals of allowed cells.
        font_metrics: the metrics the mask was built for.
        features: named geometry, e.g. ``eye_left`` / ``nose`` / ``code_strokes``.
        inner_radius: always ``None`` for now (rings are not supported).

    ``width`` and ``height`` are the only stored size authority. ``scale`` is a
    read-only property derived from ``height`` (the shape is normalised to
    ``v ∈ [-1, 1]``, so one shape unit is half the mask height); it is
    **derived, not authoritative** and never feeds back into the geometry.
    """

    kind: str
    width: int
    height: int
    allowed: tuple[tuple[bool, ...], ...]
    spans: tuple[tuple[tuple[int, int], ...], ...]
    font_metrics: FontMetrics
    features: Mapping[str, frozenset[tuple[int, int]]] = field(default_factory=dict)
    inner_radius: None = None

    @property
    def scale(self) -> float:
        """Rows per shape unit — derived, not authoritative."""
        return self.height / _SHAPE_V_SPAN

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
        PipelineError: the shared stage failure, always with ``stage="shape"``
            and a ``Diagnostic``. ``INVALID_SHAPE`` for an unknown ``kind``,
            ``text != "CODE"``, a non-``None`` ``inner_radius``, an unsupported
            ``cell_aspect`` or a mask with no fillable cell; ``INVALID_SIZE``
            for a non-positive or non-integer ``height_rows`` and for malformed
            cell metrics. ``ShapeError`` is a synonym of ``PipelineError``.
    """
    if not isinstance(shape_spec, ShapeSpec):
        raise _error(ErrorCode.INVALID_SHAPE,
                     f"shape_spec must be a ShapeSpec, got {type(shape_spec).__name__}",
                     "ShapeSpec")
    if not isinstance(size_request, SizeRequest):
        raise _error(ErrorCode.INVALID_SIZE,
                     f"size_request must be a SizeRequest, got {type(size_request).__name__}",
                     "SizeRequest")
    if not isinstance(font_metrics, FontMetrics):
        raise _error(ErrorCode.INVALID_SIZE,
                     f"font_metrics must be a FontMetrics, got {type(font_metrics).__name__}",
                     "FontMetrics")

    rows = size_request.height_rows
    if isinstance(rows, bool) or not isinstance(rows, int) or rows <= 0:
        raise _error(ErrorCode.INVALID_SIZE,
                     f"height_rows must be a positive integer, got {rows!r}",
                     "SizeRequest.height_rows")

    kind = shape_spec.kind
    if kind not in _SHAPE_KINDS:
        raise _error(ErrorCode.INVALID_SHAPE,
                     f"unknown shape kind {kind!r}; expected one of {_SHAPE_KINDS}",
                     "ShapeSpec.kind")

    if shape_spec.inner_radius is not None:
        raise _error(
            ErrorCode.INVALID_SHAPE,
            "ring shapes are not supported yet (inner_radius must be None)",
            "ShapeSpec.inner_radius")

    if kind == "code" and shape_spec.text not in (None, _CODE_TEXT):
        raise _error(
            ErrorCode.INVALID_SHAPE,
            f"code shape only supports text='CODE', got {shape_spec.text!r}",
            "ShapeSpec.text")

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

    # An empty mask would hand C a canvas it can never fill: reject it here
    # instead of failing later inside the layout engine.
    if not any(any(row) for row in allowed_t) or not any(spans):
        raise _error(
            ErrorCode.INVALID_SHAPE,
            f"{kind} shape has no fillable cell at {rows} rows "
            f"({cols} columns)",
            "Mask.allowed")

    frozen_features = {name: frozenset(cells) for name, cells in features.items()}

    return Mask(
        kind=kind,
        width=cols,
        height=rows,
        allowed=allowed_t,
        spans=spans,
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


# ---------------------------------------------------------------------------
# shared error contract (imported last: contracts re-exports B's types)
# ---------------------------------------------------------------------------

# `codeart.contracts` re-exports FontMetrics/Mask/ShapeSpec/SizeRequest, so it
# cannot be imported before those classes exist.  Doing it here keeps one
# initialisation direction: whichever module is imported first, the other one
# sees fully defined names.
from .contracts import Diagnostic, ErrorCode, PipelineError  # noqa: E402

#: Backwards-compatible name for B's failure. It is now the shared
#: ``PipelineError``, so ``except ShapeError`` and ``except PipelineError``
#: catch exactly the same failures.
ShapeError = PipelineError
