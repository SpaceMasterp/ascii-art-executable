"""Tests for B (v2): shape mask generation (`codeart.shapes`)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from codeart import (  # noqa: E402
    FontMetrics,
    ShapeError,
    ShapeSpec,
    SizeRequest,
    build_mask,
    geometry_metrics,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "shapes"
KINDS = ("circle", "cat", "code")


def make(kind: str, rows: int = 32, **kwargs):
    return build_mask(ShapeSpec(kind, **kwargs), SizeRequest(rows), FontMetrics())


def allowed_from_spans(width: int, spans) -> list[list[bool]]:
    """Rebuild allowed[][] from spans — the definition used by the renderer."""
    rows = []
    for row_spans in spans:
        row = [False] * width
        for start, end in row_spans:
            assert 0 <= start < end <= width, (start, end, width)
            for col in range(start, end):
                assert not row[col], "spans overlap"
                row[col] = True
        rows.append(row)
    return rows


# --------------------------------------------------------------- structure --

def test_three_shapes_at_two_sizes():
    for kind in KINDS:
        for rows in (32, 64):
            mask = make(kind, rows)
            assert mask.height == rows
            if kind in ("circle", "cat"):
                assert mask.width == math.ceil(rows * 1.0 / 0.5)
            assert len(mask.allowed) == mask.height
            assert all(len(row) == mask.width for row in mask.allowed)
            assert len(mask.spans) == mask.height
            assert mask.inner_radius is None
            assert mask.kind == kind
            assert mask.font_metrics.cell_aspect == 0.5


def test_spans_rebuild_allowed_exactly():
    for kind in KINDS:
        for rows in (32, 64):
            mask = make(kind, rows)
            rebuilt = allowed_from_spans(mask.width, mask.spans)
            assert rebuilt == [list(row) for row in mask.allowed]


def test_spans_are_sorted_and_disjoint():
    for kind in KINDS:
        mask = make(kind, 32)
        for row_spans in mask.spans:
            starts = [s for s, _ in row_spans]
            assert starts == sorted(starts)
            for (s1, e1), (s2, _e2) in zip(row_spans, row_spans[1:]):
                assert e1 <= s2


def test_hole_cells_are_not_allowed():
    cat = make("cat", 32)
    for name in ("eye_left", "eye_right", "nose"):
        for (r, c) in cat.features[name]:
            assert cat.allowed[r][c] is False
    code = make("code", 32)
    assert code.features["code_strokes"]
    for (r, c) in code.features["code_strokes"]:
        assert code.allowed[r][c] is False


def test_some_row_has_multiple_spans():
    for kind in ("cat", "code"):
        mask = make(kind, 32)
        assert any(len(row) >= 2 for row in mask.spans), kind


# ------------------------------------------------------------------- metrics --

def test_cat_features_meet_acceptance():
    for rows in (32, 64):
        mask = make("cat", rows)
        metrics = geometry_metrics(mask)
        assert metrics["eye_cells"]["left"] >= 4
        assert metrics["eye_cells"]["right"] >= 4
        assert metrics["nose_cells"] >= 2
        assert metrics["ear_gap_rows"] >= 2, metrics["ear_gap_rows"]
        assert len(metrics["holes"]) == 3          # two eyes + nose


def test_circle_bbox_ratio():
    for rows in (32, 64):
        metrics = geometry_metrics(make("circle", rows))
        assert abs(metrics["bbox"]["ratio"] - 1.0) <= 0.05


def test_determinism():
    for kind in KINDS:
        assert make(kind, 32) == make(kind, 32)
        assert geometry_metrics(make(kind, 32)) == geometry_metrics(make(kind, 32))


def test_scaling_preserves_geometry():
    small = geometry_metrics(make("cat", 32))
    large = geometry_metrics(make("cat", 64))
    for side in ("left", "right"):
        ratio = large["eye_cells"][side] / small["eye_cells"][side]
        assert 3.0 <= ratio <= 5.0, ratio          # area grows ~4x
    nose_ratio = large["nose_cells"] / small["nose_cells"]
    assert 2.7 <= nose_ratio <= 5.3, nose_ratio
    assert large["ear_gap_rows"] >= small["ear_gap_rows"]


# -------------------------------------------------------------------- errors --

def test_inner_radius_is_rejected():
    with pytest.raises(ShapeError) as info:
        build_mask(ShapeSpec("cat", inner_radius=0.5), SizeRequest(32), FontMetrics())
    assert info.value.code == "INVALID_SHAPE"
    assert "ring" in info.value.message


def test_code_text_must_be_code():
    make("code")                                    # defaults to CODE
    with pytest.raises(ShapeError) as info:
        build_mask(ShapeSpec("code", text="HELLO"), SizeRequest(32), FontMetrics())
    assert info.value.code == "INVALID_SHAPE"


def test_invalid_height_rows():
    for bad in (0, -5):
        with pytest.raises(ShapeError) as info:
            build_mask(ShapeSpec("circle"), SizeRequest(bad), FontMetrics())
        assert info.value.code == "INVALID_SIZE"


def test_unknown_kind_is_rejected():
    with pytest.raises(ShapeError) as info:
        build_mask(ShapeSpec("triangle"), SizeRequest(32), FontMetrics())
    assert info.value.code == "INVALID_SHAPE"


# -------------------------------------------------------------------- ctx --

def test_ctx_duck_typing():
    class Ctx:
        def __init__(self):
            self.calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls > 3:
                raise RuntimeError("cancelled")

    ctx = Ctx()
    with pytest.raises(RuntimeError):
        build_mask(ShapeSpec("circle"), SizeRequest(32), FontMetrics(), ctx=ctx)
    assert ctx.calls == 4

    class PlainCtx:
        def __init__(self):
            self.calls = 0

        def check(self):
            self.calls += 1

    plain = PlainCtx()
    make_mask = build_mask(ShapeSpec("cat"), SizeRequest(8), FontMetrics(), ctx=plain)
    assert make_mask.height == 8
    assert plain.calls == 8


# --------------------------------------------------------------- fixtures --

@pytest.mark.parametrize("kind", KINDS)
def test_fixture_regression(kind):
    path = FIXTURES / f"{kind}_32.json"
    assert path.is_file(), path
    data = json.loads(path.read_text(encoding="utf-8"))
    mask = make(kind, data["height"])
    assert mask.width == data["width"]
    assert mask.height == data["height"]
    assert ["".join("#" if v else "." for v in row) for row in mask.allowed] == data["rows"]
    assert [[list(s) for s in spans] for spans in mask.spans] == data["spans"]
