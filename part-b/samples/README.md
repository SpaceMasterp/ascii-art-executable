# Sample Assets (Part B)

[中文](README.zh-CN.md)

Three **fixed samples** for part B, matching `project-issues-for-PM.md` §9 B②
("cat 72×36, logo, slogan + a size/density table") and the golden inputs for the
D8 (end-to-end) and D12 (shape) gates. Every grid here is rendered by
`build_grid` — none of it is hand-written — and every `.meta.json` is produced by
`export_meta` (B's slice of the sidecar).

## Conventions

- All three images are **white art on a black background** (same as
  `../demo/cat.png`), so the default `threshold=128` treats bright pixels as
  foreground — downstream does **not** need `invert=True`. With a black-on-white
  image, pass `invert=True`.
- One cell = one printable ASCII character; rows are not `rstrip`ped; coordinates
  are 0-based.
- Every cell with `"1"` in `fg_rows` must be occupied by a non-space character.
  Do **not** rebuild the mask from `grid_rows`: a foreground cell may land on
  `level 0` and render as a space (`fg=True, ch=" "`).

## Table (real script output)

| group | source | max_w | cols × rows | fg_count | density |
|---|---|---|---|---|---|
| cat | `../demo/cat.png` (560×560 L) | 72 | 72 × 36 | 1126 | 0.4344 |
| cat | same | 48 | 48 × 24 | 525 | 0.4557 |
| logo | `logo.png` (512×512 L, framed bold A) | 72 | 72 × 36 | 581 | 0.2242 |
| logo | same | 48 | 48 × 24 | 194 | 0.1684 |
| slogan | text `"ASCII"` (`slogan.txt`) | 72 | 72 × 13 | 280 | 0.2991 |
| slogan | same | 48 | 48 × 8 | 128 | 0.3333 |

> density = fg_count / (cols×rows), e.g. cat at 72 = 1126 / 2592 = 0.434414.

## How to regenerate

```bash
python3 samples/make_samples.py     # redraw logo.png, re-render 6 grids + 6 sidecars, print the table
```

- The script is **idempotent**: pure integer geometry + deterministic
  `build_grid`, no timestamps — two runs produce byte-identical files.
- It puts the project root on `sys.path` itself, so it can run from any directory;
  it needs an interpreter that can `import PIL`.
- The slogan goes through the text branch (`_render_slogan` picks the largest
  font that fits, then wraps); `"ASCII"` stays on one line at 72/48, so it fills
  the width cap.
- Slogan fonts differ across machines; `verify` / `check_shape` should trust this
  snapshot rather than re-rendering.

## Files

| file | description |
|---|---|
| `logo.png` | 512×512 grayscale: 48 px symmetric margin, 20 px frame, ~39 px polygon "A" (flat feet, no anti-aliasing) |
| `slogan.txt` | fixed slogan: `ASCII` (with trailing newline) |
| `make_samples.py` | reproducible script (draw + render + write sidecars + print table) |
| `grid_{cat,logo,slogan}_{72,48}.txt` | plain-text grid: `rows` lines of `cols` characters |
| `grid_{cat,logo,slogan}_{72,48}.meta.json` | sidecar: `schema_version / cols / rows / size / max_w / grid_rows / fg_rows / fg_count / density` (`size` = `[cols, rows]`, 9 keys on B's side) |

## Notes for consumers

- **Shape check (F)**: feed the `PixelGrid` directly, or rebuild the mask from
  `grid_rows` + `fg_rows` when only files are available. `origin` is supplied by
  the layout stage (C/D) and is not part of this directory.
- **Backends (C/D)**: cells with `"1"` in `fg_rows` must receive a non-space
  character; cells covered by `code_spans` must be recorded in the sidecar.
- **Verify (E)**: `export_meta` writes the 9 keys that are B's half of the
  sidecar; the remaining keys (`origin` / `code_spans` / `skeleton.lines` /
  `expected_stdout` / `source_sha256`) are filled by C/D/E.
- Sidecars since v1.1 carry `size: [cols, rows]`; `load_meta` fills it in
  automatically for older files.

## Scale warning (do not mix)

- The **BF demo** uses `max_w=48` → `48×24`, `525` foreground cells.
- The **PM acceptance** for the cat uses `max_w=72` → `72×36`, `1126` foreground cells.
- Same cat, different scale: cell counts, densities and shape thresholds are not interchangeable.
