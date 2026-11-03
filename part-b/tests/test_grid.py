"""Tests for B's module: build_grid (image / slogan → PixelGrid).

pytest-compatible; also runnable standalone (no pytest needed):
    python3 tests/test_grid.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from ascii_art_executable.grid import (  # noqa: E402
    DEFAULT_CHARSET,
    MAX_TEXT_CHARS,
    META_SCHEMA_VERSION,
    build_grid,
    export_meta,
    load_meta,
)
from shared.types import PixelGrid  # noqa: E402


# ---------------------------------------------------------------- helpers --

def _circle(path: Path, size: int = 240) -> Path:
    """White filled circle on black — bright foreground, dark background."""
    im = Image.new("L", (size, size), 0)
    ImageDraw.Draw(im).ellipse([size * 0.12, size * 0.12, size * 0.88, size * 0.88], fill=255)
    im.save(path)
    return path


def _white_rect(path: Path, w: int = 240, h: int = 120) -> Path:
    im = Image.new("L", (w, h), 255)
    im.save(path)
    return path


# ------------------------------------------------------------------ tests --

def test_returns_pixelgrid_with_consistent_shape(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=48)
    assert isinstance(g, PixelGrid)
    assert g.width <= 48 and g.height >= 1
    assert len(g.cells) == g.width * g.height
    assert len(g.render().splitlines()) == g.height


def test_width_capped_by_max_w(tmp_path: Path) -> None:
    p = _circle(tmp_path / "big.png", size=1200)
    assert build_grid(p, max_w=60).width == 60
    assert build_grid(p, max_w=20).width == 20


def test_fg_bg_marks_clear(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")  # white circle on black
    g = build_grid(p, max_w=48)
    cx, cy = g.width // 2, g.height // 2
    assert g.at(cx, cy).fg is True   # circle centre → 前景
    assert g.at(0, 0).fg is False    # corner → 背景
    assert 0.05 < g.density < 0.6


def test_rows_have_uniform_length(tmp_path: Path) -> None:
    g = build_grid(_circle(tmp_path / "c.png"), max_w=40)
    for y in range(g.height):
        assert len(g.row(y)) == g.width


def test_custom_charset_only_uses_given_chars(tmp_path: Path) -> None:
    g = build_grid(_circle(tmp_path / "c.png"), charset="X#", max_w=40)
    assert g.charset == "X#"
    assert set(g.render().replace("\n", "")) <= set("X# ")


def test_default_charset_is_sparse_to_dense() -> None:
    assert DEFAULT_CHARSET[0] == " " and len(DEFAULT_CHARSET) == 10


def test_invert_flips_fg_bg(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    normal = build_grid(p, max_w=40)
    inv = build_grid(p, max_w=40, invert=True)
    cx, cy = normal.width // 2, normal.height // 2
    assert normal.at(cx, cy).fg is True and inv.at(cx, cy).fg is False
    assert normal.at(0, 0).fg is False and inv.at(0, 0).fg is True


def test_slogan_text_becomes_grid(tmp_path: Path) -> None:
    g = build_grid("HELLO", max_w=60)
    assert isinstance(g, PixelGrid)
    assert g.width <= 60
    assert g.density > 0.02
    # letters occupy the vertical middle band — some fg must sit there
    mid = g.height // 2
    assert any(g.at(x, mid).fg for x in range(g.width))


def test_small_slogan_still_produces_fg() -> None:
    g = build_grid("A", max_w=20)
    assert g.density > 0.0


def test_deterministic_output(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    assert build_grid(p, max_w=40).render() == build_grid(p, max_w=40).render()


def test_cell_aspect_squashes_height(tmp_path: Path) -> None:
    # 240x120 (2:1) image at max_w=80 → 80 wide, round(80*120/240/2) = 20 tall
    g = build_grid(_white_rect(tmp_path / "r.png"), max_w=80)
    assert (g.width, g.height) == (80, 20)
    g1 = build_grid(_white_rect(tmp_path / "r2.png"), max_w=80, cell_aspect=1.0)
    assert (g1.width, g1.height) == (80, 40)


def test_image_smaller_than_max_w_is_not_upscaled(tmp_path: Path) -> None:
    g = build_grid(_white_rect(tmp_path / "tiny.png", w=30, h=10), max_w=80)
    assert g.width == 30


def test_empty_slogan_raises() -> None:
    try:
        build_grid("   ")
    except ValueError:
        return
    raise AssertionError("expected ValueError for blank slogan")


# --------------------------------------------- charset validation (PM §3 #5) --

def test_charset_accepts_printable_ascii(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    for cs in (" .:-=+*#%@", "X#", " @", "!~"):
        g = build_grid(p, charset=cs, max_w=20)
        assert g.charset == cs
        assert set(g.render().replace("\n", "")) <= set(cs + " ")


def test_charset_rejects_tab(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    try:
        build_grid(p, charset=" .\t#", max_w=20)
    except ValueError as exc:
        msg = str(exc)
        assert "charset[2]" in msg and "U+0009" in msg, msg
        return
    raise AssertionError("expected ValueError for a Tab in charset")


def test_charset_rejects_cjk_and_emoji(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    cases = ((" .中", "U+4E2D"), (" .＃", "U+FF03"), (" .🐟", "U+1F41F"))
    for cs, needle in cases:
        try:
            build_grid(p, charset=cs, max_w=20)
        except ValueError as exc:
            assert needle in str(exc), str(exc)
        else:
            raise AssertionError(f"expected ValueError for charset {cs!r}")


def test_charset_rejects_empty_and_non_str(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    for bad in ("", None, 5, b" #"):
        try:
            build_grid(p, charset=bad, max_w=20)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for charset {bad!r}")


def test_charset_duplicates_are_deduped(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, charset="###", max_w=20)
    assert g.charset == "#"
    assert set(g.render().replace("\n", "")) <= set("# ")


def test_max_w_must_be_positive_int(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    for bad in (0, -3, "48", 4.5, True, None):
        try:
            build_grid(p, max_w=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for max_w={bad!r}")
    assert build_grid(p, max_w=48.0).width == 48   # integral float still fine


# --------------------------- foreground mask + sidecar (PM §0 决议 3, §3 #4) --

def test_all_background_image_has_empty_mask(tmp_path: Path) -> None:
    p = tmp_path / "black.png"
    Image.new("L", (40, 20), 0).save(p)
    g = build_grid(p, max_w=10)
    assert g.fg_count == 0 and g.density == 0.0
    assert all(row == "0" * g.width for row in g.fg_rows)
    assert g.grid_rows == tuple(" " * g.width for _ in range(g.height))
    meta = export_meta(g)
    assert meta["fg_count"] == 0 and meta["density"] == 0.0


def test_all_foreground_image_has_full_mask(tmp_path: Path) -> None:
    p = _white_rect(tmp_path / "w.png", w=40, h=20)
    g = build_grid(p, max_w=10)
    assert g.fg_count == g.width * g.height
    assert g.density == 1.0
    assert all(row == "1" * g.width for row in g.fg_rows)


def test_mask_keeps_foreground_with_blank_glyph(tmp_path: Path) -> None:
    # gray 8 with threshold 4 → fg=True, level 0 → ch == " ": the glyph rows
    # look entirely blank, only the mask knows these cells must be occupied.
    p = tmp_path / "dark.png"
    Image.new("L", (20, 20), 8).save(p)
    g = build_grid(p, charset=" .#", max_w=10, threshold=4)
    invisible = [c for c in g.cells if c.fg and c.ch == " "]
    assert invisible, "fixture should produce fg cells with a blank glyph"
    assert all(ch == " " for row in g.grid_rows for ch in row)  # glyphs are lost
    assert sum(row.count("1") for row in g.fg_rows) == g.fg_count
    mask = g.fg_mask()
    assert sum(sum(row) for row in mask) == g.fg_count
    assert all(isinstance(v, bool) for row in mask for v in row)


def test_meta_roundtrip(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=24)
    out = tmp_path / "cat.meta.json"
    written = export_meta(g, out)
    assert out.is_file()
    loaded = load_meta(out)
    assert loaded == written
    assert loaded["cols"] == g.width and loaded["rows"] == g.height
    assert loaded["max_w"] == 24
    assert loaded["grid_rows"] == list(g.grid_rows)
    assert loaded["fg_rows"] == list(g.fg_rows)
    assert loaded["fg_count"] == g.fg_count
    assert abs(loaded["density"] - g.density) < 1e-12
    assert loaded["schema_version"] == META_SCHEMA_VERSION
    assert isinstance(loaded["grid_rows"][0], str)


def test_meta_origin_and_extra_passthrough(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=16)
    meta = export_meta(g, origin=(2, 1), extra={"code_spans": []})
    assert meta["origin"] == [2, 1]
    assert meta["code_spans"] == []
    try:
        export_meta(g, origin=(0, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a 0-based origin")


def test_meta_rejects_inconsistent_sidecar(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=16)
    out = tmp_path / "bad.meta.json"
    meta = export_meta(g)
    meta["fg_count"] = 0            # disagrees with fg_rows
    out.write_text(json.dumps(meta), encoding="utf-8")
    try:
        load_meta(out)
    except ValueError as exc:
        assert "fg_count" in str(exc), str(exc)
    else:
        raise AssertionError("expected ValueError for inconsistent fg_count")


def test_cat_fixture_numbers_are_stable() -> None:
    cat = Path(__file__).resolve().parents[1] / "demo" / "cat.png"
    g = build_grid(cat, max_w=72)
    assert (g.width, g.height) == (72, 36)          # PM §0: 72×36 golden
    assert g.fg_count == 1126
    assert abs(g.density - 1126 / (72 * 36)) < 1e-12


# ------------------------------------------------- default max_w (PM §9 B①) --

def test_default_max_w_is_72() -> None:
    cat = Path(__file__).resolve().parents[1] / "demo" / "cat.png"
    g = build_grid(cat)                              # no max_w on purpose
    assert (g.width, g.height) == (72, 36)
    assert g.fg_count == 1126
    assert g.max_w == 72
    assert export_meta(g)["max_w"] == 72
    # an explicit (smaller) cap still wins
    assert build_grid(cat, max_w=48).width == 48


# ------------------------------------------------------ slogan text contract --

def test_slogan_short_text_is_ok() -> None:
    g = build_grid("ASCII", max_w=72)
    assert g.width <= 72 and g.height >= 2
    assert g.fg_count > 0
    assert g.source == "ASCII"


def test_slogan_79_chars_does_not_degenerate() -> None:
    # exactly 79 printable-ASCII chars, several words
    text = ("The quick brown fox jumps over the lazy dog and keeps running " * 2)[:79]
    assert len(text) == 79
    for max_w in (72, 48):
        g = build_grid(text, max_w=max_w)
        assert g.width <= max_w, (max_w, g.width)
        assert g.height >= 2, f"{max_w} wide -> only {g.height} row(s)"
        assert g.fg_count > 0, f"{max_w} wide -> empty art"


def test_slogan_over_max_chars_raises_value_error() -> None:
    try:
        build_grid("x" * (MAX_TEXT_CHARS + 1), max_w=72)
    except ValueError as exc:
        assert "too long" in str(exc)
    else:
        raise AssertionError("expected ValueError for over-long slogan")


def test_slogan_empty_and_blank_raise() -> None:
    for text in ("", "   ", "\n\n"):
        try:
            build_grid(text, max_w=40)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {text!r}")


def test_slogan_rejects_non_ascii() -> None:
    cases = (("中文", "U+4E2D"), ("ASCII 🐟", "U+1F41F"), ("a\tb", "U+0009"))
    for text, needle in cases:
        try:
            build_grid(text, max_w=72)
        except ValueError as exc:
            assert needle in str(exc), str(exc)
            assert "slogan[" in str(exc), str(exc)
        else:
            raise AssertionError(f"expected ValueError for {text!r}")


def test_slogan_long_word_is_hard_split() -> None:
    g = build_grid("X" * 120, max_w=72)
    assert g.width <= 72
    assert g.height >= 2
    assert g.fg_count > 0


# --------------------------------------- structural grid + sidecar (P0-2/P2) --

def _six_field_grid():
    """A PixelGrid look-alike WITHOUT max_w — the shape A may freeze."""
    cell = lambda x, y, fg, level, ch: SimpleNamespace(  # noqa: E731
        x=x, y=y, fg=fg, level=level, ch=ch)
    return SimpleNamespace(
        width=2, height=1, charset=" #", source="mock",
        cells=(cell(0, 0, True, 1, "#"), cell(1, 0, False, 0, " ")),
    )


def test_export_meta_accepts_six_field_grid() -> None:
    meta = export_meta(_six_field_grid())
    assert (meta["cols"], meta["rows"], meta["size"]) == (2, 1, [2, 1])
    assert meta["max_w"] is None          # absent on the 6-field variant
    assert meta["grid_rows"] == ["# "]
    assert meta["fg_rows"] == ["10"]
    assert meta["fg_count"] == 1 and meta["density"] == 0.5


def test_export_meta_reports_missing_attributes() -> None:
    try:
        export_meta(SimpleNamespace(width=2, height=1, charset=" #"))
    except ValueError as exc:
        assert "cells" in str(exc), str(exc)
    else:
        raise AssertionError("expected ValueError for a grid without cells")

    broken = SimpleNamespace(
        width=1, height=1, charset=" #",
        cells=(SimpleNamespace(x=0, y=0, ch="#"),),
    )
    try:
        export_meta(broken)
    except ValueError as exc:
        assert "fg" in str(exc) and "level" in str(exc), str(exc)
    else:
        raise AssertionError("expected ValueError for a cell without fg/level")


def test_meta_has_size_key_and_roundtrips(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=24)
    out = tmp_path / "c.meta.json"
    written = export_meta(g, out)
    assert written["size"] == [g.width, g.height]
    assert load_meta(out) == written


def test_load_meta_upgrades_legacy_sidecar(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=16)
    legacy = export_meta(g)
    legacy.pop("max_w")     # sidecar written before max_w was recorded
    legacy.pop("size")      # ... and before `size` existed
    out = tmp_path / "legacy.meta.json"
    out.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = load_meta(out)
    assert loaded["max_w"] is None
    assert loaded["size"] == [g.width, g.height]


def test_meta_rejects_size_mismatch(tmp_path: Path) -> None:
    p = _circle(tmp_path / "c.png")
    g = build_grid(p, max_w=16)
    meta = export_meta(g)
    meta["size"] = [g.width + 1, g.height]
    out = tmp_path / "bad-size.meta.json"
    out.write_text(json.dumps(meta), encoding="utf-8")
    try:
        load_meta(out)
    except ValueError as exc:
        assert "size" in str(exc), str(exc)
    else:
        raise AssertionError("expected ValueError for a size mismatch")


# ------------------------------------------------------------- standalone --

if __name__ == "__main__":
    import inspect
    import tempfile
    import traceback

    tmp = Path(tempfile.mkdtemp(prefix="grid-test-"))
    fns = [f for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    for fn in fns:
        try:
            takes_arg = len(inspect.signature(fn).parameters) > 0
            fn(tmp) if takes_arg else fn()
            print(f"PASS  {fn.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    raise SystemExit(1 if failures else 0)
