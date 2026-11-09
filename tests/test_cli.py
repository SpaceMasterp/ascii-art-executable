"""CLI sample eligibility and source/report output through the normal entry point."""

import json
import subprocess
import sys

from codeart.presentation import describe_result
from codeart.contracts import Diagnostic, ErrorCode, GenerationResult


def test_cli_real_sample_source_and_report(tmp_path):
    output = tmp_path / "max2.c"
    report_path = tmp_path / "max2.json"
    result = subprocess.run(
        [sys.executable, "-m", "codeart.cli", "--sample", "max2", "--shape", "cat",
         "--scale", "1.5", "--output", str(output), "--report", str(report_path)],
        capture_output=True, text=True, timeout=35,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text())
    assert report["verified"]
    assert all(item["status"] == "PASS" for item in report["checks"].values())
    assert report["layout"]["scale"] == 1.5
    assert output.read_bytes() == report["source_text"].encode()
    assert output.read_bytes().endswith(b"\n")


def test_failed_layout_keeps_attempt_history():
    history = [{"scale": 2, "reason": "capacity exhausted"}]
    result = GenerationResult(diagnostics=[
        Diagnostic(ErrorCode.LAYOUT_LIMIT, "layout", "No room", details={"attempt_history": history})
    ])
    report = describe_result(result)
    assert not report["verified"]
    assert report["attempt_history"] == history
    assert report["source_text"] is None
    assert report["checks"]["geometry"]["status"] == "NOT_RUN"


def test_artifact_names_include_realized_size():
    from codeart.presentation import artifact_name
    fixed = artifact_name("max2", "cat", {"height": 32, "scale": 1})
    grown = artifact_name("max2", "cat", {"height": 64, "scale": 2})
    assert fixed == "case_max2_cat_h32_s1.c"
    assert grown == "case_max2_cat_h64_s2.c"
    assert fixed != grown
