# Part C completion checks

Code under test is the C layout engine on branch `c`, based on
main `0d49651`. This round implements the v1.5 P0 item **initial size
estimation**: the engine builds a scale-1 base mask and starts the first
attempt at a measured scale instead of always starting at scale 1. The public
`contracts.py` signatures are unchanged; the new logic lives in
`codeart/layout.py` plus updated regression tests in `tests/test_layout.py`.

Test date is 11 November 2026 in Asia/Hong_Kong.

Environment is Python 3.13.16, pytest 9.2.0 on Windows 11 (AMD64). libclang is
not installed on this machine, so the Clang-dependent source tests cannot run
locally; they report `DEPENDENCY_UNAVAILABLE` and are validated by the CI
(macos-15, libclang 18.1.1). The C-owned `tests/test_layout.py` does not depend
on libclang and runs fully here. See `C_environment.json`.

The full suite on this machine is `112 failed, 185 passed, 31 skipped`, both
before and after this change, with an identical failing set: every failure is
pre-existing (missing libclang, Windows symlink privilege, CRLF fixtures), so
the change introduces no new regression.

## The implemented decision

A scale-1 base mask is built first. From it the engine measures the longest
fillable span `U` and the total fillable cells `A`; from the tokens it takes
the longest token `L` and the total token width `T`. The first attempt starts at

`s_start = max(1, initial_scale, L/U, sqrt(T/(eta*A)))` with `eta = 0.75`.

The loop then requests `ceil(base_height_rows * s_start * growth_factor**
attempt)`. `s_start` is never below 1, so the estimate only moves the start up.
A failure during the base mask build (timeout/cancel) still attaches the
`attempt_history` key.

| Commit | Input | Command | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 0d49651 | C-owned suite | `python -m pytest tests/test_layout.py -q` | All layout tests pass | 23 passed | C_tests.txt | PASS |
| 0d49651 | Width-12 token, circle h=4 | `test_longest_token_gets_a_large_enough_start_via_estimate` | Width estimate (L/U=1.5) moves first attempt to h=6, fits without small retries | 1 attempt, h=6, token in a 12-cell span, geometry PASS | C_tests.txt | PASS |
| 0d49651 | Width-801 token, limits 800x600 | `test_long_token_that_never_fits_raises_layout_limit_with_history` | Token wider than max_columns: LAYOUT_LIMIT with history | LAYOUT_LIMIT, canvas-limit record (h=401, w=802) | C_tests.txt | PASS |
| 0d49651 | Width-10 token, fixed 5-wide fake builder | `test_exhausted_attempts_raise_layout_limit_with_history` | Token never fits, all attempts exhausted | 3 failed attempts, all point at token 0 | C_tests.txt | PASS |
| 0d49651 | 60 tokens, circle h=6 | `test_growth_retries_until_the_tokens_fit` | Growth by 1.25, bounded, records failures then success | bounded attempts, last record success | C_tests.txt | PASS |
| 0d49651 | 200 tokens, max_columns=10 | `test_canvas_size_limit_raises_layout_limit` | Growth rejected at the column limit | LAYOUT_LIMIT, "canvas limits" reason | C_tests.txt | PASS |
| 0d49651 | Join checker sets the cancel event | `test_cancellation_in_join_checker_stops_layout` | Packing stops on cancellation | CANCELLED | C_tests.txt | PASS |
| 0d49651 | Slow checker, layout_timeout_s=0.05 | `test_layout_stage_timeout_raises_layout_timeout` | Stage timeout reported with history | LAYOUT_TIMEOUT with history | C_tests.txt | PASS |
| 0d49651 | Fake builder, 2s stage vs 100s pipeline | `test_mask_building_respects_layout_stage_budget` | Budget enforced during base mask generation | Stops at 2s, not 10s, history key present | C_tests.txt | PASS |
| 0d49651 | 1200 width-1 tokens, CODE 178x32 | `test_code_mask_packs_tokens_across_many_short_spans` | Reach fragmented rows and flow across spans | All 1200 placed; tokens occupy multi-span rows | C_tests.txt | PASS |
| 0d49651 | initial_scale=1.01, base 32 | `test_actual_scale_reflects_rounded_height` | Scale from rounded height | 33/32 = 1.03125 | C_tests.txt | PASS |

## Coverage of the assigned checks

| Assigned item | Where verified | Status |
| --- | --- | --- |
| Initial size estimate (s_start) | width-12 estimate test; growth/timeout tests | PASS |
| Long tokens | width-12 estimate test; width-801 impossible-canvas test | PASS |
| Multi-span layout | CODE 178x32 short-span test; cat multi-span geometry | PASS |
| Automatic growth (1.25, max 12) | growth and exhausted-attempt tests | PASS |
| Size limits (max_columns=800, max_rows=600) | canvas limit and width-801 tests | PASS |
| Timeout (layout_timeout_s) | stage timeout and shared-deadline tests | PASS |
| Cancellation (cancel_event) | join-checker cancellation test | PASS |
| Attempt history | success and failure histories asserted in every case | PASS |

## Known limits

- Packing is greedy in reading order, not globally optimal.
- The estimate never starts below scale 1, so the minimum is still the base
  height (32 rows); it cannot shrink the canvas for very short code.
- A token wider than the largest span the canvas can provide cannot be split
  and always fails with `LAYOUT_LIMIT`.
- The local machine lacks libclang; the Clang-dependent suite is confirmed by
  CI rather than on this machine.
