# Part B — Image / Slogan → Character Grid

[中文](README.zh-CN.md)

This directory is **part B** of the *ASCII Art Executable* project: the pattern-input
module. It turns an image (PNG/JPG) or a short slogan into a dense character grid
(`PixelGrid`) where every cell maps to exactly one source column, with an explicit
foreground/background mask and a JSON sidecar that downstream modules (code layout,
shape check) can consume without re-rendering anything.

Everything in this repository lives under `part-b/`; the root `LICENSE` and
`README.md` are untouched.

## What it does

- **Downsample** an image with Pillow (grayscale → grid), width capped by `max_w`
  (default **72**, the D8 golden scale: `demo/cat.png` → 72×36).
- **Mask**: each cell carries `fg` (foreground = must be occupied), `level`
  (density index) and `ch` (glyph). `fg=True` with `ch=" "` is legal — that is
  why the mask is exported separately.
- **Charset validation**: one glyph = one printable single-column ASCII character
  (`0x20`–`0x7E`); Tab / full-width / CJK / emoji raise `ValueError`.
- **Slogans**: printable-ASCII text only, word-wrapped to `max_w`, at most
  `MAX_TEXT_CHARS = 200` characters. Empty / too long / non-ASCII input raises
  `ValueError` with the offending index (`slogan[3] = '中' (U+4E2D)` …).
- **Sidecar**: `export_meta()` writes `<out>.meta.json`; `load_meta()` reads and
  validates it.

## Interface

```python
build_grid(src, charset=" .:-=+*#%@", max_w=72,
           threshold=128.0, invert=False, cell_aspect=2.0) -> PixelGrid
```

| parameter | meaning |
|---|---|
| `src` | image path (PNG/JPG/… any Pillow format) **or** slogan text; anything that is not an existing file path is treated as text |
| `charset` | density ramp, sparse → dense, first char is treated as blank (default `" .:-=+*#%@"`) |
| `max_w` | width cap, positive int, **default 72** |
| `threshold` | grayscale 0–255 separating foreground from background (bright ≥ threshold = fg) |
| `invert` | flip fg/bg (dark subject on a light background) |
| `cell_aspect` | terminal cell height/width ratio, default 2.0 |

`PixelGrid` exposes `width`, `height`, `cells`, `charset`, `source`, `threshold`,
`max_w`, plus `at(x, y)`, `row(y)`, `render()`, `grid_rows`, `fg_rows`, `fg_mask()`,
`fg_count` and `density`.

## Quick start

```bash
cd part-b
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests -q          # 38 passed
./.venv/bin/python tests/test_grid.py          # same 38 tests, no pytest needed
```

Any Python ≥ 3.10 that can `import PIL` works. (Known pitfall on macOS: a `.venv`
copied from another machine can hang on `import PIL` inside dyld; use the system
interpreter or rebuild the venv.)

## Slogan rules

- printable ASCII + `\n` only; everything else raises `ValueError` naming the
  offset and code point (this avoids rendering CJK/emoji as solid `.notdef` blocks);
- longer than `MAX_TEXT_CHARS = 200` → `ValueError` (write it to a file and pass the path);
- wrapped to `max_w` by words; a single word wider than the whole line is split;
- long text shrinks the font / grows the canvas instead of collapsing to a
  1-row empty grid (79 chars → 70×20, fg=304 at `max_w=72`).

## Sidecar (`<out>.meta.json`)

`export_meta(grid, out=None, *, origin=None, extra=None) -> dict`

| key | meaning |
|---|---|
| `schema_version` | sidecar version (currently 1) |
| `cols` / `rows` / `size` | columns / rows / `[cols, rows]` |
| `max_w` | width cap used at build time (`null` when unknown) |
| `grid_rows` | per-row glyphs (background cells are spaces) |
| `fg_rows` | foreground mask, `"1"` = foreground, `"0"` = background |
| `fg_count` / `density` | foreground cell count / foreground ratio |

Both row forms are stored because a foreground cell at `level 0` carries a blank
glyph and is indistinguishable from background in `grid_rows` alone. Never
re-derive the mask from `render()`.

`load_meta()` validates consistency and upgrades older sidecars (missing `max_w`
→ `null`, missing `size` → `[cols, rows]`).

## Compatibility with a 6-field `PixelGrid`

B's `PixelGrid` is a **superset** of the 6-field version the integration owner may
freeze: `max_w` is the only extra field and it sits last with default `None`, so
5-/6-positional construction still works. `export_meta()` does **structural**
(duck-typed) validation — `width`, `height`, `cells`, `charset`, each cell with
`fg` / `level` / `ch` — so a 6-field object is accepted and `max_w` is read via
`getattr(grid, "max_w", None)`. Missing attributes are reported by name.

## Samples

`part-b/samples/` contains three fixed samples rendered at `max_w=72` and `48`
(regenerate with `python3 samples/make_samples.py`, idempotent):

| group | source | max_w | cols × rows | fg_count | density |
|---|---|---|---|---|---|
| cat | `demo/cat.png` (560×560 L) | 72 | 72 × 36 | 1126 | 0.4344 |
| cat | same | 48 | 48 × 24 | 525 | 0.4557 |
| logo | `samples/logo.png` (512×512 L) | 72 | 72 × 36 | 581 | 0.2242 |
| logo | same | 48 | 48 × 24 | 194 | 0.1684 |
| slogan | text `"ASCII"` | 72 | 72 × 13 | 280 | 0.2991 |
| slogan | same | 48 | 48 × 8 | 128 | 0.3333 |

Each grid has a matching `.meta.json` sidecar. `samples/README.md` documents the
conventions (white art on black background, origin supplied by the layout stage).

## Tests

38 tests, all passing (`pytest -q tests`):

```
38 passed in 0.21s
```

They cover the image path (size cap, fg/bg marks, invert, aspect), charset
validation (printable ASCII, Tab/CJK/emoji rejection, de-duplication), mask
export (`fg=True` with blank glyph), the meta round-trip, duck-typed export, and
the slogan contract (short, 79-char, 300-char, blank, CJK/emoji/Tab, long-word split).
