"""Conservatively extract file-scope definitions; A alone decides eligibility.

This is not a C preprocessor. Conditional regions and ambiguous declarations
are deliberately left to A or reported as ineligible, never rewritten.
"""
from dataclasses import dataclass, field
import re
from time import monotonic

from .contracts import RunContext, StageError
from .source import analyze_source

SCOPE = "Only the extracted function is verified, not the entire input program."


@dataclass
class FunctionCandidate:
    name: str
    start_line: int
    end_line: int
    source_text: str
    a_status: str
    diagnostic: dict | None = None


@dataclass
class PrepassResult:
    candidates: list = field(default_factory=list)
    ignored_lines: list = field(default_factory=list)
    selected: str | None = None
    validation_scope: str = SCOPE
    error: str | None = None


def _masked(text):
    # Preserve offsets and newlines while hiding comments and literal braces.
    pattern = r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    return re.sub(pattern, lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), text, flags=re.S)


def inspect_file(text, function=None, *, analyzer=analyze_source, timeout_s=30):
    """Return raw candidates with A diagnostics mapped to original file lines."""
    result = PrepassResult()
    ctx = RunContext(monotonic() + timeout_s)
    masked = _masked(text)
    # Hide directive lines, including continuations, only for locating braces.
    masked = re.sub(r'^\s*#[^\n]*(?:\\\n[^\n]*)*',
                    lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), masked, flags=re.M)
    depth = 0
    boundary = 0
    opening = None
    conditional_lines = set()
    level = 0
    for n, line in enumerate(text.splitlines(), 1):
        if re.match(r'\s*#\s*(if|ifdef|ifndef)\b', line): level += 1
        if level: conditional_lines.add(n)
        if re.match(r'\s*#\s*endif\b', line): level = max(0, level - 1)
    for i, ch in enumerate(masked):
        if ch == '{':
            if depth == 0:
                header = masked[boundary:i]
                match = re.search(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*\([^;{}]*\)\s*$', header)
                opening = (boundary, match[1]) if match and '=' not in header else None
            depth += 1
        elif ch == '}':
            depth = max(0, depth - 1)
            if depth == 0:
                if opening:
                    start, name = opening
                    while start < i and masked[start].isspace(): start += 1
                    line_start = text.rfind('\n', 0, start) + 1
                    column_offset = start - line_start
                    if not text[line_start:start].strip():
                        start = line_start
                        column_offset = 0
                    line = text.count('\n', 0, start) + 1
                    end = text.count('\n', 0, i) + 1
                    raw = text[start:i+1]
                    diagnostic = None
                    if name == 'main' or conditional_lines.intersection(range(line, end+1)):
                        diagnostic = {'code': 'UNSUPPORTED_SOURCE', 'line': line, 'column': 1,
                                      'message': 'main is excluded' if name == 'main' else 'Conditional preprocessing region is not extracted'}
                    else:
                        try:
                            analyzer(raw, ctx=ctx)
                        except StageError as exc:
                            d = exc.diagnostic
                            diagnostic = {'code': d.code.value, 'line': line + d.line - 1 if d.line else None,
                                          'column': d.column + column_offset if d.column and d.line == 1 else d.column, 'message': d.message}
                    result.candidates.append(FunctionCandidate(name, line, end, raw, 'FAIL' if diagnostic else 'PASS', diagnostic))
                boundary = i+1
                opening = None
        elif ch == ';' and depth == 0:
            boundary = i+1
    eligible = [c for c in result.candidates if c.a_status == 'PASS' and (function is None or c.name == function)]
    if len(eligible) > 1 and function:
        result.error = 'AMBIGUOUS_FUNCTION'
    elif eligible:
        chosen = eligible[0]
        result.selected = chosen.name
    else:
        result.error = 'NO_ELIGIBLE_FUNCTION'
    chosen = next((c for c in eligible if c.name == result.selected), None)
    total = len(text.splitlines())
    for a, b in ((1, chosen.start_line-1), (chosen.end_line+1, total)) if chosen else ((1, total),):
        if a <= b:
            result.ignored_lines.append({'start_line': a, 'end_line': b, 'reason': 'Outside the selected function' if chosen else 'No function selected'})
    return result


def selected_source(result):
    return next(c.source_text for c in result.candidates if c.name == result.selected and c.a_status == 'PASS')
