# Module D — comment filling and source output (`codeart/fill.py`)

D writes the tokens that C placed and fills every remaining fillable cell with
the two comment forms E accepts. It never moves, resizes, reorders or rewrites
a token, and it never writes into a hole, a `protected_blank` or another
token's cells.

## Interface

```python
from codeart.fill import render_source

rendered = render_source(
    model,        # SourceModel: tokens with index, spelling, width
    plan,         # LayoutPlan: mask, placements, protected_blanks
    fill_options, # FillOptions(allow_line_comments=True)
    ctx=ctx,      # RunContext; ctx.check() once per row
)
```

| type | fields used |
|---|---|
| `SourceModel` | `tokens` (`index`, `spelling`, `width`) |
| `LayoutPlan` | `mask` (`width`, `height`, `allowed`, `spans`), `placements`, `protected_blanks` |
| `FillOptions` | `allow_line_comments` |
| `RenderedCode` | `source_text`, `position_map`, `coverage`, `token_coverage`, `comment_coverage`, `comment_cells` |

`position_map[token_index] = (row, col)` is copied from `plan.placements`.

## Canvas rules

1. Each placement writes `token.spelling` at `(row, col)`; text cell count is
   `token.width == len(token.spelling)`, so spaces inside a string literal are
   part of the token and are never treated as gaps.
2. `mask.allowed == False` cells stay blank (holes).
3. `protected_blanks` stay blank (mandatory separators chosen by C).
4. A free gap is one contiguous run inside a single span. Gaps never cross a
   hole or another span.
5. Every output row ends with LF, including the last row. Trailing spaces are
   trimmed; a token's trailing spaces are kept.

## Comment grammar

Only two forms are emitted; E's geometry checker matches the same grammar.

### Block comments (interior gaps)

```
/*====...====*/          # at least "/**/" (4 cells), body is only "="
```

- If the gap touches a real token on a side, reserve one blank cell on that
  side; the 4-cell minimum applies to the comment itself, not the blanks.
- After the boundary blanks, a gap needs at least 4 free cells, otherwise it
  stays blank (1–3 leftover cells are allowed to stay blank).
- One block comment fills the whole available run.

### Line comments (row tail only)

```
//====...====            # "//" plus "=" body, at least 2 cells
```

- Only at the tail of the **last span of a row** and only when no real token
  follows on that row.
- The comment must extend to the span end; otherwise a later allowed cell
  would remain after it and E reports `line_comment_tail`.
- After the boundary blank at least 2 free cells are required; a 1-cell tail
  stays blank.
- `FillOptions(allow_line_comments=False)` disables this form completely.

## Coverage

The denominator is the number of `allowed == True` cells; only non-space
characters inside allowed cells count as ink. Token-internal spaces and
boundary blanks are not ink.

```
coverage         = (token ink + block comment cells + line comment cells) / allowed
token_coverage   = token ink / allowed
comment_coverage = (block + line) / allowed
comment_cells    = {"block": block cells, "line": line cells}
```

`comment_cells` counts the comment delimiters too. The values must match E's
re-computation exactly (`geometry_metrics["coverage"]` etc.).

## Errors

A placement that does not match its token, leaves the canvas, covers a
non-fillable cell or overlaps another token makes the plan unusable. D raises
`StageError(Diagnostic(ErrorCode.INTERNAL_ERROR, "render", ...))`; the pipeline
keeps the earlier stages' artifacts. D does not report verification results —
that is E's job.

## Tests

`tests/test_fill.py` covers:

- circle row with three tokens (first acceptance case), geometry check passes;
- internal gap lengths 1–10 and tail gap lengths 1–10;
- real `/` before a comment (boundary blank keeps the division operator);
- a line comment before a later token is refused (block comment instead);
- cat multi-span row: first span block comment, middle span block comment,
  last span line comment;
- `allow_line_comments=False`;
- string literal with an internal space (`"a b"` is one 5-cell token);
- a real `int div(int a, int b){return a/b;}` function: the rendered source is
  re-lexed with Clang and compared token by token, then compiled with
  `clang -std=c11 -pedantic-errors -c`.

## Known limits

- One comment per gap; a gap is not split into several comments.
- Line comments are single-line by construction; no backslash continuation.
- Coverage is a layout consequence: if C leaves small spans, D cannot raise it
  without breaking the boundary rules.
