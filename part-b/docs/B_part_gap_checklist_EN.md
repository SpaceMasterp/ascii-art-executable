# Part B — Gap Audit and Pre-Upload Repository Check

> Read-only audit; no source file was modified. Scope: `ascii-art-executable_B` (B's
> implementation), `samples/` (B's sample assets), the kickoff-plan docx,
> `project-issues-for-PM.md`, `project_issues_narrative.md`, and
> `ascii-art-executable_BF/F_对接说明.md`.
> Test environment: `/tmp/b_venv` (Python 3.13.5 + Pillow 13.0.0 + pytest 9.2.0),
> **26 passed** at audit time.
> Note: the document list mentions `project-issues-narrative.md` (hyphenated); that file
> does **not** exist — only `project_issues_narrative.md` (underscored) is present, and the
> audit used it.
>
> **Update 2026-11-04: P0-1 (`max_w` default 72), P0-2 (slogan branch), P0-3 (duck-typed
> `export_meta`), P2 (sidecar `size`) and P1 (`.gitignore` `.DS_Store`) are fixed; tests went
> 26 → 38 all green. See §6 “Before / after”.**

---

## 1. Executive summary

1. **The functional surface is complete and passes G1**: `build_grid` + single-column charset
   validation + `fg_rows` mask + `export_meta/load_meta` + 3 fixed samples are all in place;
   26 tests green and runnable from any cwd (`cd /tmp && pytest <B>/tests` → 26 passed).
2. **The `max_w` default was not implemented**: the docs require 72 (PM §9 B①, PM:23's 72×36
   golden), the code still had `max_w: int = 80`. Without the argument the result was
   `width=80`, `meta["max_w"]=80` — the D8 call `build_grid(demo/cat.png)` would have missed the
   72×36 golden.
3. **The slogan branch had two reproducible defects**: (1) text of roughly ≥48 characters
   degenerated into a `72×2 / fg=0` empty grid (`README.md:44-45` still claimed
   “long slogans wrap automatically”); (2) text of ≥256 characters made
   `Path(src).is_file()` raise `OSError: [Errno 63] File name too long` instead of `ValueError`.
4. **The interface freeze had a hard conflict**: B's `PixelGrid` has 7 fields (extra `max_w`)
   plus 3 mask helpers; BF's has 6 fields but adds `ShapeReport`/`DetectionReport` — neither is a
   superset. Worse, `export_meta` used `isinstance(grid, PixelGrid)`, so passing a BF instance
   raised `ValueError: grid must be a PixelGrid, got PixelGrid`. Freezing either side breaks the
   other; the fields must be merged first.
5. **The repo was not a git repository** (no `.git`, 0 commits). `.gitignore` already excluded
   `.venv/` (40 MB), `__pycache__/`, `*.pyc`, `.pytest_cache/` but **missed `.DS_Store`**
   (the 6148 B file at the B root would have entered the first commit).

---

## 2. Requirement-by-requirement table

Status values: **met / partially met / missing / not B's responsibility**. “Action?” = does B
have to do anything.

| # | Requirement (quoted) | Source | Status | Evidence | Action? |
|---|---|---|---|---|---|
| 1 | `build_grid(src, charset, max_w) → PixelGrid`; image/slogan → character grid; “size-controlled, clear foreground/background marks” | docx §6(3) Table 2, row B | met | `grid.py:120-151`; `tests/test_grid.py:47` (`test_returns_pixelgrid_with_consistent_shape`) | no |
| 2 | `PixelGrid` “contains width, per-cell coordinates and foreground/background marks” | docx §6(2), paragraph 2 | met | `shared/types.py:25-32` (`GridCell`), `:43-54` (PixelGrid fields) | no |
| 3 | “Each cell maps to one character position in the source; foreground cells are marked must-occupy, background cells may stay blank” | docx §2(2), step 1 | met | `grid.py:173-180` (fg/level/ch assignment); `GridCell.fg/ch`; `test_fg_bg_marks_clear` (tests:62) | no |
| 4 | Skeleton-phase acceptance: “any PNG in → a **size-controlled** grid out, with foreground/background correctly separated” | docx §4(2), sentence 1 | partially met | Width is capped (`grid.py:165` `tw=min(g.width,max_w)`, `test_width_capped_by_max_w` tests:56); **height is unbounded**: a 50×2000 image at 72 → `50×1000` (measured); black-on-white art defaults to `density=0.797` (needs `invert`) | yes (P1: `max_h` + document it) |
| 5 | “Support custom charset and a resolution cap” | docx §5(1), row B | met | `charset` parameter + `validate_charset` (`grid.py:69-101`); `max_w` validated by `_validate_max_w` (`:103-117`) | no |
| 6 | “Add a single-column charset whitelist; keep the 13 tests green” | PM:201 (§9 B①); PM:96 (§3 #5: one cell = one character, printable ASCII only, no Tab/CRLF/full-width) | met | `test_charset_accepts_printable_ascii`, `_rejects_tab`, `_rejects_cjk_and_emoji`, `_rejects_empty_and_non_str`, `_duplicates_are_deduped` (tests:139-186) | no |
| 7 | “Confirm the `grid_rows`/`fg_rows` sidecar format and **`max_w` default 72**” | PM:201 | **fixed** (default 72) | Before: `max_w: int = 80`; after: `max_w: int = 72` (`grid.py:162`), `test_default_max_w_is_72` asserts cat → 72×36/1126 and `meta.max_w=72` | no |
| 8 | “13/13: all of B's grid tests pass … G1 criterion = `tests/test_grid.py` 13/13” | PM:22, PM:131 | met (now 26, 38 after the fixes) | The original 13 tests are untouched; new ones were appended; `pytest -q` → 26 passed at audit time (38 after fixes); same result from `/tmp` (cwd-independent) | no |
| 9 | “Tests must run as `python3 tests/xxx.py`” | PM:144 | met | `tests/test_grid.py:291-311` ships a standalone runner; `python3 tests/test_grid.py` → 26/26 | no |
| 10 | Sidecar must contain `grid_rows` (expected glyphs) and `fg_rows` (foreground mask); “storing only one loses whether a cell is foreground” | narrative:231,233; PM:95 | met | `export_meta` (`grid.py:321-378`) emitted 8 keys incl. both rows; `test_meta_roundtrip` (tests:236), `test_mask_keeps_foreground_with_blank_glyph` (tests:221) | no |
| 11 | Sidecar also needs `origin` / `size` / `code_spans` / `skeleton.lines` / `expected_stdout` / `source_sha256` | PM:16 (§0 resolution 3), PM:95, narrative:231 | **fixed** (`size` added) | After: 9 keys incl. `size: [cols, rows]` (`test_meta_has_size_key_and_roundtrips`); before: only `schema_version/cols/rows/max_w/grid_rows/fg_rows/fg_count/density`; `origin` is an optional argument (`grid.py:366-372`) but not auto-filled; the remaining keys belong to C/D/E | partly: B adds `size`, rest aligns with A |
| 12 | “Deliver 3 fixed samples before D3 (cat 72×36, logo, slogan) plus a size/density table” | PM:201 (§9 B②) | met | `samples/README.md:17-26` (six real rows); `samples/make_samples.py` renders 6 grids + 6 sidecars, byte-identical across two runs | no |
| 13 | “Keep the demo cat unchanged before D8; supply the second and third shape-check patterns for D12” | PM:201 (§9 B③); PM:23 | met | `test_cat_fixture_numbers_are_stable` (tests:283, locks 72×36/1126); `samples/logo.png` + `slogan.txt` serve as samples 2 and 3 | no |
| 14 | “Rows/columns 0-based, 1 cell = 1 character, printable ASCII only, no Tab/CRLF/full-width, no trailing rstrip” | PM:96; narrative:284 | partially met | Enforced for the charset (`grid.py:69-101`); **slogan input was unconstrained** (CJK — see #15); no rstrip (`types.py:55-59` concatenates glyphs) | yes (P1: define the slogan contract) |
| 15 | Slogan text branch is stable (non-ASCII / over-long / empty) — not listed in the docs, but B claimed “long slogans wrap” (`README.md:44-45`) | `ascii-art-executable_B/README.md:43-45` | **fixed** | After: 79 chars at 72 → 70×20/fg=304 (at 48 → 48×43/fg=342); 300 chars and CJK/emoji/Tab all raise `ValueError`; before: empty text → `ValueError` (tests:129), `"中文"` at 72 → 52×14 with `d=0.077` rendered as two rows of `@@@@` blocks (no CJK glyph → `.notdef`), `"HELLO "*8` (48 chars) → **72×2, fg=0**, length ≥256 → **`OSError [Errno 63]`** (`grid.py:138`) | **yes (P0/P1)** |
| 16 | Support PNG / JPG | docx §5(1) row B (“PNG/JPG…”), `README.md:39` | met (functionally) | Measured L/RGB/RGBA/P/1 modes and PNG/JPG all give `24×6 / fg=38`; `I;16` also works (fg=48; 16-bit saturates differently for the threshold); **tests only build L PNGs** — no JPG/RGBA case | yes (P1: add tests) |
| 17 | Transparent background semantics | not defined in the docs | missing (undefined) | RGBA transparent + white art → fg=102 (alpha ignored, equivalent to a black background); transparent + **black** art → `fg=0` (art disappears) | yes (P1: define + test) |
| 18 | Resolution-cap semantics: width only, or both width and height? | docx Table 2 row B (“size-controlled”); PM:96 | partially met | Code caps width only: `grid.py:165` `tw=min(g.width,max_w)`; height is derived as `th=round(tw*h/w/cell_aspect)` (`:166`) with no cap. The docs only say “size-controlled / width never exceeds the cap” (`README.md:40`), nothing about height | yes (P1: document + optional `max_h`) |
| 19 | `demo/` holds the pattern; demo script | docx §7; PM:145 (directory conventions) | met | `demo/cat.png` (560×560 L, 4192 B); generator `scripts/demo_grid.py` | no |
| 20 | `scripts/demo_grid.py` overwrites `demo/cat.png` | known hazard (checked this round) | partially met (harmless today) | `scripts/demo_grid.py:84` `make_cat(out / "cat.png")` → `im.save(path)` (`:76`); the regenerated file's sha256 `39e91a4f…` is **identical** to the committed `demo/cat.png`, so nothing changes today — but any drawing change would silently move the golden | yes (P1: `--out` / skip when present) |
| 21 | README should cover interface, sample table, dependency versions, how to run | docx §5(1) A (README owned by A) + B's own contract | **fixed** (README rewritten) | After: README documents the new API, 9 sidecar keys, the sample table and the interpreter pitfall, and drops `CanvasPlan`; before: `README.md:36-47` had interface/parameters/run steps but was **missing** `export_meta/load_meta/validate_charset/fg_rows` (`grid.py:321-426`), the sample table and the Pillow version, still claimed `CanvasPlan` was part of the freeze (`README.md:51`, removed by PM:14), and its venv instructions conflicted with PM:143 | yes (P1: update README) |
| 22 | v2 “one-click PNG → character art experience” | docx §5(1), last sentence of row B | missing | Only `scripts/demo_grid.py` (hard-coded cat); no entry point / CLI accepting an arbitrary PNG | yes (P2) |
| 23 | CLI subcommands `build/verify/detect` | docx §2(1); PM:203-205 (owner E) | not B's responsibility | B has no `cli.py`, as per the split; `samples/make_samples.py` is an offline script | no |
| 24 | Large-image / performance limits | not written (PM:96 only constrains skeleton runtime <2 s) | missing (undefined) | Measured cat@72 0.011 s, slogan@72 0.003 s; no `max_h`/`max_pixels`; a 50×2000 image yields 1000 rows | yes (P2: document limits) |
| 25 | F's consumption contract: `PixelGrid` row-major, single character, printable ASCII, **foreground from `cell.fg`** | `BF/F_对接说明.md:32-34`; `BF/ascii_art_executable/shapecheck.py:21-31,47-48` | met | `types.py:68-88` (`grid_rows`/`fg_rows`/`fg_mask`); `test_mask_keeps_foreground_with_blank_glyph` (tests:221) proves the mask stays correct when `fg=True, ch=" "` | no |
| 26 | B and BF `PixelGrid` agree (F already consumes the BF shape) | `BF/F_对接说明.md:38` (F only added reports, did not change PixelGrid) | **fixed** (duck typing; A still must merge fields) | After: `export_meta` accepts a 6-field equivalent (`test_export_meta_accepts_six_field_grid`) and names missing attributes (`test_export_meta_reports_missing_attributes`); before: B `[width,height,cells,charset,source,threshold,max_w]` (7) vs BF 6 fields without `max_w`; BF also has `ShapeReport/DetectionReport`; `export_meta(bf.PixelGrid(...))` → `ValueError: grid must be a PixelGrid, got PixelGrid` (the `isinstance` at `grid.py:348`) | **yes (P0: merge with A)** |
| 27 | Move the package into `ascii_art_executable/shared/`, keep a shim, “keep B's 13 tests” | PM:142 | not B's responsibility (A executes) | Still a top-level `shared/`; after the move B's `from shared.types import ...` must be updated | no (B validates) |
| 28 | Engineering baseline: `git init` before D2, `pyproject.toml` on D3–5 | PM:141, PM:5 | missing (A/E) | The B directory has no `.git`, no `pyproject.toml`, no `LICENSE` (verified with `ls`) | no (B not responsible, but it affects upload) |

---

## 3. Prioritised to-do list

### P0 (must land before the D3 interface freeze)

1. **Set the `max_w` default to 72**
   - Change `ascii_art_executable/grid.py:123` → `max_w: int = 72`; document “default 72” in `README.md:40`.
   - Test: `test_default_max_w_is_72` — `build_grid(demo/cat.png)` must give `(width, height) == (72, 36)`, `grid.max_w == 72`, `export_meta(grid)["max_w"] == 72`.
   - Basis: PM:201 (“`max_w` default 72”), PM:23 (“72×36 is the fixed D8 gate input”).

2. **Merge `PixelGrid` and relax `export_meta`'s type check**
   - With A: fold B's `max_w`, `grid_rows`, `fg_rows`, `fg_mask` (`shared/types.py:54,68,73,85`) into the frozen `types.py` while keeping F's `ShapeReport`/`DetectionReport` (BF version).
   - Change `grid.py:348` from `isinstance(grid, PixelGrid)` to a structural check (attributes `width/height/cells/charset`), so cross-package / cross-version instances are accepted.
   - Tests: `test_export_meta_accepts_structural_grid` (self-made dataclass with the same attributes exports fine); `test_types_has_pixelgrid_extras` (guards against losing fields during the merge).
   - Basis: PM:131/154 (G1 requires `types.py` to import and the three backends to mock-call without errors), `BF/F_对接说明.md:38`.

3. **Align the sidecar keys with A's schema**
   - Change: add `"size": [cols, rows]` in `export_meta` (`grid.py:350-359`); keep `origin` optional and supplied by C/D; document that “B owns the grid quartet”.
   - Test: `test_meta_has_size_key`.
   - Basis: PM:16 sidecar field table (`origin`/`size`/…), PM:95.

### P1 (before the D8 end-to-end gate)

4. **Long-slogan degeneration**: `_render_slogan_fit` (`grid.py:264-275`) should crop/scale to `max_w`; `_render_slogan` (`:196-214`) must not fall back to a canvas wider than `max_w`.
   Test: `test_long_slogan_keeps_foreground` (48- and 72-char cases, assert `height > 1 and fg_count > 0`).
5. **≥256-char `OSError`**: wrap `path.is_file()` (`grid.py:138`) in `try/except OSError` and fall through to the text branch.
   Test: `test_text_over_255_chars_is_treated_as_text`.
6. **Non-ASCII slogan policy**: not specified by the docs; pick one and document it in the README/`build_grid` docstring: (a) support only characters the font covers, or (b) detect `.notdef` (solid blocks) and raise `ValueError`.
   Test: `test_cjk_slogan_policy` (assert according to the chosen policy).
7. **Transparent-PNG semantics**: composite onto black via `alpha_composite` before `.convert("L")` (`grid.py:139`, matching the white-on-black cat/logo), or add a `bg=` parameter.
   Tests: `test_transparent_png_black_art`, `test_transparent_png_white_art`.
8. **Format/mode tests**: `test_jpeg_input`, `test_rgba_input`, `test_palette_png` (current tests only build L PNGs).
9. **Height cap**: add `max_h: int | None = 64` (or `max_cells`), enforced in `_grid_from_image` (`grid.py:165-166`); test `test_tall_image_height_capped` (50×2000@72 must give `height <= 64`).
10. **README update**: document the new API, the sample table (copy `samples/README.md:17-26`), the Pillow version and the `max_w` default; drop `CanvasPlan` from `README.md:51`; replace the venv instructions (`README.md:22-32`) with “any interpreter that can import PIL + known dyld pitfall”.
11. **demo_grid overwrite**: make `scripts/demo_grid.py:84` accept `--out` or skip when the file exists; add `test_make_cat_matches_golden` (`make_cat(tmp)` compared with `demo/cat.png` by sha256 — identical as measured today).

### P2 (optional / not v1 blockers)

12. **v2 “one-click PNG”**: add `scripts/ascii_preview.py <png> [--max-w 72] [--charset]`, or wait for E's CLI `preview` subcommand (docx §5(1), last sentence of row B).
13. **Add `.DS_Store` to `.gitignore`** and delete `ascii-art-executable_B/.DS_Store`.
14. **Document performance / large-image limits** in the README: cat@72 ≈ 11 ms; suggest “single image ≤ 4K per side, `max_w` ≤ 120”.
15. **Package-migration check**: after `shared/` moves into `ascii_art_executable/shared/`, re-run the 26 tests and `import ascii_art_executable`.

---

## 4. Pre-upload repository check (read-only, no git command executed)

### 4.1 Current state

| item | result |
|---|---|
| Is it a git repository? | **No**: `ls -d ascii-art-executable_B/.git` → `No such file or directory`; 0 commits |
| `.gitignore` content | `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` (4 lines, 41 B) |
| Coverage | ✅ `.venv` / `__pycache__` / `*.pyc` / `.pytest_cache`; ❌ **`.DS_Store` not covered**; ❌ `dist/`, `*.egg-info/` not covered (future packaging would leak) |
| Junk to keep out | `.venv` **40 MB**; `.pytest_cache` 16 KB; `__pycache__` 232 KB across 4 dirs (tests 152 KB / ascii_art_executable 44 KB / shared 28 KB / scripts 8 KB); `ascii-art-executable_B/.DS_Store` **6148 B**; root `.DS_Store` 10244 B |

### 4.2 Files that would enter the repo under the old `.gitignore` (10 files, 50,890 B ≈ 50 KB)

```
   6148  ./.DS_Store            <- should be excluded (.gitignore gap)
     41  ./.gitignore
   2489  ./README.md
    605  ./ascii_art_executable/__init__.py
  16894  ./ascii_art_executable/grid.py
   4192  ./demo/cat.png
   3675  ./scripts/demo_grid.py
    333  ./shared/__init__.py
   5720  ./shared/types.py
  10793  ./tests/test_grid.py
```

Without `.DS_Store`: **9 files / 44,742 B**, clean to publish.

### 4.3 Upload recommendations (plan only, not executed)

- **Repository root**: use `group project` rather than a B-only repository — the PM docs, `samples/` and B are reviewed together, and a B-only repo would break the `../ascii-art-executable_B/demo/cat.png` relative path in `samples/README.md`.
- **Include `samples/`**: **yes**. 16 files / 76 KB, small PNGs plus plain text; F/C depend on it as golden fixtures and `make_samples.py` is idempotent (identical sha256 across runs).
- **`ascii-art-executable_BF/`**: keep it out, or place it under `docs/reference/BF/` marked “reference implementation, not built”. Side-by-side copies make it unclear which one ships.
- **Directory name**: rename `ascii-art-executable_B/` to `ascii-art-executable/` (matches PM:141); otherwise point `packages = ["ascii_art_executable", "shared"]` at it in `pyproject.toml`.
- **Files to add**: `LICENSE` (MIT suggested for a course project), `.gitattributes` (`* text=auto`, `*.png binary`, `*.txt text eol=lf`, `*.meta.json text eol=lf`), a top-level `README.md` (overview + three commands + environment), `pyproject.toml` (A/E, PM:141), and a top-level `.gitignore` (B's entries + `.DS_Store` + `dist/` + `*.egg-info/`).
- **Suggested steps** (not executed):
  1. `git init` in `group project`;
  2. write the top-level `.gitignore` first (`.DS_Store`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `dist/`);
  3. `git add .gitignore README.md ascii-art-executable_B samples/ project-issues-for-PM.md project_issues_narrative.md` (explicit allow-list; avoid `git add .` picking up `.venv`);
  4. re-check with `git status --porcelain` — **no** `.venv/`, `__pycache__/`, `.DS_Store`; verify with `git check-ignore -v ascii-art-executable_B/.venv`;
  5. first commit → create the remote → push; tag D8/D12/D15 (PM:140).

---

## 5. One-paragraph status note for the PM

> Part B is functionally complete: `build_grid` + single-column charset validation + `fg_rows` mask + sidecar export/load + 3 fixed samples, 26 tests green and runnable without pytest, so the G1 criterion passes. Three things would still block D8: (1) `max_w` defaulted to 80 instead of 72; (2) long slogans (≳48 chars) degenerated into an empty grid and ≥256 chars raised `OSError`; (3) B's `PixelGrid` has an extra `max_w` while BF adds two F report structures — A must merge them, otherwise `export_meta` fails across packages. The repo has not been `git init`-ed and `.gitignore` misses `.DS_Store`.

---

## 6. Before / after (2026-11-04)

| item | before | after | evidence |
|---|---|---|---|
| `max_w` default | `= 80`; omitting it gave an 80-wide grid | `= 72`; omitting it gives cat → 72×36 / fg=1126 / d=0.4344 | function signature; `test_default_max_w_is_72` |
| 79-char sentence | `72×2`, `fg=0` (empty grid; at 48 only `48×1`) | `70×20`, `fg=304`, d=0.217 (at 48 → `48×43`, `fg=342`) | `test_slogan_79_chars_does_not_degenerate` |
| 300-char text | `OSError [Errno 63] File name too long` | `ValueError: slogan text is too long (300 chars > MAX_TEXT_CHARS=200)` | `test_slogan_over_max_chars_raises_value_error` |
| CJK / emoji / Tab | rendered as two rows of solid blocks | `ValueError` with `slogan[i]` and `U+4E2D` / `U+1F41F` / `U+0009` | `test_slogan_rejects_non_ascii` |
| `export_meta` type check | `isinstance(grid, PixelGrid)`; a BF instance raised “got PixelGrid” | structural check on `width/height/cells/charset` + per-cell `fg/level/ch`, naming whatever is missing; `max_w` via `getattr(..., None)` | `test_export_meta_accepts_six_field_grid`, `..._reports_missing_attributes` |
| sidecar keys | 8 keys, no `size` | 9 keys incl. `size: [cols, rows]`; `load_meta` validates `size` against `cols/rows` and back-fills older files | `test_meta_has_size_key_and_roundtrips`, `test_load_meta_upgrades_legacy_sidecar`, `test_meta_rejects_size_mismatch` |
| `.gitignore` | 4 lines, no `.DS_Store` | 6 lines with `.DS_Store` and `**/.DS_Store`; `git check-ignore -v .DS_Store` hits line 6 | measured in a scratch repo |
| tests | 26 | **38 all green** (12 added) | `pytest -q` → `38 passed in 0.19s` |
| sample numbers | cat 72×36/1126/0.4344 | **unchanged** (all six rows identical, reruns idempotent) | `samples/make_samples.py` output |

Files touched by the fixes: `ascii_art_executable/grid.py`, `tests/test_grid.py`, `README.md`, `.gitignore`, `samples/*.meta.json`, `samples/README.md`.
