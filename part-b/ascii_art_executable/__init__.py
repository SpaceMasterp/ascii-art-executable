"""ASCII Art Executable — public pipeline package.

Module owners per 启动方案 §五:
- B: grid (image/slogan → PixelGrid)  ← this phase
- C: backends/c, D: backends/{cpp,python}, E: verify + cli, F: shapecheck
"""

from shared.types import GridCell, PixelGrid
from ascii_art_executable.grid import (
    DEFAULT_CHARSET,
    META_SCHEMA_VERSION,
    build_grid,
    export_meta,
    load_meta,
    validate_charset,
)

__all__ = [
    "DEFAULT_CHARSET",
    "GridCell",
    "META_SCHEMA_VERSION",
    "PixelGrid",
    "build_grid",
    "export_meta",
    "load_meta",
    "validate_charset",
]
