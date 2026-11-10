"""Shared result presentation for the CLI and local web interface."""

from dataclasses import asdict, is_dataclass
from enum import Enum

from .contracts import CheckStatus, ErrorCode

CHECKS = ("token", "geometry", "compile", "behavior")

LOW_CODE_FILL_WARNING = "Token density is low; filler comments occupy most allowed cells."


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def describe_result(result):
    """Retain diagnostics and attempt history without sending the full mask."""
    report = result.verification
    stop_reason = next((item.code.value for item in result.diagnostics
                        if item.code in (ErrorCode.CANCELLED, ErrorCode.PIPELINE_TIMEOUT)),
                       "PIPELINE_STOPPED")
    checks = {}
    for name in CHECKS:
        status = getattr(report, f"{name}_status", CheckStatus.NOT_RUN)
        reason = report.skip_reasons.get(name) if report else stop_reason
        if status == CheckStatus.NOT_RUN and reason is None:
            reason = stop_reason
        checks[name] = {"status": status.value, "reason": reason}
    verified = (
        not result.diagnostics
        and all(checks[name]["status"] == "PASS" for name in CHECKS[:3])
        and checks["behavior"]["status"] != "FAIL"
    )
    plan = result.plan
    rendered = result.rendered
    history = plan.attempt_history if plan else next(
        (item.details["attempt_history"] for item in result.diagnostics
         if "attempt_history" in item.details), (),
    )
    return {
        "verified": verified,
        "checks": checks,
        "diagnostics": json_value(result.diagnostics),
        "attempt_history": json_value(history),
        "layout": {
            "width": plan.mask.width, "height": plan.mask.height,
            "scale": plan.actual_scale, "attempts": plan.attempt_count,
        } if plan else None,
        "code_fill_ratio": rendered.token_coverage if rendered else None,
        "code_fill_warning": LOW_CODE_FILL_WARNING if rendered and rendered.token_coverage < 0.10 else None,
        "coverage": {
            "total": rendered.coverage, "token": rendered.token_coverage,
            "comment": rendered.comment_coverage, "comment_cells": rendered.comment_cells,
        } if rendered else None,
        "source_text": rendered.source_text if rendered else None,
        "verification": json_value(report) if report else None,
    }


def artifact_name(sample, shape, layout, extension="c"):
    """Include realized dimensions and scale so fixed and grown runs stay distinct."""
    stem = f"case_{sample or 'custom'}_{shape}"
    if layout:
        scale = format(layout["scale"], ".6g")
        stem += f"_h{layout['height']}_s{scale}"
    return f"{stem}.{extension}"
