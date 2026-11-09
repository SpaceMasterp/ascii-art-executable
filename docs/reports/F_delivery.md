# Part F CI and documentation follow-up

The workflow implementation is source commit
`97adf33071ec33c4aab303a03ed63eaf3b9d519d`.
[Actions run 42633564163](https://github.com/nukofish/ascii-art-executable/actions/runs/42633564163)
tested PR merge commit `9ea8a2e32e97abc9f464e109032f186ed8310b53`.
The acceptance artifact records this exact commit and `checkout_dirty=false`.

The runner used Ubuntu 24.04, Python 3.12, Clang 18.1.3, libclang 18.1.1 and
pytest 9.2.0. No application or pipeline interface changed. The branch also
includes B's newly merged completion sheet.

| Commit | Input | Command or action | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 9ea8a2e | Full repository | python -m pytest -q | Complete suite passes | 216 passed in 19.07s | Ubuntu full job log | PASS |
| 9ea8a2e | Fixed samples and cat scales | scripts.run_verification and overall passed assertion | passed=true, 144 comparisons | 18 C files, 144 comparisons, scales 1/2/4 PASS | Commit-named Actions artifact | PASS |
| 9ea8a2e | Python native binding | clang.cindex.Index.create() | Bundled library loads | libclang loaded | Environment step | PASS |
| 9ea8a2e | Browser JavaScript | node --check codeart/web/app.js | Valid syntax | Command succeeded | Ubuntu full job log | PASS |
| 9ea8a2e | Base and current collection | scripts/check_test_count.py | No decrease | Base 216, current 216 | Ubuntu full job log | PASS |
| 9ea8a2e | Pure-Python modules | Fast Ubuntu job | Tests pass | 90 passed | Ubuntu fast job log | PASS |
| 9ea8a2e | PR without full-ci label | Optional macOS job | Skip | SKIPPED as configured | Actions job list | NOT_RUN |
| 97adf33 | English and Chinese guides | Read setup and CI tables | Matching commands and dependencies | Both document the same policy and troubleshooting | README.md, README.zh-CN.md | PASS |

Ubuntu runs the complete suite and production acceptance on every workflow
trigger. macos-15 runs only for workflow_dispatch or a full-ci-labelled PR.
Its skipped state in this run is separate from functional acceptance.
The original library and runtime budgets remain in effect.

The artifact contains 18 generated C files and report.json. It includes
per-check states, diagnostics, compiler information, build counts and scaled
cat results. Historical F reports retain their own version anchors.
Other module owners maintain their own completion sheets.
