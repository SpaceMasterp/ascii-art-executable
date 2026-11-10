# Part F complete-file entry and code-fill indicator

Base: main@8b9f9e8. This follow-up does not change A's contract or C's sizing.

- CLI: `--file INPUT.c [--function NAME]`; the original `--source` stays available.
- Web: file mode, Find functions, PASS/FAIL candidate selector and original-file diagnostics.
- Eligibility: each extracted definition is really analyzed by A; main and conditional-preprocessor regions are excluded conservatively. This is a lexical extractor, not a complete C parser or preprocessor; exotic declarators may not be listed. Dependencies and source bytes are never synthesized.
- Validation scope: the extracted function only, not the entire original program. Custom extractions do not acquire built-in behavior fixtures.
- Audit: JSON prepass includes exact extracted text, original line ranges, rejection diagnostics, selection, ignored line intervals and reasons. Ignored intervals describe lines outside the selected definition; if definitions share a line, candidate text is the precise extraction boundary.
- Indicator: `code_fill_ratio` uses D's non-space token ink / allowed cells, excluding filler comments; below 0.10 displays advice without changing verification or layout.

Regression coverage uses real A: external global rejection and original locations, definitions versus declarations, comment/literal brace handling, explicit/missing selection, conditional exclusion, original Unicode preservation, CLI-generated report and real HTTP candidate endpoint. Existing app/CLI/pipeline checks also run in the full suite.

Manual UI visual testing is not claimed; JavaScript syntax and HTTP behavior are checked automatically. The new controls retain the existing server's loopback policy and body limit.
