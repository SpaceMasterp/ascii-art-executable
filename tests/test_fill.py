"""Part D tests: comment filling, boundaries, holes and re-lexing."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import monotonic

import pytest

from codeart import FontMetrics, Mask, ShapeSpec, SizeRequest, build_mask
from codeart import source
from codeart._verification_geometry import check_geometry
from codeart.contracts import (
    FillOptions,
    LayoutOptions,
    LayoutPlan,
    Placement,
    RunContext,
    SourceModel,
    Token,
    VerificationProfile,
)
from codeart.fill import render_source
from codeart.layout import fit_layout

CLANG = shutil.which("clang")
try:
    import clang.cindex  # noqa: F401
    HAS_LIBCLANG = True
except Exception:
    HAS_LIBCLANG = False
requires_clang = pytest.mark.skipif(
    CLANG is None or not HAS_LIBCLANG,
    reason="Clang and libclang are required",
)


def context(seconds=30):
    return RunContext(monotonic() + seconds)


def model_for(tokens, name="f", signature="int f("):
    return SourceModel("src", "src", tuple(tokens), VerificationProfile(), name, signature)


def plan_for(mask, placements, protected=()):
    return LayoutPlan(
        mask=mask,
        placements=tuple(placements),
        protected_blanks=frozenset(protected),
        actual_scale=1.0,
        attempt_count=1,
        attempt_history=(),
    )


def rect_mask(width, height=3):
    allowed = tuple(tuple(True for _ in range(width)) for _ in range(height))
    spans = tuple(((0, width),) for _ in range(height))
    return Mask(
        kind="rect", width=width, height=height, allowed=allowed, spans=spans,
        font_metrics=FontMetrics(),
    )


def circle_case():
    mask = build_mask(ShapeSpec("circle"), SizeRequest(32), FontMetrics())
    tokens = (
        Token(0, "keyword", "int", 3, 1, 1),
        Token(1, "identifier", "f", 1, 1, 5),
        Token(2, "punctuator", "(", 1, 1, 6),
    )
    placements = (Placement(0, 16, 10), Placement(1, 16, 14), Placement(2, 16, 15))
    return model_for(tokens), plan_for(mask, placements, {(16, 13)})


def split_lines(rendered):
    lines = rendered.source_text.split("\n")
    assert lines[-1] == ""
    return lines[:-1]


# ---------------------------------------------------------------- basic case


def test_circle_row_outputs_a_legal_canvas():
    model, plan = circle_case()
    rendered = render_source(model, plan, FillOptions(), ctx=context())

    lines = split_lines(rendered)
    assert len(lines) == plan.mask.height
    assert all(len(line) <= plan.mask.width for line in lines)
    assert lines[16] == "/*=====*/ int f( " + "//" + "=" * 45
    assert rendered.position_map == {0: (16, 10), 1: (16, 14), 2: (16, 15)}

    allowed = sum(1 for row in plan.mask.allowed for cell in row if cell)
    assert rendered.comment_cells == {"block": 9, "line": allowed - 64 + 47}
    token_ink = 5
    total = token_ink + 9 + rendered.comment_cells["line"]
    assert rendered.coverage == total / allowed
    assert rendered.token_coverage == token_ink / allowed
    assert rendered.comment_coverage == (total - token_ink) / allowed


def test_circle_row_passes_geometry_check():
    model, plan = circle_case()
    rendered = render_source(model, plan, FillOptions(), ctx=context())
    metrics, issues = check_geometry(model, plan, rendered, None, context())
    assert not issues.reasons, issues.reasons
    assert metrics["coverage"] == rendered.coverage
    assert metrics["comment_cells"] == rendered.comment_cells


# ------------------------------------------------------------ gap lengths


@pytest.mark.parametrize("gap", range(1, 11))
def test_internal_gap_between_tokens(gap):
    mask = rect_mask(gap + 3)
    tokens = (
        Token(0, "identifier", "a", 1, 1, 1),
        Token(1, "identifier", "b", 1, 1, 2 + gap),
    )
    plan = plan_for(mask, (Placement(0, 1, 1), Placement(1, 1, 2 + gap)))
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[1]

    if gap < 6:
        expected_gap = " " * gap
    else:
        expected_gap = " " + "/*" + "=" * (gap - 6) + "*/" + " "
    assert row == " a" + expected_gap + "b"


@pytest.mark.parametrize("gap", range(1, 11))
def test_tail_gap_after_a_token(gap):
    mask = rect_mask(1 + gap)
    tokens = (Token(0, "identifier", "a", 1, 1, 1),)
    plan = plan_for(mask, (Placement(0, 1, 0),))
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[1]

    if gap < 3:
        expected_tail = ""  # trailing blanks are trimmed
    else:
        expected_tail = " " + "//" + "=" * (gap - 3)
    assert row == "a" + expected_tail


# ------------------------------------------------------- boundary counter-examples


def test_real_division_sign_keeps_a_space_before_the_comment():
    mask = rect_mask(20)
    tokens = (
        Token(0, "punctuator", "/", 1, 1, 1),
        Token(1, "identifier", "x", 1, 1, 2),
    )
    plan = plan_for(mask, (Placement(0, 1, 5), Placement(1, 1, 12)))
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[1]

    assert row[5] == "/" and row[6] == " " and row[7:11] == "/**/"
    assert row[12] == "x"
    assert "//" not in row[:13]


def test_line_comment_never_swallows_a_later_token():
    cat = build_mask(ShapeSpec("cat"), SizeRequest(32), FontMetrics())
    tokens = (
        Token(0, "keyword", "int", 3, 1, 1),
        Token(1, "identifier", "x", 1, 1, 5),
        Token(2, "punctuator", "=", 1, 1, 6),
        Token(3, "number", "1", 1, 1, 7),
        Token(4, "identifier", "z", 1, 1, 8),
    )
    placements = (
        Placement(0, 13, 3),
        Placement(1, 13, 7),
        Placement(2, 13, 8),
        Placement(3, 13, 9),
        Placement(4, 13, 60),
    )
    plan = plan_for(cat, placements, {(13, 6)})
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[13]

    assert "//" not in row
    assert row[45:59] == "/*" + "=" * 10 + "*/"
    assert row[59] == " " and row[60] == "z"
    metrics, issues = check_geometry(model_for(tokens), plan, rendered, None, context())
    assert not issues.reasons, issues.reasons


def test_cat_multi_span_row_uses_block_then_line():
    cat = build_mask(ShapeSpec("cat"), SizeRequest(32), FontMetrics())
    tokens = (
        Token(0, "keyword", "int", 3, 1, 1),
        Token(1, "identifier", "x", 1, 1, 5),
        Token(2, "punctuator", "=", 1, 1, 6),
        Token(3, "number", "1", 1, 1, 7),
    )
    placements = (
        Placement(0, 13, 3),
        Placement(1, 13, 7),
        Placement(2, 13, 8),
        Placement(3, 13, 9),
    )
    plan = plan_for(cat, placements, {(13, 6)})
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[13]

    assert row == (
        "   int x=1 " + "/*====*/" + "     " + "/*============*/"
        + "     " + "//" + "=" * 14
    )
    metrics, issues = check_geometry(model_for(tokens), plan, rendered, None, context())
    assert not issues.reasons, issues.reasons


# ------------------------------------------------------------- other options


def test_line_comments_can_be_disabled():
    model, plan = circle_case()
    rendered = render_source(model, plan, FillOptions(allow_line_comments=False), ctx=context())
    assert "//" not in rendered.source_text
    assert rendered.comment_cells["line"] == 0
    metrics, issues = check_geometry(model, plan, rendered, None, context())
    assert not issues.reasons, issues.reasons


def test_string_internal_space_is_not_a_gap():
    mask = build_mask(ShapeSpec("circle"), SizeRequest(32), FontMetrics())
    tokens = (Token(0, "string_literal", '"a b"', 5, 1, 1),)
    plan = plan_for(mask, (Placement(0, 16, 10),))
    rendered = render_source(model_for(tokens), plan, FillOptions(), ctx=context())
    row = split_lines(rendered)[16]

    assert row[10:15] == '"a b"'
    allowed = sum(1 for row_cells in mask.allowed for cell in row_cells if cell)
    assert rendered.token_coverage == 4 / allowed
    metrics, issues = check_geometry(model_for(tokens), plan, rendered, None, context())
    assert not issues.reasons, issues.reasons


# ------------------------------------------------------- real A -> C -> D chain


def real_layout_case(text, shape, seconds=60):
    """Run the real A -> C -> D chain and return its artifacts."""
    ctx = context(seconds)
    model = source.analyze_source(text, VerificationProfile(), ctx=ctx)
    plan = fit_layout(
        model,
        ShapeSpec(shape),
        LayoutOptions(),
        mask_builder=build_mask,
        join_checker=source.can_join,
        ctx=ctx,
    )
    rendered = render_source(model, plan, FillOptions(), ctx=ctx)
    return model, plan, rendered, ctx


REAL_SOURCES = {
    "div": "int div(int a,int b){return a/b;}",
    "gcd": "int gcd(int a,int b){if(b==0)return a;return gcd(b,a%b);}",
}


@pytest.mark.parametrize("shape", ("circle", "cat", "code"))
@pytest.mark.parametrize("name", tuple(REAL_SOURCES))
@requires_clang
def test_real_layout_relexes_geometry_and_compiles(name, shape, tmp_path):
    """D's real-layout regression: A's tokens, C's layout, D's output."""
    text = REAL_SOURCES[name]
    model, plan, rendered, ctx = real_layout_case(text, shape)
    lines = split_lines(rendered)

    actual = [token for token in model.profile.lex_source(rendered.source_text, ctx=ctx)
              if not token.is_comment]
    assert [(token.kind, token.spelling) for token in actual] == [
        (token.kind, token.spelling) for token in model.tokens
    ]

    metrics, issues = check_geometry(model, plan, rendered, actual, ctx)
    assert not issues.reasons, issues.reasons
    assert rendered.coverage > 0.9

    # Holes stay blank.
    for feature in ("eye_left", "eye_right", "nose", "code_strokes"):
        for row, col in plan.mask.features.get(feature, ()):
            assert lines[row][col] == " ", (feature, row, col, lines[row])

    # A real division sign keeps a blank before any adjacent comment.
    for token, placement in zip(model.tokens, plan.placements):
        if token.spelling == "/":
            row, col = placement.row, placement.col
            suffix = lines[row][col + 1:]
            assert not suffix.startswith(("//", "/*")), (name, shape, lines[row])

    # Every line comment closes the line; no token or allowed cell follows it.
    for line in lines:
        if "//" in line:
            assert re.search(r"//=*$", line), line

    # Block comments respect the four-cell minimum.
    for line in lines:
        for match in re.finditer(r"/\*=*\*/", line):
            assert len(match.group()) >= 4, line

    program = tmp_path / f"{name}_{shape}.c"
    program.write_text(rendered.source_text, encoding="utf-8")
    build = subprocess.run(
        [CLANG, "-std=c11", "-pedantic-errors", "-x", "c", "-c", str(program),
         "-o", str(program.with_suffix(".o"))],
        capture_output=True, text=True,
        timeout=max(0, ctx.deadline - monotonic()),
    )
    assert build.returncode == 0, build.stderr

