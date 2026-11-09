# Part F validation after integrating Part E

Code under test is commit
`42a61c78756f543dfd865ff8fc4ffa96474fcd67`, which includes main
`3dab181abde97f9389c61a60c067558c782c16d5`.
The implementation checkout was clean when formal acceptance and environment
capture ran. Evidence files were copied into this report after validation.

The production process utilities, lexer cleanup, verification context and
regression imports match main's Part E implementation. F retains compatibility
imports at the former process-module path.

| Commit | Input | Command | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 42a61c7 | Complete repository | python -m pytest -q | All tests pass | 196 passed in 24.85s | F_after_E_tests.txt | PASS |
| 42a61c7 | Base main test collection | BASE_SHA=3dab181… python scripts/check_test_count.py | No decrease | Base 182, current 196 | Local guard output | PASS |
| 42a61c7 | Six built-in functions and three shapes | python -m scripts.run_verification --output-dir ../f-after-e-fixed | 18 h32 outputs; four passing checks | 18 outputs, 144 comparisons, fixed matrix PASS | f_after_e/fixed/report.json | PASS |
| 42a61c7 | Original process-module imports | tests/test_procutil.py | Shared identities preserved | Compatibility test passed | Full test log | PASS |

The formal report records `checkout_dirty=false`, 18 rendered object builds,
6 original executable builds and 18 rendered executable builds.
Scaled-cat acceptance remains NOT_RUN with MISSING_REFERENCE. B's merged
h32/h64/h96 data still needs alignment with E's h32/h64/h128 acceptance set.

**Later status / 后续状态** (appended; the paragraphs above are kept as the
original record and are not rewritten)

PR #21 (commit `94cd53d`) connected B's h32/h64/h128 reference data to E's
scaled-cat acceptance, so the MISSING_REFERENCE state above no longer applies.
The comparison rules are: `base_area` is always taken from h32,
`area_at_scale = base_area × scale²`, `center` uses the current scale's
centroid with 0.5 subtracted to convert it to grid-index means, and
`ear_gap_rows` uses the current scale's value. Current result:
`scripts/run_verification.py` prints `Scaled cat: 1x PASS, 2x PASS, 4x PASS`
and `PASS fixed matrix (144/144 comparisons)`. The rest of this document
remains the record of the original commit; re-run the acceptance to judge a
newer version.

The earlier F acceptance document and screenshot remain historical evidence
for the unchanged browser interface. The HTTP and CLI tests passed again
against the integrated process utilities.
