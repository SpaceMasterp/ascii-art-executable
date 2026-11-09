"""Check that the current revision collects at least as many tests as its base."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory


def count_tests(root):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=root, capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    match = re.search(r"(\d+) tests? collected", result.stdout)
    if match is None:
        raise RuntimeError("Cannot determine the collected test count")
    return int(match.group(1))


def main():
    base = os.environ.get("BASE_SHA", "")
    if not base or set(base) == {"0"}:
        print("No baseline revision is available.")
        return
    root = Path(__file__).resolve().parents[1]
    current = count_tests(root)
    with TemporaryDirectory(prefix="codeart-base-") as directory:
        archive = Path(directory) / "base.tar"
        with archive.open("wb") as output:
            subprocess.run(["git", "archive", base], cwd=root, stdout=output, check=True)
        baseline = Path(directory) / "checkout"
        baseline.mkdir()
        with tarfile.open(archive) as files:
            files.extractall(baseline, filter="data")
        previous = count_tests(baseline)
    print(f"Base {base}: {previous} tests; current: {current} tests.")
    if current < previous:
        raise SystemExit("The collected test count decreased.")


if __name__ == "__main__":
    main()
