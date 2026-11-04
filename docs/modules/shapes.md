# Module B (v2) — shape masks (`codeart/shapes.py`)

[中文](shapes.zh-CN.md)

B no longer downsamples photos: it **generates the pattern**. Given a shape
request it returns a `Mask` — the grid of cells the layout engine (C) may fill —
plus the geometry features the verifier (F) measures. B never emits source code.

## Interface

```python
from codeart import FontMetrics, ShapeSpec, SizeRequest, build_mask, geometry_metrics

mask = build_mask(
    ShapeSpec(kind="cat"),          # "circle" | "cat" | "code"
    SizeRequest(height_rows=32),    # C decides the row count
    FontMetrics(cell_aspect=0.5),   # fixed constant for the project
)
```

`build_mask(shape_spec, size_request, font_metrics, *, ctx=None) -> Mask`

| type | fields |
|---|---|
| `FontMetrics` | `cell_aspect: float = 0.5` (cell width px / cell height px) |
| `SizeRequest` | `height_rows: int` |
| `ShapeSpec` | `kind: str`, `text: str \| None`, `font_id: str \| None`, `inner_radius: float \| None` |
| `Mask` | `kind`, `width`, `height`, `allowed[row][col]`, `spans[row]`, `scale`, `font_metrics`, `features`, `inner_radius` |

`ctx` is an optional cancellation context: if it exposes `raise_if_cancelled()`
or `check()`, that hook is called once per row (duck typing — no dependency on
F's `contracts.py`).

### Sizing

C owns the height. B derives the width from the physical aspect ratio `r`:

```
columns = ceil(height_rows × r / cell_aspect)
```

With `cell_aspect = 0.5`, a shape with `r = 1.0` at 32 rows is 64 columns wide
(physical width `64 × 0.5 = 32` equals the height). `scale = height_rows / 2`
is the number of rows per shape unit (the shape is normalised to `v ∈ [-1, 1]`).

| kind | r | 32 rows | 64 rows |
|---|---|---|---|
| `circle` | 1.0 | 64×32 | 128×64 |
| `cat` | 1.0 | 64×32 | 128×64 |
| `code` | 25/9 ≈ 2.778 | 178×32 | 356×64 |

## Shapes

### `circle`

Solid disk: a cell is allowed when `u² + v² ≤ 1`, where `(u, v)` is the cell
centre normalised so that `v ∈ [-1, 1]` and `u` is scaled by `cell_aspect`.
The bounding box is exactly the requested rectangle, so its physical aspect
ratio is 1.0.

### `cat`

Cat head: an ellipse (`rx = 0.95`, `ry = 0.80`, centre slightly below the
middle), two triangular ears whose tips reach the top edge, two elliptical eye
holes and one nose hole. Holes punch through the silhouette, so the head stays a
single connected fillable region with three interior holes.

### `code`

A solid rectangle with the word **CODE** hollowed out, using a built-in 5×7
bitmap font (one unit of letter spacing, one unit of margin on every side so
strokes never touch the mask border). `text` defaults to `"CODE"`; any other
value raises `INVALID_SHAPE`. The glyph bitmaps live in `_GLYPHS` in
`codeart/shapes.py` and are plain ASCII art, so they are easy to tweak.

## `spans` convention

`spans[row]` lists every maximal run of allowed cells on that row as half-open
`(start, end)` pairs:

- ordered by `start`, non-overlapping, `0 ≤ start < end ≤ width`;
- holes split a row into several spans (every `cat` and `code` mask has rows with
  two or more spans — e.g. the rows through the cat's eyes);
- a fully allowed row is `((0, width),)`; a fully blocked row is `()`.

Rebuilding a row from its spans must reproduce `allowed[row]` exactly; the test
suite asserts this for every shape at 32 and 64 rows.

`tests/fixtures/shapes/{circle,cat,code}_32.json` are fixed snapshots of
`allowed` + `spans` at 32 rows (≈12 KB in total) and are checked in the
regression test.

## `features`

Named geometry, each a set of 0-based `(row, col)` cells:

| key | meaning |
|---|---|
| `eye_left`, `eye_right` | eye holes (cells that are **not** allowed) |
| `nose` | nose hole |
| `ear_left`, `ear_right` | ear silhouettes (allowed cells) |
| `eyes`, `ears` | unions of the two sides |
| `code_strokes` | glyph cells hollowed out of the `code` rectangle |

Circle masks have no features (`{}`). Eye and nose sets describe the holes, so
their cells are always `allowed == False`.

## `geometry_metrics(mask)`

Helper for the verifier (E). Returns:

```
kind, cols, rows, cell_aspect,
bbox: {cols, rows, ratio},                 # ratio = cols*cell_aspect/rows
allowed_cells, spans_total, rows_with_multiple_spans,
eye_cells: {left, right}, nose_cells,
ear_gap_rows,                             # dip between the ear tips, in rows
holes: [{cells, centroid: {row, col}}],   # interior holes only
code_stroke_cells
```

## Acceptance targets (measured at 32 rows)

| metric | target | measured |
|---|---|---|
| eye cells | each ≥ 4 | 43 / 43 |
| nose cells | ≥ 2 | 10 |
| ear dip between peaks | ≥ 2 rows | 5 |
| circle bbox ratio | 1.0 ± 0.05 | 1.000 |
| determinism | two calls identical | yes (dataclass equality) |
| scaling 32 → 64 | eye area ×~4, geometry preserved | 43 → 163 (×3.79), nose 10 → 34, dip 5 → 10 |

## Errors

`ShapeError` subclasses `ValueError` and carries a stable `code`:

| code | when |
|---|---|
| `INVALID_SHAPE` | unknown `kind`, `text != "CODE"`, or `inner_radius is not None` (rings are not supported yet) |
| `INVALID_SIZE` | `height_rows` not a positive int, or `cell_aspect` not positive |

## Running the tests

```bash
python -m pytest tests/test_shapes.py -q     # 17 passed
```

The suite covers all three shapes at 32 and 64 rows, span reconstruction,
holes-not-allowed, multi-span rows, the acceptance metrics above, determinism,
error codes, the `ctx` duck-typing hook and the fixture regression.
