"""Regression tests for the Part D evidence generator."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from codeart.contracts import (
    Diagnostic,
    ErrorCode,
    GenerationRequest,
    GenerationResult,
    ShapeSpec,
)
from codeart.pipeline import generate


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_d_reports", ROOT / "scripts" / "generate_d_reports.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_refuses_an_existing_output_directory(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    unrelated = output / "other_member_h128.c"
    unrelated.write_text("/* keep me */\n", encoding="utf-8")
    assert MODULE.main(["--output-dir", str(output)]) == 2
    assert unrelated.read_text(encoding="utf-8") == "/* keep me */\n"


def test_row_ok_rejects_failed_or_undiagnosed_checks():
    good = {
        "token": "PASS", "geometry": "PASS", "compile_status": "PASS",
        "behavior": "NOT_RUN", "compile_rc": 0, "hole_ink": 0,
        "line_tail_ok": "YES", "diagnostics": "",
    }
    assert MODULE._row_ok(good)
    for key, value in (
        ("token", "FAIL"), ("geometry", "FAIL"), ("compile_status", "NOT_RUN"),
        ("behavior", "FAIL"), ("compile_rc", 1), ("hole_ink", 1),
        ("line_tail_ok", "NO"), ("diagnostics", "pipeline:CANCELLED: cancelled"),
    ):
        broken = dict(good, **{key: value})
        assert not MODULE._row_ok(broken), (key, value)


def test_partial_result_is_archived_and_fails_the_run(tmp_path, monkeypatch):
    request = GenerationRequest(
        "int add(int a,int b){return a+b;}", ShapeSpec("circle")
    )
    full = generate(request)
    assert full.plan is not None and full.rendered is not None
    partial = GenerationResult(
        plan=full.plan,
        rendered=full.rendered,
        verification=None,
        diagnostics=[Diagnostic(ErrorCode.CANCELLED, "verification", "cancelled")],
    )
    monkeypatch.setattr(MODULE, "generate", lambda _request: partial)

    output = tmp_path / "partial"
    assert MODULE.main(["--output-dir", str(output)]) == 1

    rows = list(csv.DictReader((output / "D_manifest.csv").open(encoding="utf-8")))
    assert rows
    assert all(row["token"] == "NOT_RUN" for row in rows)
    assert all("CANCELLED" in row["diagnostics"] for row in rows)
    assert (output / "D_cases.md").exists()
    assert list(output.glob("case_*.c"))
