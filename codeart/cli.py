"""Command-line entry point for the integration smoke demo and production pipeline."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from ._integration_demo import DEMO_SOURCE, demo_deps
from .contracts import CheckStatus, GenerationRequest, ShapeSpec
from .environment import revision_info
from .pipeline import generate
from .prepass import inspect_file, selected_source, SCOPE
from .presentation import json_value
from .presentation import CHECKS, describe_result
from .verification_fixtures import BUILTIN_FIXTURES, select_builtin


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--demo", action="store_true", help="use the fixed smoke fixture")
    inputs.add_argument("--sample", choices=tuple(BUILTIN_FIXTURES), help="verify a real built-in sample")
    inputs.add_argument("--source", type=Path, help="path to a C11 function")
    inputs.add_argument("--file", type=Path, help="extract a function from a complete C file")
    parser.add_argument("--function", help="exact function name for --file")
    parser.add_argument("--shape", choices=("circle", "cat", "code"), default="circle")
    parser.add_argument("--output", type=Path, help="write generated source to this file")
    parser.add_argument("--scale", type=float, default=1.0, help="initial scale, between 1 and 4")
    parser.add_argument("--report", type=Path, help="write a JSON run report")
    args = parser.parse_args(argv)
    if args.function and not args.file:
        parser.error("--function requires --file")
    if not 1 <= args.scale <= 4:
        parser.error("--scale must be between 1 and 4")
    if args.report is not None:
        try:
            report_path = args.report.resolve()
            for option, path in (("--file", args.file), ("--source", args.source), ("--output", args.output)):
                if path is None:
                    continue
                same_path = report_path == path.resolve()
                if same_path or (
                    report_path.exists() and path.exists() and report_path.samefile(path)
                ):
                    parser.error(f"--report and {option} must refer to different files")
        except (OSError, RuntimeError) as exc:
            parser.exit(2, f"Cannot check report path: {exc}\n")
    selection = select_builtin(args.sample) if args.sample else None

    try:
        source = DEMO_SOURCE if args.demo else selection.fixture.source if selection else (args.file or args.source).read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        parser.exit(2, f"Cannot read source: {exc}\n")

    extraction = inspect_file(source, args.function) if args.file else None
    if extraction:
        print(SCOPE, file=sys.stderr)
        if extraction.error:
            data = json_value(extraction)
            if args.report:
                try:
                    args.report.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except OSError as exc:
                    parser.exit(2, f"Cannot write report: {exc}\n")
            print(json.dumps(data, indent=2), file=sys.stderr)
            return 1
        source = selected_source(extraction)

    if args.demo:
        print("Integration demo: real B mask, simulated A/C/D/E. Checks are not run.", file=sys.stderr)
    request = GenerationRequest(
        source, ShapeSpec(args.shape, "CODE" if args.shape == "code" else None), fixtures=selection,
    )
    request = replace(request, layout_options=replace(request.layout_options, initial_scale=args.scale))
    result = generate(request, deps=demo_deps() if args.demo else None)
    if args.report:
        try:
            report = describe_result(result)
            report["revision"] = revision_info()
            if extraction:
                report["prepass"] = json_value(extraction)
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except OSError as exc:
            parser.exit(2, f"Cannot write report: {exc}\n")

    if result.plan is not None:
        plan = result.plan
        print(f"{plan.mask.width} x {plan.mask.height}; scale={plan.actual_scale:g}; "
              f"attempts={plan.attempt_count}", file=sys.stderr)
    if result.rendered is not None:
        print(f"coverage={result.rendered.coverage:.2%}; code_fill_ratio={result.rendered.token_coverage:.2%}", file=sys.stderr)
        if result.rendered.token_coverage < 0.10:
            print("Low code fill: consider a smaller shape.", file=sys.stderr)
    report = result.verification
    for name in CHECKS:
        status = getattr(report, f"{name}_status", CheckStatus.NOT_RUN)
        reason = report.skip_reasons.get(name) if report is not None else "PIPELINE_STOPPED"
        print(f"{name}: {status.value}" + (f" ({reason})" if reason else ""), file=sys.stderr)
    for diagnostic in result.diagnostics:
        position = f":{diagnostic.line}" if diagnostic.line is not None else ""
        if diagnostic.column is not None:
            position += f":{diagnostic.column}"
        print(f"{diagnostic.stage}{position}: {diagnostic.code.value}: {diagnostic.message}",
              file=sys.stderr)

    if result.rendered is not None:
        data = result.rendered.source_text.encode("utf-8")
        try:
            if args.output is None:
                sys.stdout.buffer.write(data)
            else:
                args.output.write_bytes(data)
        except OSError as exc:
            parser.exit(2, f"Cannot write output: {exc}\n")

    if args.demo:
        return int(bool(result.diagnostics) or result.rendered is None)
    if report is None:
        return 1
    required = (report.token_status, report.geometry_status, report.compile_status)
    return int(bool(result.diagnostics) or any(status != CheckStatus.PASS for status in required)
               or report.behavior_status == CheckStatus.FAIL)


if __name__ == "__main__":
    raise SystemExit(main())
