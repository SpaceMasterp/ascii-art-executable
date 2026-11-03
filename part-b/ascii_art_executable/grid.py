"""B's module: image / slogan → character grid (图案输入与字符画).

Contract (启动方案 §六·三, owner B):

    build_grid(src, charset, max_w, max_h) -> PixelGrid

- ``src``     : image file path (PNG/JPG/…) **or** slogan text (anything that is
                not an existing file path is treated as text). Slogan text must
                be printable ASCII (``0x20``-``0x7E`` plus newlines), at most
                ``MAX_TEXT_CHARS`` characters, and it is word-wrapped to
                ``max_w``; CJK/emoji/Tab raise ``ValueError`` naming the offset.
- ``charset`` : density ramp, sparse → dense; first char is treated as blank.
                Every glyph must be printable ASCII ``0x20``-``0x7E`` and one
                column wide; duplicates are de-duplicated. Tab, CR/LF,
                full-width, CJK and emoji raise ``ValueError``.
- ``max_w``   : resolution cap (positive int, **default 72**) — the grid width
                never exceeds it (分辨率上限); other values raise ``ValueError``.
- ``max_h``   : optional height cap (positive int or ``None``, default ``None``).
                With both caps set the image shrinks by the tighter ratio, so
                width ≤ ``max_w`` and height ≤ ``max_h``.

Backward-compatible extras (defaults keep the contract behaviour):
- ``threshold``   : gray level 0-255 splitting 前景 from 背景; bright ≥ threshold
                    is foreground by default.
- ``invert``      : flip the fg/bg decision (dark subject on a light background).
- ``cell_aspect`` : terminal character cells are ~2x taller than wide; dividing
                    the target height by this keeps the rendered art from
                    looking squashed. Default 2.0.

Alpha semantics: an image whose alpha channel actually has transparency
(any pixel with ``alpha < 128``) uses alpha as the shape mask — transparent
pixels are background regardless of their RGB value and ``invert`` is ignored
for them; opaque pixels are foreground and their ramp level is clamped to ≥ 1 so
dark artwork still shows a glyph. Fully opaque RGBA images keep the luminance
behaviour.

Sidecar (B's slice, see :func:`export_meta`): ``grid_rows`` **and** ``fg_rows``
(plus ``cols`` / ``rows`` / ``max_w`` / ``fg_count`` / ``density``). Both row
forms are required because a foreground cell may carry a blank glyph
(``level == 0``), which makes it indistinguishable from background in
``grid_rows`` alone.

Skeleton-phase acceptance (启动方案 §四·二):
- arbitrary PNG in → size-controlled grid out, fg/bg marks clear, deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from shared.types import GridCell, PixelGrid

DEFAULT_CHARSET = " .:-=+*#%@"  # sparse → dense, index 0 = blank

# Printable ASCII is the only charset the frozen contract allows: one cell is one
# source character, and the backends count monospace columns.
_CHARSET_MIN, _CHARSET_MAX = 0x20, 0x7E

#: Version of B's sidecar slice (see :func:`export_meta`); bump on breaking changes.
META_SCHEMA_VERSION = 1

_META_REQUIRED = ("schema_version", "cols", "rows", "grid_rows",
                  "fg_rows", "fg_count", "density")

#: Slogan text longer than this must come from a file; also keeps
#: ``Path(src).is_file()`` away from the OS ``ENAMETOOLONG`` limit (255 bytes).
MAX_TEXT_CHARS = 200

_MIN_FONT = 6  # smallest font size used when wrapping long slogans

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   # macOS
    "/System/Library/Fonts/Helvetica.ttc",                  # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",                         # Windows
)


# ---------------------------------------------------------------------------
# input validation (frozen contract: PM §3 #5, §9 B①)
# ---------------------------------------------------------------------------

def validate_charset(charset: "str | None") -> str:
    """Return ``charset`` normalised for use as a density ramp.

    Every glyph must be a printable, single-column ASCII character
    (``0x20``-``0x7E``); Tab, CR/LF, full-width, CJK and emoji are rejected
    because one grid cell must map to exactly one source column
    (``project-issues-for-PM.md`` §3 #5). Duplicates are removed keeping the
    first occurrence, so the level → glyph mapping stays deterministic.

    Raises ``ValueError`` naming the offending character and its index.
    """
    if not isinstance(charset, str):
        raise ValueError(
            f"charset must be a str, got {type(charset).__name__}")
    if not charset:
        raise ValueError("charset must not be empty")

    for i, ch in enumerate(charset):
        code = ord(ch)
        if code < _CHARSET_MIN or code > _CHARSET_MAX:
            raise ValueError(
                f"charset[{i}] = {ch!r} (U+{code:04X}) is not a printable "
                f"single-column ASCII character; allowed range is "
                f"0x20-0x7E (Tab, CR/LF, full-width, CJK and emoji are "
                f"rejected)")

    # dict preserves insertion order; duplicates would otherwise give two levels
    # the same glyph and silently shrink the usable ramp.
    normalised = "".join(dict.fromkeys(charset))
    if not normalised:
        raise ValueError("charset must not be empty after de-duplication")
    return normalised


def _validate_max_w(max_w, *, name: str = "max_w") -> int:
    """Return the cap as a positive int, else raise ``ValueError``."""
    if isinstance(max_w, bool) or not isinstance(max_w, (int, float)):
        raise ValueError(f"{name} must be a positive integer, got {max_w!r}")
    if isinstance(max_w, float):
        if not max_w.is_integer():
            raise ValueError(f"{name} must be a positive integer, got {max_w!r}")
        max_w = int(max_w)
    if max_w <= 0:
        raise ValueError(f"{name} must be >= 1, got {max_w}")
    return int(max_w)


def _validate_max_h(max_h) -> "int | None":
    """Return ``max_h`` as a positive int, or ``None`` meaning "unbounded"."""
    if max_h is None:
        return None
    return _validate_max_w(max_h, name="max_h")


def _validate_slogan(text: "str | None") -> str:
    """Validate slogan text before it reaches the renderer.

    Contract (PM §3 #5 / ``project_issues_narrative.md`` §5): one grid cell is
    one printable ASCII character, so non-ASCII text (CJK, emoji, full-width)
    is rejected instead of being rendered as ``.notdef`` tofu blocks. Text
    longer than :data:`MAX_TEXT_CHARS` must be passed as a file path, which also
    keeps ``Path(...).is_file()`` below the OS filename limit.
    """
    if not isinstance(text, str):
        raise ValueError(f"slogan must be a str, got {type(text).__name__}")
    if not text.strip():
        raise ValueError("slogan text is empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(
            f"slogan text is too long ({len(text)} chars > "
            f"MAX_TEXT_CHARS={MAX_TEXT_CHARS}); put it in a file and pass the "
            f"path instead")
    for i, ch in enumerate(text):
        code = ord(ch)
        if ch == "\n":
            continue
        if code < _CHARSET_MIN or code > _CHARSET_MAX:
            raise ValueError(
                f"slogan[{i}] = {ch!r} (U+{code:04X}) is not printable ASCII; "
                f"the grid contract allows one printable ASCII character per "
                f"cell (Tab, CR/LF, CJK, full-width and emoji are rejected)")
    return text


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_grid(
    src: "str | Path",
    charset: str = DEFAULT_CHARSET,
    max_w: int = 72,
    max_h: "int | None" = None,
    threshold: float = 128.0,
    invert: bool = False,
    cell_aspect: float = 2.0,
) -> PixelGrid:
    """Downsample an image or slogan into a fg/bg-marked character grid.

    ``max_w`` defaults to **72** (the D8 golden scale: ``demo/cat.png`` →
    72×36); ``max_h=None`` means "no height cap". When both caps are set the
    image is scaled down by the tighter ratio, so width ≤ ``max_w`` **and**
    height ≤ ``max_h``.

    Images with a real alpha channel use it as the shape mask: pixels with
    ``alpha < 128`` are background regardless of their RGB value (a black logo
    on a transparent canvas no longer disappears), and ``invert`` is ignored for
    those pixels. Fully opaque RGBA images keep the plain luminance behaviour.

    Raises ``ValueError`` for an empty/illegal charset (see
    :func:`validate_charset`), a non-positive ``max_w``/``max_h``, or blank /
    non-ASCII / over-long slogan text (see :func:`_validate_slogan`).
    """
    charset = validate_charset(charset)
    max_w = _validate_max_w(max_w)
    max_h = _validate_max_h(max_h)
    threshold = min(255.0, max(0.0, float(threshold)))

    # ``Path("A"*300).is_file()`` raises OSError(ENAMETOOLONG) on macOS; the text
    # branch below must never leak that as a non-ValueError exception.
    path = Path(src) if isinstance(src, (str, Path)) else None
    is_file = False
    if path is not None:
        try:
            is_file = path.is_file()
        except OSError:
            is_file = False

    if is_file:
        image, alpha = _open_image(path)
        source = str(path)
    else:
        text = _validate_slogan(src if isinstance(src, str) else str(src))
        image = _render_slogan(text, max_w)
        alpha = None
        source = text

    return _grid_from_image(image, charset, max_w, threshold, invert, cell_aspect,
                            source, alpha=alpha, max_h=max_h)


def _open_image(path: Path) -> "tuple[Image.Image, Image.Image | None]":
    """Return ``(grayscale, alpha_mask)``; ``alpha_mask`` is ``None`` if opaque.

    Pillow's ``convert("L")`` throws the alpha channel away, so a transparent
    canvas turns black and swallows dark artwork. When the file really carries
    transparency (some pixel with ``alpha < 128``) we keep the alpha channel and
    let it decide foreground/background; an opaque RGBA image falls back to the
    normal luminance threshold.
    """
    im = Image.open(path)
    alpha = None
    if "A" in im.getbands() or (im.mode == "P" and "transparency" in im.info):
        alpha = im.convert("RGBA").getchannel("A")
        if alpha.getextrema()[0] >= 128:  # fully opaque → not a shape mask
            alpha = None
    return im.convert("L"), alpha


# ---------------------------------------------------------------------------
# image → grid
# ---------------------------------------------------------------------------

def _grid_from_image(
    im: Image.Image,
    charset: str,
    max_w: int,
    threshold: float,
    invert: bool,
    cell_aspect: float,
    source: str,
    *,
    alpha: "Image.Image | None" = None,
    max_h: "int | None" = None,
) -> PixelGrid:
    g = im.convert("L")
    tw = min(g.width, max_w)
    th = max(1, round(tw * g.height / g.width / max(1.0, cell_aspect)))
    if max_h is not None and th > max_h:
        # Shrink by the tighter ratio: height hits the cap, width follows.
        th = max_h
        tw = max(1, min(tw, round(th * max(1.0, cell_aspect) * g.width / g.height)))
    if (tw, th) != (g.width, g.height):
        resample = Image.BOX if tw < g.width else Image.NEAREST
        g = g.resize((tw, th), resample)
        if alpha is not None:
            alpha = alpha.resize((tw, th), resample)

    n = len(charset)
    cells: list[GridCell] = []
    px = g.load()
    ap = alpha.load() if alpha is not None else None
    for y in range(th):
        for x in range(tw):
            v = px[x, y]
            if ap is not None:
                # Alpha is the shape mask: opaque = foreground, transparent =
                # background, luminance/invert do not get a vote. A dark glyph
                # still needs a visible ramp level, hence the max(1, level).
                fg = ap[x, y] >= 128
                level = 0 if n == 1 else min(n - 1, int(round(v / 255 * (n - 1))))
                if fg and n > 1:
                    level = max(1, level)
            else:
                fg = (v >= threshold) ^ bool(invert)
                level = 0 if n == 1 else min(n - 1, int(round(v / 255 * (n - 1))))
            ch = charset[level] if fg else " "
            cells.append(GridCell(x=x, y=y, fg=fg, level=level, ch=ch))

    return PixelGrid(
        width=tw,
        height=th,
        cells=tuple(cells),
        charset=charset,
        source=source,
        threshold=threshold,
        max_w=max_w,
    )


# ---------------------------------------------------------------------------
# slogan text → image (white text on black, so "bright = foreground" holds)
# ---------------------------------------------------------------------------

def _render_slogan(text: str, max_w: int) -> Image.Image:
    """Render ASCII slogan text white-on-black, wrapped to ``max_w`` pixels.

    Sizing rule (1 px ≈ 1 grid column):
    1. take the **largest** font size whose wrapped block fits the width cap and
       a height budget of ``max(24, max_w // 2)`` px, never splitting words;
    2. if the text is too long for that budget, relax the budget 4× and retry —
       a taller canvas is still far better than the old degenerate 1-row grid
       that downsampled to ``fg_count == 0``;
    3. last resort: smallest font with hard word splitting.
    """
    budget_w = int(max_w)
    budget_h = max(24, max_w // 2)

    for limit in (budget_h, budget_h * 4):
        for size in range(48, _MIN_FONT - 1, -1):
            font = _font_at(size)
            lines = _wrap_text(text, font, budget_w, allow_split=False)
            if lines is None:
                continue
            if _block_height(lines, font) <= limit:
                return _draw_lines(lines, font)

    font = _font_at(_MIN_FONT)
    lines = _wrap_text(text, font, budget_w, allow_split=True) or [text]
    return _draw_lines(lines, font)


def _font_at(size: int):
    for cand in _FONT_CANDIDATES:
        if Path(cand).exists():
            try:
                return ImageFont.truetype(cand, size)
            except OSError:
                continue
    return _default_font(size)


def _wrap_text(
    text: str, font, budget_w: float, *, allow_split: bool
) -> "list[str] | None":
    """Word-wrap ``text`` to ``budget_w`` pixels, measured with the real font.

    Explicit newlines force a break (blank lines are dropped). A word wider than
    the whole budget is only broken mid-word when ``allow_split`` is set;
    otherwise ``None`` is returned so the caller can try a smaller font.
    """
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    lines: list[str] = []

    def fits(s: str) -> bool:
        return probe.textlength(s, font=font) <= budget_w

    for block in text.split("\n"):
        words = block.split()
        if not words:
            continue
        cur = ""
        for word in words:
            if fits(word if not cur else cur + " " + word):
                cur = word if not cur else cur + " " + word
                continue
            if cur:
                lines.append(cur)
                cur = ""
            if fits(word):
                cur = word
                continue
            if not allow_split:
                return None
            chunk = ""
            for ch in word:
                if fits(chunk + ch):
                    chunk += ch
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            cur = chunk
        if cur:
            lines.append(cur)
    return lines or None


def _block_height(lines: list[str], font) -> int:
    """Height of a wrapped block in px, matching :func:`_draw_lines`."""
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bboxes = [probe.textbbox((0, 0), line, font=font) for line in lines]
    return max(b[3] - b[1] for b in bboxes) * len(lines)


def _draw_lines(lines: list[str], font) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bboxes = [probe.textbbox((0, 0), line, font=font) for line in lines]
    widths = [b[2] - b[0] for b in bboxes]
    line_h = max(b[3] - b[1] for b in bboxes)
    pad = max(2, int(line_h * 0.25))
    canvas = Image.new("L", (max(widths) + 2 * pad, line_h * len(lines) + 2 * pad), 0)
    d = ImageDraw.Draw(canvas)
    y = pad
    for line, b, w in zip(lines, bboxes, widths):
        d.text((pad + (max(widths) - w) // 2 - b[0], y - b[1]), line, font=font, fill=255)
        y += line_h
    return canvas


def _default_font(size: int) -> ImageFont.ImageFont:
    try:  # Pillow ≥ 10.1 can scale the bundled default font
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# sidecar <out>.meta.json — B's slice of the build contract
# ---------------------------------------------------------------------------

#: Attributes a PixelGrid-compatible object must expose (class identity is not
#: required: A's frozen 6-field type and B's 7-field superset both qualify).
_GRID_ATTRS = ("width", "height", "cells", "charset")
_CELL_ATTRS = ("fg", "level", "ch")


def _grid_rows_from(grid) -> "tuple[list[str], list[str]]":
    """Return ``(grid_rows, fg_rows)`` from any PixelGrid-shaped object.

    Structural (duck-typed) validation: missing attributes are reported by name,
    so feeding a 6-field ``PixelGrid`` (no ``max_w``) or an equivalent
    ``SimpleNamespace`` works, while a broken object gets a precise error.
    """
    missing = [name for name in _GRID_ATTRS if not hasattr(grid, name)]
    if missing:
        raise ValueError(
            "grid must be PixelGrid-compatible; missing attribute(s): "
            + ", ".join(missing))

    width, height = grid.width, grid.height
    if not (isinstance(width, int) and isinstance(height, int)
            and width > 0 and height > 0):
        raise ValueError(
            f"grid.width/grid.height must be positive ints, got {width!r} and "
            f"{height!r}")
    try:
        cells = tuple(grid.cells)
    except TypeError as exc:
        raise ValueError("grid.cells must be an iterable of grid cells") from exc
    if len(cells) != width * height:
        raise ValueError(
            f"grid.cells has {len(cells)} items, expected {width * height} "
            f"(cols × rows)")

    grid_rows: list[str] = []
    fg_rows: list[str] = []
    for y in range(height):
        glyphs: list[str] = []
        mask: list[str] = []
        for x in range(width):
            index = y * width + x
            cell = cells[index]
            absent = [name for name in _CELL_ATTRS if not hasattr(cell, name)]
            if absent:
                raise ValueError(
                    f"grid.cells[{index}] (x={x}, y={y}) missing attribute(s): "
                    + ", ".join(absent))
            ch = cell.ch
            if not isinstance(ch, str) or len(ch) != 1:
                raise ValueError(
                    f"grid.cells[{index}].ch must be a single character, "
                    f"got {ch!r}")
            glyphs.append(ch)
            mask.append("1" if cell.fg else "0")
        grid_rows.append("".join(glyphs))
        fg_rows.append("".join(mask))
    return grid_rows, fg_rows


def export_meta(
    grid: PixelGrid,
    out: "str | Path | None" = None,
    *,
    origin: "tuple[int, int] | None" = None,
    extra: Optional[dict] = None,
) -> dict:
    """Build (and optionally write) B's part of ``<out>.meta.json``.

    Why both ``grid_rows`` and ``fg_rows``: a foreground cell may carry a blank
    glyph (``level == 0``), so it looks exactly like a background cell in
    ``grid_rows``. Storing only one of them loses "is this cell foreground?"
    (``project_issues_narrative.md`` §4.3; ``project-issues-for-PM.md`` §3 #4).

    Args:
        grid: anything that *looks like* ``PixelGrid`` — ``width``, ``height``,
            ``cells`` and ``charset`` attributes, each cell exposing
            ``fg`` / ``level`` / ``ch``. Class identity is deliberately **not**
            required, so the 6-field variant frozen by A (no ``max_w``) and B's
            7-field superset are both accepted; ``max_w`` is read with
            ``getattr(..., None)``.
        out: sidecar path. When given, the dict is written as UTF-8 JSON
            (parent directories are created). ``None`` returns the dict only.
        origin: ``(line, col)`` of the pattern's top-left corner, **1-based**;
            owned by C/D and passed through untouched.
        extra: additional already-frozen sidecar keys (``code_spans``,
            ``skeleton.lines``, ``expected_stdout``, ``source_sha256`` …) merged
            on top; B does not interpret them.

    Returns:
        The sidecar dict, always (also when it was written to disk).
    """
    grid_rows, fg_rows = _grid_rows_from(grid)
    width, height = grid.width, grid.height
    fg_count = sum(row.count("1") for row in fg_rows)

    meta: dict = {
        "schema_version": META_SCHEMA_VERSION,
        "cols": width,
        "rows": height,
        "size": [width, height],
        "max_w": getattr(grid, "max_w", None),
        "grid_rows": grid_rows,
        "fg_rows": fg_rows,
        "fg_count": fg_count,
        "density": fg_count / (width * height),
    }

    if origin is not None:
        line, col = origin
        if int(line) < 1 or int(col) < 1:
            raise ValueError(
                f"origin must be 1-based (line, col), got {origin!r}")
        meta["origin"] = [int(line), int(col)]
    if extra:
        meta.update(extra)

    if out is not None:
        path = Path(out)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return meta


def load_meta(path: "str | Path") -> dict:
    """Read and sanity-check a sidecar written by :func:`export_meta`.

    Raises ``ValueError`` for unreadable files, invalid JSON, or a sidecar whose
    ``grid_rows`` / ``fg_rows`` / ``fg_count`` / ``density`` disagree.
    """
    p = Path(path)
    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read sidecar {p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"sidecar {p} is not valid JSON: {exc}") from exc
    _validate_meta(meta, str(p))
    return meta


def _validate_meta(meta, src: str = "<meta>") -> None:
    """Validate the B-owned fields of a sidecar dict (in place, no I/O)."""
    if not isinstance(meta, dict):
        raise ValueError(f"{src}: sidecar must be a dict, "
                         f"got {type(meta).__name__}")
    missing = [k for k in _META_REQUIRED if k not in meta]
    if missing:
        raise ValueError(f"{src}: missing sidecar keys {missing}")

    cols, rows = meta["cols"], meta["rows"]
    if not (isinstance(cols, int) and isinstance(rows, int)
            and cols > 0 and rows > 0):
        raise ValueError(f"{src}: cols/rows must be positive ints, "
                         f"got {cols!r}/{rows!r}")

    # Newer sidecars carry "size": [cols, rows]; older ones predate it (and the
    # optional "max_w"), so both are upgraded in place instead of failing.
    size = meta.get("size")
    if size is None:
        meta["size"] = [cols, rows]
    elif (not isinstance(size, (list, tuple)) or len(size) != 2
          or list(size) != [cols, rows]):
        raise ValueError(f"{src}: size={size!r} disagrees with "
                         f"cols/rows ({cols}x{rows})")

    if "max_w" not in meta:
        meta["max_w"] = None
    elif meta["max_w"] is not None and not isinstance(meta["max_w"], int):
        raise ValueError(f"{src}: max_w must be an int or null, "
                         f"got {meta['max_w']!r}")

    grid_rows, fg_rows = meta["grid_rows"], meta["fg_rows"]
    for name, value in (("grid_rows", grid_rows), ("fg_rows", fg_rows)):
        if not isinstance(value, list) or len(value) != rows:
            raise ValueError(f"{src}: {name} must be a list of {rows} rows")
        bad = [i for i, r in enumerate(value)
               if not isinstance(r, str) or len(r) != cols]
        if bad:
            raise ValueError(f"{src}: {name} rows {bad} are not strings of "
                             f"{cols} cells")

    for y, row in enumerate(grid_rows):
        if any(ord(c) < _CHARSET_MIN or ord(c) > _CHARSET_MAX for c in row):
            raise ValueError(f"{src}: grid_rows[{y}] must be printable ASCII")
    for y, row in enumerate(fg_rows):
        if set(row) - {"0", "1"}:
            raise ValueError(f"{src}: fg_rows[{y}] may only contain '0'/'1'")

    ones = sum(row.count("1") for row in fg_rows)
    if meta["fg_count"] != ones:
        raise ValueError(f"{src}: fg_count={meta['fg_count']} disagrees with "
                         f"fg_rows ({ones} foreground cells)")
    expected = ones / (cols * rows)
    if abs(float(meta["density"]) - expected) > 1e-9:
        raise ValueError(f"{src}: density={meta['density']} disagrees with "
                         f"fg_count/{cols}x{rows} ({expected})")
