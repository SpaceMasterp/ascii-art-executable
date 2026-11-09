"""Tests for the scaled shape metrics consumed by the verifier (Part E)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from codeart import (  # noqa: E402
    FontMetrics,
    ShapeSpec,
    SizeRequest,
    build_mask,
    geometry_metrics,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "shapes"
HEIGHTS = (32, 64, 96)
KINDS = ("circle", "cat", "code")
HOLE_FEATURES = ("eye_left", "eye_right", "nose")
TOLERANCE_KEYS = {
    "bbox_ratio_abs",
    "area_rel",
    "area_abs_cells",
    "centroid_abs_cells",
}


def load(rows: int) -> dict:
    path = FIXTURES / f"metrics_h{rows}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def make(kind: str, rows: int):
    return build_mask(
        ShapeSpec(kind, text="CODE" if kind == "code" else None),
        SizeRequest(rows),
        FontMetrics(),
    )


def stats(cells) -> dict:
    """Same conventions as the generator: inclusive bbox, cell-centre centroid."""
    count = len(cells)
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return {
        "cells": count,
        "bbox": [min(rows), min(cols), max(rows), max(cols)],
        "centroid": [
            sum(row + 0.5 for row in rows) / count,
            sum(col + 0.5 for col in cols) / count,
        ],
    }


def area_tolerance(tol: dict, expected: float) -> float:
    return max(tol["area_abs_cells"], tol["area_rel"] * expected)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ schema --

@pytest.mark.parametrize("rows", HEIGHTS)
def test_document_schema(rows):
    document = load(rows)
    assert document["schema_version"] == 1
    assert document["cell_aspect"] == 0.5
    assert document["height_rows"] == rows
    assert document["generated_by"] == "scripts/gen_shape_metrics.py"
    assert set(document["tolerance"]) == TOLERANCE_KEYS
    assert set(document["shapes"]) == set(KINDS)
    assert document["scaling_expectation"]["area_scale_ref_height"] == 32
    assert document["scaling_expectation"]["note"]


# -------------------------------------------------- current implementation --

@pytest.mark.parametrize("rows", HEIGHTS)
@pytest.mark.parametrize("kind", KINDS)
def test_fixture_matches_current_implementation(kind, rows):
    document = load(rows)
    expected = document["shapes"][kind]
    tol = document["tolerance"]

    mask = make(kind, rows)
    actual = geometry_metrics(mask)

    assert expected["cols"] == mask.width == actual["cols"]
    assert expected["rows"] == mask.height == actual["rows"]
    assert expected["bbox_ratio"] == pytest.approx(
        actual["bbox"]["ratio"], abs=tol["bbox_ratio_abs"])

    expected_area = expected["allowed_cells"]
    assert abs(actual["allowed_cells"] - expected_area) <= area_tolerance(
        tol, expected_area)
    assert expected["spans_total"] == actual["spans_total"]
    assert expected["rows_with_multiple_spans"] == actual["rows_with_multiple_spans"]

    present = {name for name in HOLE_FEATURES if mask.features.get(name)}
    assert set(expected["features"]) == present

    for name in present:
        got = stats(mask.features[name])
        ref = expected["features"][name]
        assert abs(got["cells"] - ref["cells"]) <= area_tolerance(tol, ref["cells"])
        assert got["bbox"] == ref["bbox"]
        assert got["centroid"] == pytest.approx(
            ref["centroid"], abs=tol["centroid_abs_cells"])

    assert expected["hole_count"] == len(present)
    if kind == "cat":
        assert expected["ear_gap_rows"] == actual["ear_gap_rows"]
    else:
        assert expected["ear_gap_rows"] is None


# ------------------------------------------------------- scaling invariant --

@pytest.mark.parametrize("kind", KINDS)
def test_feature_keys_are_identical_at_every_height(kind):
    keysets = [set(load(rows)["shapes"][kind]["features"]) for rows in HEIGHTS]
    assert keysets[0] == keysets[1] == keysets[2]
    assert keysets[0] == (set(HOLE_FEATURES) if kind == "cat" else set())


@pytest.mark.parametrize("kind", KINDS)
def test_feature_areas_scale_with_height_squared(kind):
    reference = load(32)["shapes"][kind]
    tol = load(32)["tolerance"]
    for rows in HEIGHTS[1:]:
        scaled = load(rows)["shapes"][kind]
        assert set(scaled["features"]) == set(reference["features"])
        for name, ref_feature in reference["features"].items():
            expected = ref_feature["cells"] * (rows / 32) ** 2
            got = scaled["features"][name]["cells"]
            assert got >= 1
            assert abs(got - expected) <= area_tolerance(tol, expected), (
                kind, name, rows, got, expected)


@pytest.mark.parametrize("kind", KINDS)
def test_feature_centroids_scale_linearly(kind):
    reference = load(32)["shapes"][kind]
    tol = load(32)["tolerance"]["centroid_abs_cells"]
    for rows in HEIGHTS[1:]:
        scaled = load(rows)["shapes"][kind]
        for name, ref_feature in reference["features"].items():
            expected = [value * rows / 32 for value in ref_feature["centroid"]]
            got = scaled["features"][name]["centroid"]
            for actual, target in zip(got, expected):
                assert abs(actual - target) <= tol, (
                    kind, name, rows, actual, target)


@pytest.mark.parametrize("kind", KINDS)
def test_bbox_ratio_is_height_invariant(kind):
    ratios = [load(rows)["shapes"][kind]["bbox_ratio"] for rows in HEIGHTS]
    tol = load(32)["tolerance"]["bbox_ratio_abs"]
    assert max(ratios) - min(ratios) <= tol


# ------------------------------------------------------------- generator --

def test_generator_is_idempotent_and_fixtures_are_current(tmp_path):
    script = ROOT / "scripts" / "gen_shape_metrics.py"
    outputs = []
    for run in ("first", "second"):
        out_dir = tmp_path / run
        result = subprocess.run(
            [sys.executable, str(script), "--out-dir", str(out_dir)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "wrote" in result.stdout
        outputs.append(out_dir)

    for rows in HEIGHTS:
        name = f"metrics_h{rows}.json"
        first = outputs[0] / name
        second = outputs[1] / name
        committed = FIXTURES / name
        assert first.read_bytes() == second.read_bytes() == committed.read_bytes()
        assert sha256(first) == sha256(second) == sha256(committed)
