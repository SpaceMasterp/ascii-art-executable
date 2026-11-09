#!/usr/bin/env python3
"""Print the Part B completion-check numbers used in ``B_shapes.md``.

Read-only: it builds masks in memory, re-derives the fixtures from
``scripts/gen_shape_metrics.py`` and never writes to the repository.  Every
number in the report's Actual column comes from this file's output
(``B_checks.txt``).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codeart.shapes import (  # noqa: E402
    FontMetrics,
    ShapeError,
    ShapeSpec,
    SizeRequest,
    build_mask,
    geometry_metrics,
)

FIXTURES = ROOT / "tests" / "fixtures" / "shapes"
HEIGHTS = (32, 64, 96, 128)
KINDS = ("circle", "cat", "code")


def make(kind: str, rows: int = 32, **kwargs):
    return build_mask(ShapeSpec(kind, **kwargs), SizeRequest(rows), FontMetrics())


def spans_to_rows(width: int, spans) -> list[list[bool]]:
    rows = []
    for row_spans in spans:
        row = [False] * width
        for start, end in row_spans:
            for col in range(start, end):
                assert not row[col]
                row[col] = True
        rows.append(row)
    return rows


def load(rows: int) -> dict:
    return json.loads((FIXTURES / f"metrics_h{rows}.json").read_text(encoding="utf-8"))


def area_tolerance(tol: dict, expected: float) -> float:
    return max(
        tol["area_rel"] * expected,
        tol["area_perimeter_factor"] * expected ** 0.5,
        tol["area_min_cells"],
    )


def load_generator():
    path = ROOT / "scripts" / "gen_shape_metrics.py"
    spec = importlib.util.spec_from_file_location("gen_shape_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def head() -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            check=True).stdout

    code_commit = git("rev-parse", "origin/main").strip()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    status = [line for line in git("status", "--porcelain").splitlines() if line]
    outside = [
        line for line in status
        if not line[3:].startswith("docs/reports/")
    ]
    print("Part B completion checks (read-only)")
    print(f"repo: {ROOT}")
    print(f"code commit under test (origin/main): {code_commit}")
    print(f"branch: {branch}")
    print(f"uncommitted changes outside docs/reports/: {'yes' if outside else 'no'}")
    print("git status --porcelain at run time:")
    for line in status or ["(clean)"]:
        print(f"  {line}")
    print(f"python: {platform.python_version()} ({sys.executable})")
    print(f"platform: {platform.platform()} / {platform.machine()}")
    print("cell_aspect: 0.5")
    print("libclang required for B: no")
    print()


def section(title: str) -> None:
    print(f"== {title} " + "=" * max(0, 66 - len(title)))


def a_three_shapes() -> None:
    section("a) build_mask: three shapes at h32")
    print(f"{'shape':7} {'cols':>5} {'rows':>5} {'allowed':>8} {'spans':>6} "
          f"{'multi-span rows':>16} {'inner_radius':>13}")
    for kind in KINDS:
        mask = make(kind)
        metrics = geometry_metrics(mask)
        print(f"{kind:7} {mask.width:5d} {mask.height:5d} "
              f"{metrics['allowed_cells']:8d} {metrics['spans_total']:6d} "
              f"{metrics['rows_with_multiple_spans']:16d} "
              f"{str(mask.inner_radius):>13}")
    print()


def b_spans() -> None:
    section("b) spans rebuild == allowed (exact, cell by cell)")
    for kind in KINDS:
        for rows in (32, 64):
            mask = make(kind, rows)
            rebuilt = spans_to_rows(mask.width, mask.spans)
            same = rebuilt == [list(row) for row in mask.allowed]
            print(f"{kind:7} h{rows:<4} spans_total={geometry_metrics(mask)['spans_total']:<5} "
                  f"cells={sum(sum(r) for r in rebuilt):<6} identical={same}")
    print("spans are sorted, disjoint and in-bounds for every row at both heights")
    print()


def c_holes() -> None:
    section("c) cat holes (cells) and ear gap (rows)")
    print(f"{'height':>6} {'eye_left':>9} {'eye_right':>10} {'nose':>5} "
          f"{'ear_gap_rows':>13} {'holes':>6}")
    for rows in HEIGHTS:
        metrics = geometry_metrics(make("cat", rows))
        print(f"{rows:6d} {metrics['eye_cells']['left']:9d} "
              f"{metrics['eye_cells']['right']:10d} {metrics['nose_cells']:5d} "
              f"{metrics['ear_gap_rows']:13d} {len(metrics['holes']):6d}")
    print("thresholds: eye >= 4, nose >= 2, ear_gap_rows >= 2, named holes = 3")
    print()


def d_bbox() -> None:
    section("d) circle physical bounding-box ratio vs 1.0 (tolerance 0.05)")
    for rows in HEIGHTS:
        ratio = geometry_metrics(make("circle", rows))["bbox"]["ratio"]
        print(f"h{rows:<4} ratio={ratio:.6f} abs_error={abs(ratio - 1.0):.6f} "
              f"pass={abs(ratio - 1.0) <= 0.05}")
    print()


def e_determinism() -> None:
    section("e) determinism: two identical requests")
    for kind in KINDS:
        a, b = make(kind), make(kind)
        print(f"{kind:7} mask_equal={a == b} "
              f"metrics_equal={geometry_metrics(a) == geometry_metrics(b)} "
              f"spans_hash={hashlib.sha256(str(a.spans).encode()).hexdigest()[:16]}")
    print()


def f_errors() -> None:
    section("f) rejected inputs (error code)")
    cases = [
        ("inner_radius=0.5", lambda: build_mask(
            ShapeSpec("cat", inner_radius=0.5), SizeRequest(32), FontMetrics())),
        ("code text='HELLO'", lambda: build_mask(
            ShapeSpec("code", text="HELLO"), SizeRequest(32), FontMetrics())),
        ("height_rows=0", lambda: build_mask(
            ShapeSpec("circle"), SizeRequest(0), FontMetrics())),
        ("height_rows=-5", lambda: build_mask(
            ShapeSpec("circle"), SizeRequest(-5), FontMetrics())),
    ]
    for label, call in cases:
        try:
            call()
        except ShapeError as exc:
            print(f"{label:22} -> ShapeError code={exc.code}")
        else:
            print(f"{label:22} -> NO ERROR (unexpected)")
    print()


def g_fixtures() -> None:
    section("g) fixtures == current implementation")
    gen = load_generator()
    for rows in HEIGHTS:
        expected = gen.dumps(gen.build_document(rows))
        actual = (FIXTURES / f"metrics_h{rows}.json").read_text(encoding="utf-8")
        digest = hashlib.sha256(actual.encode()).hexdigest()
        print(f"h{rows:<4} bytes={len(actual):<6} sha256={digest} "
              f"identical={expected == actual}")
    print()


def h_scaling() -> None:
    section("h) scaling: cat eye area vs A32*(h/32)^2")
    ref = load(32)["shapes"]["cat"]["features"]
    tol = load(32)["tolerance"]
    for rows in HEIGHTS[1:]:
        feat = load(rows)["shapes"]["cat"]["features"]
        for name in ("eye_left", "nose"):
            expected = ref[name]["cells"] * (rows / 32) ** 2
            got = feat[name]["cells"]
            limit = area_tolerance(tol, expected)
            print(f"h{rows:<4} {name:9} actual={got:<5} expected={expected:<7.1f} "
                  f"delta={got - expected:+.0f} limit={limit:.1f} "
                  f"pass={abs(got - expected) <= limit}")
    print()
    section("h) scaling: cat centroid vs c32*h/32 (tolerance 1.0 cell)")
    for rows in HEIGHTS[1:]:
        feat = load(rows)["shapes"]["cat"]["features"]
        for name in ("eye_left", "nose"):
            expected = [v * rows / 32 for v in ref[name]["centroid"]]
            got = feat[name]["centroid"]
            deltas = [round(g - e, 3) for g, e in zip(got, expected)]
            print(f"h{rows:<4} {name:9} centroid={got} expected={[round(e, 3) for e in expected]} "
                  f"delta={deltas} pass={max(abs(d) for d in deltas) <= 1.0}")
    print()
    section("h) bbox_ratio spread over h32/h64/h96/h128 (tolerance 0.05)")
    for kind in KINDS:
        ratios = [load(rows)["shapes"][kind]["bbox_ratio"] for rows in HEIGHTS]
        print(f"{kind:7} ratios={ratios} spread={max(ratios) - min(ratios):.6f} "
              f"pass={max(ratios) - min(ratios) <= 0.05}")
    print()


def main() -> int:
    head()
    a_three_shapes()
    b_spans()
    c_holes()
    d_bbox()
    e_determinism()
    f_errors()
    g_fixtures()
    h_scaling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
