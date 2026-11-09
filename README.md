# Code Art Studio

Reformat one self-contained C11 function into a circle, a cat head or hollow
CODE while preserving effective tokens. Python implements the pipeline,
libclang checks source structure and lexical boundaries, and Clang compiles
the output. Token, geometry, compile and behavior checks are reported separately.

## Install

Use Python 3.10 or later and a C11 Clang compiler. The pinned libclang Python
package includes its native library. On macOS, install Apple's command-line
developer tools if `clang --version` is unavailable. On Ubuntu 24.04, install
`clang-18` and put `/usr/lib/llvm-18/bin` on PATH.

From the repository root on macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m codeart.environment
python -m pytest -q
```

Production use only needs `requirements.txt`. Development dependencies add
pytest. Record the output of `python -m codeart.environment` with any bug
report. The CI baseline is macos-15, Python 3.12, the runner's Apple Clang, libclang
18.1.1 and pytest 9.2.0. Local validation also uses macOS, Python 3.14 and
Apple Clang. The exact local versions are available in the environment report.

## Local web interface

```sh
python -m codeart.app
```

Open **http://127.0.0.1:8765**. Use `--port 8766` if that port is occupied.

1. Choose one of the six built-in functions, open a `.c` file, or paste a function.
2. Select circle, cat or hollow CODE and an initial scale from 1 to 4.
3. Generate and inspect the original source, artwork, actual grid size, scale,
   attempts, coverage, elapsed time and four independent check results.
4. Review diagnostics and layout history. Download the source or JSON report.
5. Use Cancel while a generation is running. Completed results are retained.

The application binds to loopback and processes one generation at a time.
Closing its terminal with Ctrl+C requests cancellation and shuts it down.
It retains the latest five runs in memory. Downloads must be saved before
those runs are evicted or the server is stopped.

Preview uses bundled Roboto Mono Regular with cell height equal to two
character widths, matching B's 0.5 aspect ratio. Space and LF characters are
preserved and long lines scroll horizontally. Font provenance and its SIL
Open Font License are documented in [the app module guide](docs/modules/app.md).

## Command line

Run and behavior-test an unchanged built-in sample:

```sh
python -m codeart.cli --sample max2 --shape cat --scale 1.5 \
  --output max2_cat.c --report max2_cat.json
```

Compile and verify an ordinary function:

```sh
python -m codeart.cli --source example.c --shape circle --output generated.c
```

The sample choices are `max2`, `min2`, `clamp`, `absdiff`, `gcd` and
`sum_to_n`. Each includes eight fixed behavior inputs. Ordinary source and
edited samples have behavior `NOT_RUN` with reason `NO_FIXTURE`. A matching
function name alone does not select an executable fixture.

Exit status is nonzero for failed checks or pipeline diagnostics. A custom
function can succeed with behavior `NOT_RUN` when token, geometry and compile
checks pass. Output and diagnostics use stdout and stderr respectively.
Use a separate file for `--report` so it cannot overwrite the source input
or the generated C file.
The earlier `--demo` option remains a fixed smoke fixture with simulated
A/C/D/E stages and explicit `NOT_RUN` checks.

## Supported input and verification

Input is one self-contained C11 function using printable ASCII. Parameters,
automatic locals and recursion are supported. External declarations,
preprocessing dependencies, static locals, line splicing, trigraphs and real
tabs inside tokens are rejected. See [source analysis](docs/modules/source.md).

The verification evidence supports token preservation, C11 compilation and
matching behavior on the specified sample inputs. A skipped check is shown
as `NOT_RUN` with a reason. Geometry failures keep the run from being shown
as verified. Behavior is skipped for canvases above the configured cell limit.

## Fixed-size acceptance

E's public command archives the six-function by three-shape matrix.

```sh
python -m scripts.run_verification --output-dir docs/reports/local-check/fixed
```

Use a new directory for each run. The report identifies the commit and
worktree state, records 18 h32 outputs and counts actual behavior comparisons.
The same run checks the cat mask against B's h32/h64/h128 reference files.
`cat_scales` records each scale's result. `passed` combines the fixed matrix
and all three scale checks. The exit code still reports the fixed matrix.
See [the verification guide](docs/modules/verify.md) and
[the updated F integration evidence](docs/reports/F_after_E.md).
The [automatic growth demonstration](docs/reports/README.md#automatic-growth-demonstration)
shows how to reproduce and inspect layout retries.

## Team integration and delivery

[Shared contracts](docs/modules/contracts.md) define A–F entry points,
coordinates, error codes and injected dependencies. Call
`codeart.pipeline.generate(request, deps=..., cancel_event=...)`.
Production dependencies load automatically. Test doubles use the same signatures.

Each module owner maintains normal and boundary tests and its English module
guide. E owns the full regression evidence and independent scaled-cat
references supplied by B. F owns the app, CLI, environment setup and run
instructions. Formal reports should record inputs, command, expected result,
actual result, evidence and status. Store agreed deliverables under
`docs/reports/`, using `case_<function>_<shape>_h<rows>_s<scale>.c` for source artifacts.
Keep fixed and grown runs in separate `fixed/` and `scaled/` subdirectories.
Each completion table identifies the tested commit and any uncommitted changes.
Web and CLI reports include that revision information.

A minimal GitHub Actions workflow runs the complete suite on macOS for
pushes to main and pull requests, logs compiler versions and rejects a
decrease in collected test count relative to the base revision. PRs should include the actual test result and relevant environment
information. See [the F completion checklist](docs/reports/F_acceptance.md).
