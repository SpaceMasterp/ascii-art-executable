# Acceptance evidence

Each report names its tested commit and indicates uncommitted changes.
Use the columns Commit, Input, Command, Expected, Actual, Evidence and Status.
Keep PASS, FAIL and NOT_RUN distinct.

Store fixed-height evidence under `fixed/` and growth demonstrations under
`scaled/`. Name source files
`case_<function>_<shape>_h<rows>_s<scale>.c` and pair them with JSON reports.
Do not overwrite an earlier run when the source or revision differs.

## Handoffs

- B supplies independent geometry reference JSON and assertion definitions.
  E currently checks scales 1, 2 and 4, corresponding to heights 32, 64 and
  128. A proposed h96 fixture is scale 3 and must be explicitly coordinated
  with E's scale set before replacing an h128 reference.
- C owns the narrow-span hollow CODE and longest-token growth regressions.
- D reports token, block-comment and line-comment contributions separately.
- E distinguishes fixed h32 behavior evidence from grown cases, and records
  `OUTPUT_TOO_LARGE` as NOT_RUN due to size. The current builtin registry
  provides exact fixture identity. Moving builtin sources to separate C
  files is a follow-up for E that must preserve that identity and input set.
- F owns local operation, preview, exports, environment setup and CI.

## Error demonstrations

1. Non-ASCII input produces `UNSUPPORTED_SOURCE` with source line and column.
2. A function using `__LINE__` produces `UNSUPPORTED_SOURCE` without requiring
   a preprocessing directive.
3. A token wider than the configured layout can accommodate produces
   `LAYOUT_LIMIT` with `diagnostic.details["attempt_history"]`.

The public `codeart.procutil` module is shared by A and E.
