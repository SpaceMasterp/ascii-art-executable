# Part A completion checks (phase 2)

Scope of this round: input limits, lexical boundaries and diagnostics for the
source analyzer, the English module guide, and closing the private dependency on
Part E's process module.

Base: `main` at `5628b4ee15c47b9eec943fc3398cbf10dff227f9`, after #27 moved the
full suite to Ubuntu and #26 added the bilingual guides and the report index.
The branch was rebased onto that commit; the evidence below was regenerated on
the rebased tree (this checkout is a source archive, so `revision_info()`
records `null` and the base SHA is named explicitly).

Environment: Python 3.12.14, libclang 18.1.1, pytest 9.2.0, macOS arm64.
The local compiler is the clang 19 driver shipped with zig 0.14.1 because this
machine has no Xcode command line tools; CI uses the Ubuntu `clang` package and
pinned `libclang==18.1.1`. See [A_environment.json](a_source/A_environment.json).

CI note: the default pull-request job (`Fast pure-Python checks`) is a fixed file
list that does not include Part A's suites, so the merge gate is the
`Full checks (ubuntu, clang + node)` job, which runs on `main` pushes, manual
dispatch and pull requests labelled `full-ci`.

## What changed

| Area | Change |
| --- | --- |
| Diagnostics | Predefined macro names are checked on raw identifier tokens, so `__LINE__`, `__FILE__`, `__COUNTER__` and friends are rejected without any directive and with an exact position. The libclang macro-instantiation cursor stays as the fallback for implementation macros such as `__INT_MAX__`. |
| Input limits | GNU extension keywords (`__asm__`, `__attribute__`, `__extension__`, `__int128`, `__thread`) are rejected when libclang lexes them as keywords; extension names used as ordinary identifiers stay legal. Line splicing and trigraphs now report separate messages with positions. |
| Compiler errors | An input that parses but fails object compilation carries the first `input.c:line:column` from the compiler output instead of only stderr text. |
| Boundaries | `can_join` documents and tests the whole-run rule; an empty spelling is a `ValueError` rather than a silent lexer call. |
| Ownership | `codeart.procutil` is the only process dependency of A; `source.__all__` exports exactly four names; `tests/test_module_boundaries.py` fails if a private cross-owner import returns. |
| Docs | `docs/modules/source.md` rewritten as the English module guide, including the full diagnostics table and the known limits. The reports index gains a Part A entry, and both READMEs now state the macro-name and extension rule in the input-scope paragraph. |

`BuildSession` stays mode-agnostic: an earlier draft validated build modes, which
would have broken E's `original`/`rendered` builds — the exact failure this
round is meant to prevent.

## Completion checks

| Commit | Input | Command | Expected | Actual | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 5628b4e | A test suites (4 files) | `python -m pytest -q tests/test_source.py tests/test_source_lexer.py tests/test_source_boundaries.py tests/test_module_boundaries.py` | All pass | 121 passed in 23.96 s | A_tests.txt | PASS |
| 5628b4e | Ten documented diagnostics | `python -m scripts.check_source_diagnostics --output docs/reports/a_source/A_diagnostics.json` | Every case returns its declared code and position | 10/10 PASS, exit 0 | A_diagnostics.json, A_diagnostics_summary.txt | PASS |
| 5628b4e | `int f(void){return __LINE__;}` | analyze | `UNSUPPORTED_SOURCE` at 1:20, no `#` needed | `UNSUPPORTED_SOURCE` 1:20 | A_diagnostics.json | PASS |
| 5628b4e | `int f(void){ return __FILE__[0] + __COUNTER__; }` | analyze | `UNSUPPORTED_SOURCE` at the first macro | `UNSUPPORTED_SOURCE` 1:21 | A_diagnostics.json | PASS |
| 5628b4e | Non-ASCII identifier on line 2 | analyze | `UNSUPPORTED_SOURCE` at 2:10 | `UNSUPPORTED_SOURCE` 2:10 | A_diagnostics.json | PASS |
| 5628b4e | `__asm__`, `__attribute__`, `__extension__`, `__int128`, `__thread` | analyze | `UNSUPPORTED_SOURCE` at 1:15, keyword rule | All five rejected at 1:15 | test_source_boundaries.py | PASS |
| 5628b4e | `int typeof = 1; return typeof;` | analyze | Accepted: identifier, not a keyword | Accepted, function `f` | test_source_boundaries.py | PASS |
| 5628b4e | Trigraph and line splice | analyze | Positioned `UNSUPPORTED_SOURCE` | 1:23 and 1:17 | A_diagnostics.json | PASS |
| 5628b4e | CRLF source with a comment | analyze | Positions preserved, no CR in normalized text | Token at 2:1, comment kept | test_source_boundaries.py | PASS |
| 5628b4e | Fake object-build failure with `input.c:3:5: error:` | analyze | `INVALID_SOURCE` at 3:5 | `INVALID_SOURCE` 3:5 | test_source_boundaries.py | PASS |
| 5628b4e | `can_join` matrix (12 pairs, three dots, empty run) | pytest | Joins only when the whole run re-lexes identically | All cases as declared | test_source_boundaries.py | PASS |
| 5628b4e | Import graph of `codeart` | pytest | A's private modules have one importer; no `_verification_process` user | 6 checks pass | test_module_boundaries.py | PASS |
| 5628b4e | Missing compiler | analyze with `compiler="codeart-missing-compiler"` | `DEPENDENCY_UNAVAILABLE` | `DEPENDENCY_UNAVAILABLE`, no location | A_diagnostics.json | PASS |

## Notes for other owners

- **E**: the process helpers are used through `codeart.procutil` only. The macro
  table and the extension keyword rule are additive; a source that was accepted
  before and contains none of those names behaves as before. `can_join` keeps
  its signature and caching behaviour. The six builtin functions still pass the
  full pipeline matrix in `tests/test_source.py` (18 cases, four PASS checks,
  144 behavior comparisons).
- **B/C/D**: no contract change. `Token.width` is still `len(spelling)` and
  positions are still one-based on the original text.
- **F**: `source.__all__` is the public surface; error codes stay inside
  `ErrorCode`. Diagnostics for `INVALID_SOURCE` may now carry a compiler line and
  column, so a UI that shows "line/column present or absent" keeps working.

## Observation (local environment, not a Part A defect)

Cold-start runs in this sandbox occasionally fail one matrix case with
`DEPENDENCY_UNAVAILABLE: Cannot identify compiler ...`. The cause is the local
zig-provided clang driver returning a nonzero `clang --version` while its cache
warms up; the same run passes on every repeat, and all ten diagnostics cases are
unaffected. Also, the `tests/test_verify.py` failures on this machine come from a helper
that calls `clang -Xclang -dump-raw-tokens`, which the zig driver does not
accept. The macOS CI job uses Apple Clang for both, so its result — not this
sandbox — is the authoritative one.

## Reproduction

```sh
python -m pytest -q tests/test_source.py tests/test_source_lexer.py \
  tests/test_source_boundaries.py tests/test_module_boundaries.py
python -m scripts.check_source_diagnostics --output docs/reports/a_source/A_diagnostics.json
python -m codeart.environment
```
