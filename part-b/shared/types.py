"""Shared data structures for the ASCII Art Executable project.

Contract rules (from 启动方案 §六):
- Every cross-module object lives here; all members import from here, no private copies.
- Interfaces freeze in days 1-3. After the freeze, only backward-compatible
  additions are allowed; changing existing signatures is forbidden.

Ownership:
- ``PixelGrid``  — drafted by B (图案输入与字符画), ready for the day 1-3 freeze.
- The remaining four are minimal placeholders so imports compile while each
  owner (A/E/F) fills them in before the freeze meeting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# B's deliverable: the downsampled character grid
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GridCell:
    """One cell of the character grid — one character position in the source."""

    x: int          # column, 0-based
    y: int          # row, 0-based
    fg: bool        # True = 前景（需占用）, False = 背景（可留空）
    level: int      # density index, 0 <= level < len(charset)
    ch: str         # final glyph: charset[level] for fg, ' ' for background


@dataclass
class PixelGrid:
    """Downsampled target pattern, row-major cells, size bounded by max_w.

    Producers : B's ``build_grid(src, charset, max_w)``
    Consumers : C / D backends (fill foreground cells), F's shape check.

    ``cell.fg`` is the only authoritative foreground signal: a foreground cell
    may legitimately carry a blank glyph (``ch == ' '`` when ``level == 0``),
    so glyph rows alone cannot rebuild the mask. Use ``fg_rows`` / ``fg_mask()``
    and never re-derive foreground from ``render()``.

    Field-set note: this is a *superset* of the 6-field version A may freeze —
    ``max_w`` is the only extra field and it sits last with a default of
    ``None``, so 5-/6-positional construction keeps working. ``export_meta`` /
    ``load_meta`` accept any structurally equivalent object (duck typing), so a
    6-field ``PixelGrid`` is fine on both sides.
    """

    width: int
    height: int
    cells: tuple[GridCell, ...]   # index = y * width + x
    charset: str                  # density chars, sparse -> dense, first char ~ blank
    source: str                   # image path or slogan text, for reporting
    threshold: float = 128.0      # gray level (0-255) separating fg from bg
    max_w: Optional[int] = None   # requested width cap (None on legacy/manual grids)

    def at(self, x: int, y: int) -> GridCell:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"({x}, {y}) out of {self.width}x{self.height}")
        return self.cells[y * self.width + x]

    def row(self, y: int) -> str:
        return "".join(self.cells[y * self.width + x].ch for x in range(self.width))

    def render(self) -> str:
        return "\n".join(self.row(y) for y in range(self.height))

    @property
    def grid_rows(self) -> tuple[str, ...]:
        """Glyph rows, 0-based, one character per cell, no trailing rstrip."""
        return tuple(self.row(y) for y in range(self.height))

    @property
    def fg_rows(self) -> tuple[str, ...]:
        """Foreground mask rows: ``'1'`` = 前景格, ``'0'`` = 背景格.

        JSON-friendly mirror of ``cell.fg``; survives the "fg but blank glyph"
        case that ``grid_rows`` cannot express.
        """
        return tuple(
            "".join("1" if self.cells[y * self.width + x].fg else "0"
                    for x in range(self.width))
            for y in range(self.height)
        )

    def fg_mask(self) -> tuple[tuple[bool, ...], ...]:
        """2D bool foreground mask, same (rows x cols) shape as the grid."""
        return tuple(
            tuple(self.cells[y * self.width + x].fg for x in range(self.width))
            for y in range(self.height)
        )

    @property
    def fg_count(self) -> int:
        return sum(1 for c in self.cells if c.fg)

    @property
    def density(self) -> float:
        """Foreground ratio 0.0-1.0, used by F's 图案密度 report."""
        return self.fg_count / len(self.cells) if self.cells else 0.0


# ---------------------------------------------------------------------------
# Placeholders — owners fill these before the day 1-3 freeze.
# ---------------------------------------------------------------------------

@dataclass
class CodeSkeleton:
    """Parsed functional code skeleton: real statements + original positions. (owner: C)"""

    source_path: str
    lang: str                      # c | cpp | python
    statements: list = field(default_factory=list)   # TODO: (text, start_line, end_line, kind)
    fixed_regions: list = field(default_factory=list)  # TODO: regions only statements may occupy


@dataclass
class CanvasPlan:
    """Backend's free-canvas landing points. (owner: A for the base, C/D per backend)"""

    lang: str
    block_comments: list = field(default_factory=list)   # TODO: (row_span, col_span) intervals
    string_lands: list = field(default_factory=list)     # TODO: string-literal landing points
    raw_strings: list = field(default_factory=list)      # TODO: C++ R"( )" intervals
    paren_regions: list = field(default_factory=list)    # TODO: Python implicit-line-join spans


@dataclass
class VerifyReport:
    """Aggregate of the three checks: compile / run-stdout / shape. (owner: E)"""

    path: str
    compile_ok: bool = False
    run_ok: bool = False
    output_match: bool = False
    shape_ok: bool = Optional[bool]
    failed_items: list = field(default_factory=list)
    note: str = ""                 # e.g. degraded mode when no compiler found


@dataclass
class CompilerInfo:
    """Detected compiler: path, version, whether verify must degrade. (owner: E)"""

    kind: str = ""                 # gcc | g++ | clang | clang++ | cl
    path: str = ""
    version: str = ""
    needs_degrade: bool = False
