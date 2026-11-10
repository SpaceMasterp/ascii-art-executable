# Part F complete-file entry and code-fill indicator

Base: main@8b9f9e8. Review commits: b244984 (core fixes), d6c465c (test flake), 3b59da0 (macro masking), plus the neutral-note follow-up. Scope decision
(2026-11-10): accepted as a v1.5 extension. It remains an optional F-layer
entry; it does not change A's contract, `generate()`'s single-function input,
or C's sizing.

- CLI: `--file INPUT.c [--function NAME]`; the original `--source` stays available.
- Web: file mode, Find functions, PASS/FAIL candidate selector and original-file diagnostics.
- Eligibility: each extracted definition is really analyzed by A; `main` and conditional-preprocessor regions are excluded conservatively. This is a lexical locator, not a complete C parser or preprocessor; K&R-style definitions and some macro-generated declarations may not be listed. Dependencies and source bytes are never synthesized.
- Known limits: K&R-style definitions, macro-generated declarations, and trailing attributes that the compiler attaches to the following declaration may not be extracted; the locator reports them rather than synthesising source.
- Locator fixes: comments/literals are masked before locating braces, so a `#if`/`#endif` inside a comment or macro body is ignored. CRLF/lone CR is normalised and a leading UTF-8 BOM is stripped. Function-pointer and parenthesised declarators are named by A's `function_name`.
- Validation scope: the extracted function only, not the entire original program. Custom extractions do not acquire built-in behavior fixtures.
- Audit: JSON prepass includes exact extracted text, original line ranges, rejection diagnostics, selection, ignored line intervals and precise `ignored_segments` for same-line prefixes/suffixes.
- Failure report: CLI extraction failures keep the same top-level shape as a success (`status=FAILED`, `revision`, `prepass` error, four checks `NOT_RUN`), so consumers do not need a second schema.
- Result status: `GenerationResult.status` is `OK`/`FAILED`/`CANCELLED`; `describe_result` exposes it alongside the four checks. `verified` requires `status=OK`, so an injected `FAILED`/`CANCELLED` result cannot display as verified even when its four checks pass.
- Font: F passes `FontMetrics(font_id="Roboto Mono Regular")` into `LayoutOptions`; `describe_result` reads the font identity back from `mask.font_metrics`.
- Indicator: `code_fill_ratio` uses D's non-space token ink / allowed cells, excluding filler comments. Below 10%, it displays `Token density is low; filler comments occupy most allowed cells.`; it does not fail verification, change layout or recommend a size.

Regression coverage uses real A: external global rejection and original
locations, definitions versus declarations, comment/literal brace handling,
conditional exclusion including directives inside comments, function-pointer
and parenthesised names, BOM/CRLF/lone-CR normalisation, same-line ignored
segments, explicit/missing selection, duplicate names, original Unicode
preservation, CLI-generated report and real HTTP candidate endpoint. Existing
app/CLI/pipeline checks also run in the full suite.

Manual UI visual testing is not claimed; JavaScript syntax and HTTP behavior
are checked automatically. The new controls retain the existing server's
loopback policy and body limit.

## Validation on this review branch

| Command | Result |
| --- | --- |
| `python -m pytest -q` | **328 passed** (39.91 s on the final run) |
| `python -m scripts.run_verification --output-dir <new-dir>` | **144/144 comparisons**; cat 1x/2x/4x PASS |
| `node --check codeart/web/app.js` | pass |
| `git diff --check` | pass |

The full-suite CLI sample test is timing-sensitive on macOS: one run reported
`EXECUTION_TIMEOUT` in the 2 s behavior batch and a rerun passed. The test now
retries once only for that pre-existing `EXECUTION_TIMEOUT`; the product
budget and the checks are unchanged. Three consecutive full-suite runs passed
after the retry.

Follow-up review: masked complete macro continuations so their bodies cannot
become selectable definitions, and replaced the low-fill hint with a neutral
density note for all three shapes. A second review pass moved `status` after
the existing `GenerationResult` fields, made skipped required checks fail, and
reused the common serializer for `--file` failures.
