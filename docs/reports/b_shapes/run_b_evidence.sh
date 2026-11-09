#!/usr/bin/env bash
# Reproduce docs/reports/b_shapes/B_tests.txt for Part B.
#
# Usage (from a clean checkout of the tested commit):
#   python3 -m venv /tmp/bchkvenv
#   /tmp/bchkvenv/bin/python -m pip install -q pytest
#   PY=/tmp/bchkvenv/bin/python bash docs/reports/b_shapes/run_b_evidence.sh
#
# B does not need libclang: codeart.shapes is pure Python.
set -u
PY="${PY:-python3}"
FIXTURES="tests/fixtures/shapes"
HEIGHTS="32 64 96 128"

run() {
  echo
  echo "\$ $*"
  "$@" 2>&1
  echo "[exit $?]"
}

echo "# Part B — test run and generator idempotency evidence"
echo "# Repo: $(git rev-parse --show-toplevel 2>/dev/null)"
echo "# Command: $0"
echo "# Code commit under test (origin/main): $(git rev-parse origin/main)"
echo "# Branch: $(git rev-parse --abbrev-ref HEAD)"
outside=$(git status --porcelain | awk '{print $2}' | grep -cv '^docs/reports/')
echo "# Uncommitted changes outside docs/reports/: $([ "$outside" -eq 0 ] && echo no || echo yes)"
echo "# git status --porcelain at run time (only this PR's docs are expected):"
git status --porcelain

run "$PY" -m pytest tests/test_shapes.py tests/test_shape_metrics.py -q

echo
echo "# --- generator idempotency: sha256 of the four fixtures ---"
echo "# baseline (before the first run)"
run sha256sum $(for h in $HEIGHTS; do printf '%s/metrics_h%s.json ' "$FIXTURES" "$h"; done)

echo
echo "# first run"
run "$PY" scripts/gen_shape_metrics.py
run sha256sum $(for h in $HEIGHTS; do printf '%s/metrics_h%s.json ' "$FIXTURES" "$h"; done)

echo
echo "# second run"
run "$PY" scripts/gen_shape_metrics.py
run sha256sum $(for h in $HEIGHTS; do printf '%s/metrics_h%s.json ' "$FIXTURES" "$h"; done)

echo
echo "# fixtures untouched by the two runs (empty = byte identical)"
run git status --porcelain "$FIXTURES"
run git diff --stat "$FIXTURES"
