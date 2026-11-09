# Part F completion checks

The implementation is based on main commit
`6ae7bc6422329db9f7f8847bca57cc7b491d98ab`.
Final validation results and the exact implementation commit are recorded
after the complete test run.

| Input | Command or action | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| Built-in max2, cat | Generate in browser | Four independent PASS checks | Four PASS, coverage 99.77% | F_web_preview.png | PASS |
| Ordinary C11 function | Generate hollow CODE | Token, geometry, compile PASS; behavior NOT_RUN | NO_FIXTURE displayed | Browser validation | PASS |
| Non-ASCII identifier | Generate | UNSUPPORTED_SOURCE with location | Line 1, column 20 | Browser validation | PASS |
| Running gcd sample | Cancel in browser | Task stops; checks remain NOT_RUN | CANCELLED displayed | Browser and HTTP regression | PASS |
| Generated cat | Download source | Exact source bytes, final LF | Download completed | HTTP byte comparison | PASS |
| 684px viewport | Inspect layout | Page fits; code preserves spaces | No page overflow; font loaded; white-space pre | F_web_preview.png | PASS |
| Full suite | python -m pytest -q | All tests pass | Pending final run | F_tests.txt | PENDING |

The shared process utilities are now public in `codeart.procutil`. Old
imports continue through a compatibility module. Export names include
height and realized scale; reports include commit and dirty state.

CI is configured for macos-14 and logs compiler/environment versions.
The collected test-count guard compares against the PR base.

Independent scaled-cat references remain a B/E handoff. E currently checks
32, 64 and 128 rows; proposed 96-row data must be coordinated before use.
