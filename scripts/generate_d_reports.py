"""Generate Part D's 18 real-layout artifacts into a fresh output directory.

Run from the repository root with the development environment:

    python scripts/generate_d_reports.py --output-dir docs/reports/part-d/2026-11-09_fixed

The script uses the real A -> C -> D pipeline (no fixtures), writes one
``case_<function>_<shape>_h<rows>_s<scale>.c`` per case into the new directory,
compiles each output independently, and writes ``D_manifest.csv`` and
``D_cases.md`` there.

It never deletes or overwrites other members' evidence: the output directory
must not exist, and the command exits non-zero when any required check is not
PASS, when generation/verification diagnostics are present, or when only a
partial result is available.
"""

from __future__ import annotations

import argparse
import csv
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codeart.contracts import GenerationRequest, ShapeSpec
from codeart.pipeline import generate


REPORTS = ROOT / "docs" / "reports"
SHAPES = ("circle", "cat", "code")

# Same six functions as E's builtin fixtures, submitted as ordinary input
# (fixtures=None), so behavior is expected to be NOT_RUN (NO_FIXTURE).
FUNCTIONS = {
    "max2": "int max2(int a, int b) { return a > b ? a : b; }",
    "min2": "int min2(int a, int b) { return a < b ? a : b; }",
    "clamp": "int clamp(int x, int lo, int hi) { return x < lo ? lo : x > hi ? hi : x; }",
    "absdiff": "int absdiff(int a, int b) { return a > b ? a - b : b - a; }",
    "gcd": (
        "int gcd(int a, int b) { while (b != 0) { int remainder = a % b; "
        "a = b; b = remainder; } return a; }"
    ),
    "sum_to_n": "int sum_to_n(int n) { return n * (n + 1) / 2; }",
}

BLOCK = re.compile(r"/\*=*\*/")
LINE = re.compile(r"//=*$")


def _lines(text: str):
    parts = text.split("\n")
    assert parts[-1] == ""
    return parts[:-1]


def _hole_cells(plan):
    cells = set()
    for name in ("eye_left", "eye_right", "nose", "code_strokes"):
        cells.update(plan.mask.features.get(name, ()))
    return cells


def _comment_checks(lines):
    block_lengths = []
    line_tail_ok = True
    line_count = 0
    for line in lines:
        block_lengths.extend(len(match.group()) for match in BLOCK.finditer(line))
        if "//" in line:
            line_count += 1
            if not LINE.search(line):
                line_tail_ok = False
    return block_lengths, line_count, line_tail_ok


def _compile(path: Path):
    artifact = path.with_suffix(".o")
    try:
        result = subprocess.run(
            [CC, "-std=c11", "-pedantic-errors", "-x", "c", "-c", str(path),
             "-o", str(artifact)],
            capture_output=True, text=True,
        )
        return result.returncode, result.stderr.strip()
    finally:
        artifact.unlink(missing_ok=True)


def _clang_version():
    try:
        return subprocess.check_output([CC, "--version"], text=True).splitlines()[0]
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"unavailable: {exc}"


def _git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _anchor():
    """Record the actual HEAD, branch and tracked-worktree state."""
    try:
        head = _git("rev-parse", "HEAD")
        branch = _git("rev-parse", "--abbrev-ref", "HEAD")
        dirty = "yes" if _git("status", "--porcelain", "--untracked-files=no") else "no"
        try:
            base = _git("merge-base", "HEAD", "origin/main")
            base_label = f"main@{base[:7]}"
        except Exception:
            base_label = "main@unknown"
        return {"head": head, "branch": branch, "dirty": dirty, "base": base_label}
    except Exception:
        return {"head": "unknown", "branch": "unknown", "dirty": "unknown", "base": "unknown"}


def _display(path: Path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _case_paths(out_dir, name, shape, height, scale):
    stem = f"case_{name}_{shape}_h{height}_s{scale:g}"
    return out_dir / f"{stem}.c", out_dir / f"{stem}.log"


def _coverage_split(rendered, plan):
    allowed = sum(1 for row in plan.mask.allowed for cell in row if cell) or 1
    block = rendered.comment_cells["block"] / allowed
    line = rendered.comment_cells["line"] / allowed
    return rendered.token_coverage, block, line


def _status(report, name):
    return getattr(report, f"{name}_status").value if report is not None else "NOT_RUN"


def _diagnostics(result, report):
    items = [f"pipeline:{item.code.value}: {item.message}" for item in result.diagnostics]
    if report is not None:
        items.extend(f"verify:{item.code.value}: {item.message}" for item in report.diagnostics)
    return " | ".join(items)


def _row_ok(row):
    return (
        row["token"] == "PASS"
        and row["geometry"] == "PASS"
        and row["compile_status"] == "PASS"
        and row["behavior"] != "FAIL"
        and row["compile_rc"] == 0
        and row["hole_ink"] == 0
        and row["line_tail_ok"] == "YES"
        and not row["diagnostics"]
    )


def _base_row(anchor, name, shape):
    return {
        "head": anchor["head"],
        "branch": anchor["branch"],
        "dirty": anchor["dirty"],
        "base": anchor["base"],
        "case_id": f"{name}_{shape}",
        "function": name,
        "shape": shape,
    }


def main(argv=None) -> int:
    global CC
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="new directory for this run; it must not already exist",
    )
    args = parser.parse_args(argv)

    CC = shutil.which("clang")
    if CC is None:
        print("clang is required to compile the rendered outputs", file=sys.stderr)
        return 1

    out_dir = args.output_dir
    if out_dir.exists():
        print(f"refusing to overwrite existing directory: {out_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True)

    anchor = _anchor()
    rows = []
    for name, text in FUNCTIONS.items():
        for shape in SHAPES:
            case_id = f"{name}_{shape}"
            started = monotonic()
            result = generate(GenerationRequest(text, ShapeSpec(shape)))
            elapsed_ms = round((monotonic() - started) * 1000)
            diagnostics = _diagnostics(result, result.verification)

            if result.rendered is None:
                output_path, log_path = _case_paths(out_dir, name, shape, 0, 0)
                output_path.write_text(
                    f"/* generation failed: {diagnostics} */\n", encoding="utf-8"
                )
                log_path.write_text(diagnostics + "\n", encoding="utf-8")
                row = _base_row(anchor, name, shape)
                row.update({
                    "height": 0, "scale": 0,
                    "output": _display(output_path),
                    "token": "NOT_RUN", "geometry": "NOT_RUN",
                    "compile_status": "NOT_RUN", "behavior": "NOT_RUN",
                    "behavior_reason": "PIPELINE_STOPPED",
                    "diagnostics": diagnostics,
                    "coverage": "0", "token_coverage": "0",
                    "block_comment_coverage": "0", "line_comment_coverage": "0",
                    "hole_ink": "-", "block_comments": "-", "min_block_len": "-",
                    "line_comments": "-", "line_tail_ok": "-", "attempts": "-",
                    "duration_ms": elapsed_ms, "compile_rc": "-",
                    "log": _display(log_path),
                })
                rows.append(row)
                continue

            plan = result.plan
            rendered = result.rendered
            report = result.verification
            lines = _lines(rendered.source_text)
            output_path, log_path = _case_paths(
                out_dir, name, shape, plan.mask.height, plan.actual_scale
            )
            output_path.write_text(rendered.source_text, encoding="utf-8")
            block_lengths, line_count, line_tail_ok = _comment_checks(lines)
            holes = _hole_cells(plan)
            hole_ink = sum(1 for row, col in holes if lines[row][col] != " ")
            compile_rc, compile_stderr = _compile(output_path)
            token_cov, block_cov, line_cov = _coverage_split(rendered, plan)

            row = _base_row(anchor, name, shape)
            row.update({
                "height": plan.mask.height,
                "scale": f"{plan.actual_scale:g}",
                "output": _display(output_path),
                "token": _status(report, "token"),
                "geometry": _status(report, "geometry"),
                "compile_status": _status(report, "compile"),
                "behavior": _status(report, "behavior"),
                "behavior_reason": (
                    report.skip_reasons.get("behavior", "")
                    if report is not None else "VERIFICATION_NOT_RUN"
                ),
                "diagnostics": diagnostics,
                "coverage": f"{rendered.coverage:.4f}",
                "token_coverage": f"{token_cov:.4f}",
                "block_comment_coverage": f"{block_cov:.4f}",
                "line_comment_coverage": f"{line_cov:.4f}",
                "hole_ink": hole_ink,
                "block_comments": len(block_lengths),
                "min_block_len": min(block_lengths) if block_lengths else "-",
                "line_comments": line_count,
                "line_tail_ok": "YES" if line_tail_ok else "NO",
                "attempts": plan.attempt_count,
                "duration_ms": elapsed_ms,
                "compile_rc": compile_rc,
                "log": _display(log_path),
            })
            rows.append(row)
            log_path.write_text(
                "\n".join([
                    f"head: {anchor['head']}",
                    f"branch: {anchor['branch']} dirty: {anchor['dirty']}",
                    f"case: {case_id} ({plan.mask.height} rows, scale {plan.actual_scale:g})",
                    f"token: {row['token']}",
                    f"geometry: {row['geometry']}",
                    f"compile: {row['compile_status']}",
                    f"behavior: {row['behavior']} ({row['behavior_reason']})",
                    f"coverage: {row['coverage']} (token {row['token_coverage']}, "
                    f"block {row['block_comment_coverage']}, "
                    f"line {row['line_comment_coverage']})",
                    f"comment_cells: {rendered.comment_cells}",
                    f"attempts: {row['attempts']}",
                    f"clang -c rc: {compile_rc}",
                    f"diagnostics: {row['diagnostics'] or '-'}",
                    f"stderr: {compile_stderr}",
                ]) + "\n",
                encoding="utf-8",
            )

    manifest = out_dir / "D_manifest.csv"
    columns = list(rows[0].keys()) if rows else []
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    header = "| " + " | ".join([
        "case", "height", "scale", "token", "geometry", "compile", "behavior",
        "coverage", "token cov", "block cov", "line cov", "hole ink",
        "min block", "line tail", "attempts", "compile rc",
    ]) + " |"
    divider = "|" + "---|" * 16
    table = [header, divider]
    for row in rows:
        table.append("| " + " | ".join([
            row["case_id"], str(row["height"]), str(row["scale"]), row["token"],
            row["geometry"], row["compile_status"], row["behavior"],
            row["coverage"], row["token_coverage"], row["block_comment_coverage"],
            row["line_comment_coverage"], str(row["hole_ink"]),
            str(row["min_block_len"]), str(row["line_tail_ok"]),
            str(row["attempts"]), str(row["compile_rc"]),
        ]) + " |")

    cases = out_dir / "D_cases.md"
    cases.write_text("\n".join([
        "# Part D — 18 real-layout cases",
        "",
        f"- HEAD: `{anchor['head']}`",
        f"- Branch: `{anchor['branch']}` (dirty: `{anchor['dirty']}`)",
        f"- Base: `{anchor['base']}`",
        f"- Host: {platform.platform()}",
        f"- Python: {platform.python_version()}",
        f"- clang: {_clang_version()}",
        "- Generated by: `python scripts/generate_d_reports.py --output-dir ...`",
        "- Artifacts: `case_<function>_<shape>_h<rows>_s<scale>.c`",
        "- Manifest: `D_manifest.csv`",
        "",
        "## Cases",
        "",
        *table,
        "",
        "## Notes",
        "",
        "- All inputs are ordinary input (`fixtures=None`); behavior is expected to be",
        "  `NOT_RUN (NO_FIXTURE)`. The 144 behavior comparisons belong to E's builtin",
        "  fixture matrix.",
        "- Coverage is split into token, block-comment and line-comment contributions;",
        "  the denominator is the number of allowed cells.",
        "- `min block` is the shortest block comment; the grammar requires at least 4 cells.",
        "- `line tail` verifies every line comment reaches the end of its row.",
        "- `hole ink` must be 0 for the cat eyes/nose and the hollow CODE strokes.",
        "- `compile rc` is an independent `clang -std=c11 -pedantic-errors -c` run.",
        "- The `_h<rows>_s<scale>` suffix keeps fixed-size outputs separate from future",
        "  scaled runs, and this directory is never overwritten.",
        "",
    ]), encoding="utf-8")

    bad = [row for row in rows if not _row_ok(row)]
    print(f"wrote {len(rows)} cases to {out_dir}")
    print(f"head: {anchor['head']} ({anchor['branch']}, dirty: {anchor['dirty']})")
    print(f"manifest: {manifest}")
    print(f"cases: {cases}")
    if bad:
        print(f"{len(bad)} case(s) did not pass the evidence checks", file=sys.stderr)
        for row in bad:
            print(
                f"  {row['case_id']}: token={row['token']} geometry={row['geometry']} "
                f"compile={row['compile_status']} behavior={row['behavior']} "
                f"rc={row['compile_rc']} hole={row['hole_ink']} "
                f"diagnostics={row['diagnostics'] or '-'}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
