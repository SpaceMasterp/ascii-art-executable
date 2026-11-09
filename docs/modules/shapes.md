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

## Scaled reference data for verification

`tests/fixtures/shapes/metrics_h{32,64,96}.json` are generated snapshots for
Part E. Each file covers all three shapes at one height (`circle`, `cat`, and
`code` with `text="CODE"`). Regenerate them with:

```bash
python scripts/gen_shape_metrics.py
```

The generator calls `build_mask` + `geometry_metrics` for every shape/height;
no value is hand-written. It is deterministic — two runs produce byte-identical
files — and `tests/test_shape_metrics.py` checks that the committed fixtures
still match the implementation.

Top-level fields:

| field | meaning |
|---|---|
| `schema_version` | `1` |
| `cell_aspect` | `0.5`, the project-wide cell width / cell height |
| `height_rows` | row count shared by all shapes in this file |
| `generated_by` | generator path, `scripts/gen_shape_metrics.py` |
| `tolerance` | tolerances used by E (see below) |
| `shapes` | `circle`, `cat`, `code` → per-shape record |
| `scaling_expectation` | prose note plus the reference height (`32`) used by the scaling formulas |

Per-shape record:

| field | meaning |
|---|---|
| `cols`, `rows` | mask size (columns depend on the shape's physical aspect ratio) |
| `bbox_ratio` | occupied bounding-box ratio: `bbox_cols * cell_aspect / bbox_rows` |
| `allowed_cells` | number of fillable cells |
| `spans_total` | total number of maximal allowed runs over all rows |
| `rows_with_multiple_spans` | rows split by at least one hole |
| `features` | named eye/nose holes only; `{}` for `circle` and `code` |
| `hole_count` | number of named hole features: `3` for `cat`, `0` otherwise |
| `ear_gap_rows` | cat only: rows between the ear peaks; `null` otherwise |

Each feature is:

| field | meaning |
|---|---|
| `cells` | number of cells in the feature (the `A_ref` below) |
| `bbox` | inclusive `[min_row, min_col, max_row, max_col]` |
| `centroid` | `[row, col]` in **cell-centre** coordinates (`index + 0.5`) |

### Tolerance contract

For a feature measured at 32 rows with area `A_ref`:

```
A_expected(h) = A_ref * (h / 32) ** 2
area_limit(h) = max(area_rel * A_expected(h),
                    area_perimeter_factor * sqrt(A_expected(h)),
                    area_min_cells)
area_ok      = abs(cells(h) - A_expected(h)) <= area_limit(h)
centroid_ok  = abs(centroid(h)[axis] - centroid(32)[axis] * h / 32) <= centroid_abs_cells
```

The area term is **perimeter-scaled** on purpose. Reference cells are sampled at
cell centres, so a hole's measured count differs from its ideal continuous area
by the cells its outline cuts through; that error is proportional to the hole's
**perimeter**, and for area `A` the perimeter grows like `sqrt(A)`, not like a
constant. One fixed absolute number is therefore wrong at both ends of the
range: `20` cells allowed a 300% error on the 10-cell nose at 32 rows, while at
96 rows the eye's 16-cell quantisation drift already consumed 80% of the same
budget and left almost no headroom for a real regression.

Measured against the 32-row reference (`area_perimeter_factor = 4.0`,
`area_rel = 0.02`, `area_min_cells = 2`):

| feature | h | `A_ref` | `A_expected` | measured | `area_limit` | verdict |
|---|---|---|---|---|---|---|
| eye | 32 | 43 | 43 | 43 | 26.2 | pass (exact reference) |
| eye | 64 | 43 | 172 | 163 | 52.5 | pass (9-cell drift) |
| eye | 96 | 43 | 387 | 371 | 78.7 | pass (16-cell drift) |
| nose | 32 | 10 | 10 | 10 | 12.6 | pass (exact reference) |
| nose | 64 | 10 | 40 | 34 | 25.3 | pass (6-cell drift) |
| nose | 96 | 10 | 90 | 74 | 37.9 | pass (16-cell drift) |

The factor 4.0 reflects the boundary ring of a centre-sampled rasterised disc,
which is roughly `4 * sqrt(A)` cells: it admits the observed drift with a modest
margin while still rejecting a reference that is off by 50%. For large features
the 2% relative term takes over; `area_min_cells = 2` keeps degenerate one-cell
holes from having a zero budget. `bbox_ratio` is dimensionless and must not
drift with height: the three files may differ by at most
`bbox_ratio_abs = 0.05`.

`centroid` is stored in cell-centre coordinates on purpose: raw cell indices
carry a `-0.5` bias that does not scale with `h`, while `(row + 0.5)` does.
`hole_count` counts named eye/nose holes only; it is not
`len(geometry_metrics()["holes"])`, which can include incidental one-cell
quantisation components at some resolutions.

### E assertion example

```python
doc = json.loads((FIXTURES / "metrics_h32.json").read_text())
ref, tol = doc["shapes"]["cat"]["features"]["eye_left"], doc["tolerance"]
expected = ref["cells"] * (96 / 32) ** 2
limit = max(tol["area_rel"] * expected,
            tol["area_perimeter_factor"] * expected ** 0.5,
            tol["area_min_cells"])
got = len(build_mask(ShapeSpec("cat"), SizeRequest(96), FontMetrics()).features["eye_left"])
assert abs(got - expected) <= limit  # 371 vs 387, limit 78.7
```

`tests/test_shape_metrics.py` additionally checks feature-key equality at all
three heights, quadratic area scaling, linear centroid scaling, the
height-invariant `bbox_ratio`, and byte-for-byte generator idempotence. Two
negative controls guard the contract from the other side: a reference eye
inflated by 1.5x must fail the scaling invariant, and the h96 eye losing 100
cells must exceed `area_limit`.

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
