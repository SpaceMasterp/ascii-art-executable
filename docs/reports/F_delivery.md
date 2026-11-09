# Part F CI and documentation follow-up

Functional baseline is main
`4b8b5b8b29e761e5e808b5dfc69acb4b4d004f94`.
Its clean-checkout production acceptance passed the 18 fixed cases, 144 behavior
comparisons and cat scales 1, 2 and 4; the local full suite passed 216 tests.

This follow-up changes the CI baseline and documentation. The application and
pipeline interfaces are unchanged. Ubuntu 24.04 runs the complete suite and
production acceptance on each trigger. macos-15 is an additional manual or
full-ci-labelled PR check. The Python libclang package remains pinned to 18.1.1.

| Input | Command or action | Expected | Evidence |
| --- | --- | --- | --- |
| Latest branch | Ubuntu full job | Complete tests pass | PR Actions run |
| Fixed and scaled-cat acceptance | scripts.run_verification plus report passed check | passed=true, 144 comparisons | Commit-named Actions artifact |
| Browser script | node --check codeart/web/app.js | Syntax accepted | Ubuntu job log |
| Base and current collection | scripts/check_test_count.py | Current count is not lower | Ubuntu job log |
| Installation guide | English and Chinese README | Matching commands, dependencies and CI policy | README.md, README.zh-CN.md |

The workflow records the compiler version and the complete environment report.
The acceptance artifact carries the exact commit and checkout state.
Historical F reports remain anchored to their original implementations.
Owner completion sheets for other modules are maintained by those owners.
