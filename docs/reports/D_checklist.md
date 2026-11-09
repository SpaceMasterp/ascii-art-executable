# Part D — completion checklist

- **Evidence anchor:** `main@6ae7bc6`
- **Host:** macOS 26.5.1 arm64
- **Python:** 3.11.16
- **clang:** Apple clang 21.0.0
- **Branch:** `part-d-real-layout`
- **Artifacts:** `docs/reports/case_<function>_<shape>_h<rows>_s<scale>.c`
- **Case table:** `docs/reports/D_cases.md`
- **Manifest:** `docs/reports/D_manifest.csv`
- **Generator:** `python scripts/generate_d_reports.py`

## DoD table

| Case | Commit | Input | Command | Expected | Actual | Evidence | Conclusion |
|---|---|---|---|---|---|---|---|
| Fake-layout boundary tests | `main@6ae7bc6` | masks/tokens built in the test | `python -m pytest tests/test_fill.py -q` | all boundary tests pass | 33 passed | `tests/test_fill.py` | PASS |
| Real A→C→D regression | `main@6ae7bc6` | `div`, `gcd` × circle/cat/code | `python -m pytest tests/test_fill.py -q` | 6 real-layout cases pass | 6 passed | `tests/test_fill.py::test_real_layout_relexes_geometry_and_compiles` | PASS |
| 18 ordinary-input outputs | `main@6ae7bc6` | `max2`, `min2`, `clamp`, `absdiff`, `gcd`, `sum_to_n` × 3 shapes | `python scripts/generate_d_reports.py` | 18/18 token/geometry/compile PASS | 18/18 PASS; behavior 18/18 `NOT_RUN (NO_FIXTURE)` | `docs/reports/D_cases.md` | PASS |
| Division adjacency | `main@6ae7bc6` | `sum_to_n` (`(n + 1) / 2`), `div` | generator + `tests/test_fill.py` | no `//` or `/*` immediately after a real `/` | no violation found | `case_sum_to_n_*_h32_s1.c`, real-layout test | PASS |
| Short gaps | `main@6ae7bc6` | internal gaps 1–10, tail gaps 1–10 | `python -m pytest tests/test_fill.py -q` | gaps <4 stay blank; `/**/` at 4 | assertions pass | `tests/test_fill.py` gap tests | PASS |
| Line-end comments | `main@6ae7bc6` | all 18 outputs | `python scripts/generate_d_reports.py` | every `//` reaches the row end | `line_tail_ok = YES` in 18/18 | `docs/reports/D_cases.md` | PASS |
| Hole blanks | `main@6ae7bc6` | cat eyes/nose, hollow CODE strokes | `python scripts/generate_d_reports.py` | hole ink = 0 | 0 in 18/18 | `docs/reports/D_manifest.csv` | PASS |
| Coverage split | `main@6ae7bc6` | all 18 outputs | `python scripts/generate_d_reports.py` | token / block / line contributions reported | three columns populated in 18/18 | `docs/reports/D_manifest.csv` | PASS |
| Independent compile | `main@6ae7bc6` | all 18 outputs | `python scripts/generate_d_reports.py` | `clang -std=c11 -pedantic-errors -c` rc 0 | rc 0 in 18/18 | `docs/reports/D_cases.md` | PASS |

## Full test run

`python -m pytest -q` on this snapshot: **159 passed**, including **33** in
`tests/test_fill.py` (27 fake-layout + 6 real-layout).

## Key numbers

- coverage: **0.9886 – 0.9990**
- token coverage: **0.0082 – 0.0555**
- block-comment coverage: **0.0000 – 0.5123**
- line-comment coverage: **0.4687 – 0.9764**
- hole ink: **0**
- shortest block comment: **5** cells
- line comments: **18/18** reach the row end
- layout attempts / scale: **1 / 1**
- independent `clang -c`: **18/18 rc 0**

## Known limits

- Ordinary input has no behavior fixture, so behavior is `NOT_RUN`; the 144
  comparisons belong to E's builtin-fixture matrix.
- These 18 inputs all fit at the base height (`attempts = 1`, `scale = 1`);
  automatic scaling is exercised by C/E, not by this table.
- Coverage is split into token / block-comment / line-comment contributions
  in `D_manifest.csv`; the denominator is the number of allowed cells.
- D never changes the layout; a poor coverage value is a layout consequence,
  not something D may fix by filling outside the rules.
