"""Regenerate the fixed sample assets for B's pattern-input module.

Owner: B (图案输入与字符画).  These samples are the "3 组固定样例" required by
``project-issues-for-PM.md`` §9 B② (cat 72×36 / logo / slogan + 尺寸密度表) and
they are the golden inputs for the D8 / D12 gates.

What this script writes (all next to this file):

- ``logo.png``            hard-edged 512×512 letter mark, white on black
- ``slogan.txt``          the fixed slogan string (text-input branch)
- ``grid_<group>_<w>.txt`` per-row character grids rendered by B's ``build_grid``
- ``grid_<group>_<w>.meta.json`` the B sidecar slice from ``export_meta``

Groups: ``cat`` (B's demo/cat.png), ``logo`` (this folder), ``slogan`` (text).
Widths: 72 (PM acceptance scale) and 48 (BF demo scale).

Idempotent: drawing is pure integer geometry, ``build_grid`` is deterministic,
and no timestamps are written — running twice produces byte-identical files.

Usage:
    python3 samples/make_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B_DIR = ROOT / "ascii-art-executable_B"
if str(B_DIR) not in sys.path:
    sys.path.insert(0, str(B_DIR))

from PIL import Image, ImageDraw  # noqa: E402

from ascii_art_executable.grid import build_grid, export_meta  # noqa: E402

HERE = Path(__file__).resolve().parent
CAT = B_DIR / "demo" / "cat.png"
LOGO = HERE / "logo.png"
SLOGAN_TXT = HERE / "slogan.txt"
SLOGAN = "ASCII"

WIDTHS = (72, 48)
SIZE = 512          # logo canvas, square
MARGIN = 48         # symmetric blank border (background cells in the grid)
FRAME = 20          # frame bar thickness, ~2.8 cells at max_w=72
HALF_TOP = 19       # letter half-width at the apex, ~5 cells at max_w=72
HALF_FOOT = 20      # letter half-width at the baseline


# ---------------------------------------------------------------------------
# logo: pure integer geometry, no anti-aliasing, white-on-black
# ---------------------------------------------------------------------------

def make_logo(path: Path = LOGO) -> Path:
    """Draw a framed bold "A" mark: white ink on black, hard pixel edges.

    White-on-black matches ``demo/cat.png`` so every sample can be fed to
    ``build_grid`` with the default threshold (bright == foreground, no
    ``invert``). Geometry is integer-only and vertically symmetric about
    ``SIZE // 2``; PIL's ImageDraw does not anti-alias, so every edge is sharp.
    """
    im = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(im)

    # Outer frame, inset by MARGIN on all four sides → symmetric blank border.
    d.rectangle([MARGIN, MARGIN, SIZE - MARGIN - 1, SIZE - MARGIN - 1],
                outline=255, width=FRAME)

    # Bold "A": two flat-bottomed legs (polygons, not lines — a flat cap at the
    # baseline keeps the feet solid instead of leaving anti-aliased specks one
    # cell below the leg) plus a crossbar.
    apex_y, base_y = 150, 372
    left_cx, right_cx = 160, SIZE - 160
    for foot_cx in (left_cx, right_cx):
        d.polygon([(SIZE // 2 - HALF_TOP, apex_y),
                   (SIZE // 2 + HALF_TOP, apex_y),
                   (foot_cx + HALF_FOOT, base_y),
                   (foot_cx - HALF_FOOT, base_y)], fill=255)
    d.rectangle([196, 296, 312, 324], fill=255)

    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def groups() -> list[tuple[str, object]]:
    """(group name, build_grid src) — image path or slogan text."""
    return [("cat", CAT), ("logo", LOGO), ("slogan", SLOGAN)]


def render_all() -> list[dict]:
    rows: list[dict] = []
    for name, src in groups():
        for max_w in WIDTHS:
            grid = build_grid(src, max_w=max_w)
            stem = HERE / f"grid_{name}_{max_w}"
            stem.with_suffix(".txt").write_text(
                grid.render() + "\n", encoding="utf-8")
            export_meta(grid, stem.with_suffix(".meta.json"))
            rows.append({
                "group": name,
                "src": str(src) if not isinstance(src, str) else f"text:{src!r}",
                "max_w": max_w,
                "cols": grid.width,
                "rows": grid.height,
                "fg": grid.fg_count,
                "density": grid.density,
            })
    return rows


def main() -> int:
    SLOGAN_TXT.write_text(SLOGAN + "\n", encoding="utf-8")
    make_logo()
    rows = render_all()

    print(f"# {LOGO.name}: {SIZE}x{SIZE} L, margin={MARGIN}, frame={FRAME}, "
          f"letter half-width {HALF_TOP}/{HALF_FOOT}")
    print(f"# {SLOGAN_TXT.name}: {SLOGAN!r}")
    print()
    header = f"{'group':7} {'max_w':>5}  {'cols x rows':>11}  {'fg_count':>8}  density"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['group']:7} {r['max_w']:>5}  "
              f"{str(r['cols']) + ' x ' + str(r['rows']):>11}  "
              f"{r['fg']:>8}  {r['density']:.4f}")
    print()
    print(f"wrote {len(rows) * 2 + 3} files in {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
