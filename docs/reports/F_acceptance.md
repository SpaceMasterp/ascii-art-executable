# Part F completion checks

Code under test is commit `a6b3662f0f964064a8d2665b34fe1b0e102805e2`, based on
main `6ae7bc6422329db9f7f8847bca57cc7b491d98ab`.
Generated evidence files were uncommitted during the run; the environment
and JSON reports record that dirty state. The code files matched this commit.
Test date is 9 November 2026 in Asia/Hong_Kong.

Environment is Python 3.14.7, Apple Clang 21.0.0, libclang 18.1.1 and
pytest 9.2.0 on macOS arm64. See `F_environment.json`.


| Input | Command or action | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Built-in max2, cat | Generate in browser | Four independent PASS checks | Four PASS, coverage 99.77% | F_web_preview.png | PASS |
| Ordinary C11 function | Generate hollow CODE | Token, geometry, compile PASS; behavior NOT_RUN | NO_FIXTURE displayed | Browser validation | PASS |
| Non-ASCII identifier | Generate | UNSUPPORTED_SOURCE with location | Line 1, column 20 | Browser validation | PASS |
| Running gcd sample | Cancel in browser | Task stops; checks remain NOT_RUN | CANCELLED displayed | Browser and HTTP regression | PASS |
| Generated cat | Download source | Exact source bytes, final LF | Download completed | HTTP byte comparison | PASS |
| 684px viewport | Inspect layout | Page fits; code preserves spaces | No page overflow; font loaded; white-space pre | F_web_preview.png | PASS |
| Full suite | python -m pytest -q | All tests pass | 168 passed in 25.15s | F_tests.txt | PASS |

The shared process utilities are now public in `codeart.procutil`. Old
imports continue through a compatibility module. Export names include
height and realized scale; reports include commit and dirty state.

CI is configured for macos-14 and logs compiler/environment versions.
The collected test-count guard compares against the PR base.

Independent scaled-cat references remain a B/E handoff. E currently checks
32, 64 and 128 rows; proposed 96-row data must be coordinated before use.

## Additional evidence

| Input | Command or action | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Built-in max2, cat, scale 1 | CLI sample with source and report export | Four PASS; h32 | Four PASS | fixed/case_max2_cat_h32_s1.json | PASS |
| Built-in max2, cat, scale 1.5 | CLI sample with --scale 1.5 | Four PASS; h48 | Four PASS | scaled/case_max2_cat_h48_s1.5.json | PASS |
| __LINE__ function | Generate through production pipeline | UNSUPPORTED_SOURCE with location | Correct code and location | errors/line_macro.json | PASS |
| 1502-cell string token | Generate hollow CODE | LAYOUT_LIMIT with history | Eight recorded attempts | errors/layout_limit.json | PASS |
| Non-ASCII identifier | Generate through production pipeline | UNSUPPORTED_SOURCE with location | Correct code and location | errors/non_ascii.json | PASS |
| Base main versus F | scripts/check_test_count.py with BASE_SHA | Test count does not decrease | 154 to 168 | Local count guard | PASS |

Earlier local attempts encountered the existing 2-second behavior-program
limit on isolated executions. The final full run passed under the original
budgets. No resource limits or failure checks were relaxed.

The remote macOS workflow is configured in this change. Its actual result
must be checked on the pull request; local validation does not establish
the remote runner result.
