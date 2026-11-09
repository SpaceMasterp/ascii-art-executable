"""Record Part A's diagnostics for the documented error demonstrations.

Usage:
    python -m scripts.check_source_diagnostics [--output PATH]

Each case names the expected shared `ErrorCode`; the command exits nonzero when
a case produces another code, so the archived JSON and the exit status agree.
"""

import argparse
import json
from pathlib import Path
import sys

from codeart import source
from codeart.contracts import ErrorCode, StageError, VerificationProfile
from codeart.environment import revision_info

VALID = "int f(int x){int y=x*2;return y+1;}"

CASES = (
    {
        "name": "valid_function",
        "note": "A self-contained function is accepted; no main is required.",
        "source": VALID,
        "expected": None,
    },
    {
        "name": "non_ascii",
        "note": "Non-ASCII identifier reports its original line and column.",
        "source": "int f(void) {\n  return 变量;\n}",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "line_macro",
        "note": "__LINE__ is rejected without any preprocessing directive.",
        "source": "int f(void){return __LINE__;}",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "file_macro",
        "note": "The predefined macro table also covers __FILE__ and __COUNTER__.",
        "source": "int f(void){ return __FILE__[0] + __COUNTER__; }",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "compiler_extension",
        "note": "GNU extensions are outside the frozen input scope.",
        "source": 'int f(void){ __asm__("nop"); return 0; }',
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "trigraph",
        "note": "Trigraphs change the token stream during translation phase 1.",
        "source": "int f(void){ return 1 ??= 2; }",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "line_splice",
        "note": "A backslash-newline is a phase 2 transformation.",
        "source": "int f(void){ ret\\\nurn 0; }",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "external_call",
        "note": "A call to an undeclared function is an external dependency.",
        "source": "int f(int x){return g(x);}",
        "expected": "UNSUPPORTED_SOURCE",
    },
    {
        "name": "invalid_syntax",
        "note": "A parse error is reported as INVALID_SOURCE with a location.",
        "source": "int f(void) { return ;;; @ }",
        "expected": "INVALID_SOURCE",
    },
    {
        "name": "missing_compiler",
        "note": "A missing compiler keeps the run diagnosed, not silently accepted.",
        "source": VALID,
        "profile": {"compiler": "codeart-missing-compiler"},
        "expected": "DEPENDENCY_UNAVAILABLE",
    },
)


def run_case(case):
    profile = VerificationProfile(**case.get("profile", {}))
    record = {"name": case["name"], "note": case["note"], "input": case["source"],
              "expected": case["expected"]}
    try:
        model = source.analyze_source(case["source"], profile)
    except StageError as exc:
        diagnostic = exc.diagnostic
        record.update(
            actual=diagnostic.code.value, stage=diagnostic.stage,
            line=diagnostic.line, column=diagnostic.column, message=diagnostic.message,
            passed=diagnostic.code.value == case["expected"],
        )
    else:
        record.update(
            actual=None, stage="analysis", line=None, column=None,
            function_name=model.function_name, token_count=len(model.tokens),
            passed=case["expected"] is None,
        )
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the JSON report here")
    arguments = parser.parse_args(argv)
    records = [run_case(case) for case in CASES]
    report = {"revision": revision_info(), "cases": records,
              "passed": all(record["passed"] for record in records)}
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    for record in records:
        status = "PASS" if record["passed"] else "FAIL"
        location = (f"{record['line']}:{record['column']}"
                    if record["line"] else "-")
        print(f"{status} {record['name']:20} {record['actual'] or 'ACCEPTED':22} {location}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
