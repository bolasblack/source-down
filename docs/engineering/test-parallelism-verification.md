# Parallel test runner verification

Verified on Linux x86_64 on 2026-09-21 UTC (2026-09-22 in Europe/Amsterdam), using
the repository's pinned tools and 12 test workers. The
[E2E contract](e2e.md) was updated before the external-entry regression tests and
implementation. [AGD-018](../../.agents/decisions/AGD-018_parallelize-independent-tests-under-one-budget.md)
records the scheduling and ownership decision. Product code, scenario assertions
and coverage thresholds are unchanged.

## Entry points and ownership

| Entry | Execution |
| --- | --- |
| `mise run test` | Build once, then share one worker limit across discovered Rust tests, Rust doctests, Python tests and E2E modules; merge profiles and enforce the existing coverage gates after success |
| `mise run test -- --review` | Also publish readable E2E material from that execution |
| `mise run test -- --no-coverage` | The same test inventories without profile collection; native macOS/Windows CI uses this mode |
| `mise run acceptance` | E2E modules in parallel, followed by reading publication |
| `cargo test` | Native Cargo execution and a bridge to the parallel E2E coordinator with visible progress |
| `mise run release` | Extracted-artifact E2E and portability tests share a pool; relocated source retains separate execution evidence |
| `mise run check` | Existing lint and coverage-test dependencies |
| `mise run review` / `mise run benchmark` | Project rendering / reproducible performance measurements; benchmark measurements retain exclusive execution |

`--jobs N` selects a positive worker limit for test and acceptance. `SD_TEST_JOBS`
sets the default across these entries and release validation; otherwise the available
CPU count is used. `--jobs 1` gives ordered execution. A scenario's causal operations
and Python class/module fixture lifecycle retain their order. Child Python test
processes default to one worker when they invoke these tools, avoiding another
default pool inside each job.

Release preflight now requests `test --review`, removing its repeated development
E2E invocation. Actual extracted artifacts and relocated-source checks still run.

## External red and green evidence

Before implementation, the five methods in
[e2e_parallel_test.py](../../tests/e2e_parallel_test.py) produced seven failing
assertions at the public CLI: `acceptance.py` rejected `--jobs`. The entry test in
[test_entry_test.py](../../tests/test_entry_test.py) also failed because `test.py`
rejected `--no-coverage` and `--jobs`. The contract required these controls before
the tests were written.

The passing external-entry tests establish:

- Two independently running E2E modules meet at real filesystem rendezvous points;
  same-module methods and fixtures retain their lifecycle. Raw stdout/stderr bytes,
  per-worker logs, case identities and reading remain separate and attributable.
- A normal assertion failure and an abrupt worker exit cannot hide an independent
  passing case. Interruption stops dispatch, retains unfinished and unstarted
  outcomes, and reaps real children of both active workers.
- One worker preserves discovery order and partial-selection semantics; invalid
  limits fail before execution.
- A real, dependency-free Cargo fixture, Python tests and an E2E module meet at a
  shared rendezvous. Cargo-discovered integration tests and Python class fixtures
  remain present. Artifact mode uses the supplied executable without a Cargo
  manifest or substitute build. A failing Python test fails the combined gate.

The focused green runs passed five E2E scheduling tests in 1.761 seconds and the
entry test in 0.688 seconds. The existing 16 runner regression tests also passed.
These timing figures describe the fixtures, not product acceptance duration.

## Full gates and measurements

The historical instrumented E2E run
`.source-down/e2e/runs/20260921T150856-6d7adf7dba3e/results.json` passed 136 scenarios
in 260.548 seconds with the serial coordinator and no reading generation. A
controlled pilot using the same binary and four selected scenarios took 28.769
seconds sequentially and 8.285 seconds with four independent coordinator processes;
all passed. This pilot is partial evidence, separate from the full runs below.

| Command | Result | Measured wall time |
| --- | --- | --- |
| `mise run test -- --review --jobs 12` | 210 native jobs (including doctests), 133 Python tests and 136 E2E modules passed; reading and all coverage gates passed | 83.28 s including coverage reporting; E2E coordinator plus reading 58.613 s |
| `mise run acceptance -- --jobs 12` | 136/136 passed and reading published | 12.83 s including the release-build prerequisite |
| `mise run lint` | Formatting, strict Clippy and documentation/AGD checks passed | Not used as a performance comparison |
| `mise run review` | 275 pages and project checks passed | 20.73 s, concurrent with other validation; not an isolated measurement |
| `mise run release` | Linux GNU archive, extracted-artifact portability/E2E, offline relocated-source build and rendering checks passed | 53.03 s |
| `mise run benchmark` | Six generation workloads, search/read stages and six native/Poll watch workloads passed | 98.99 s, run after other validation finished |

Coverage remained above each independent 90% threshold: Rust core 9,034/9,495
(95.14%), Rust spec plugin 297/308 (96.43%), Python project plugin 113/120 (94.17%).
The full suite retained 479 jobs under the shared limit. Its reports are:

- Combined test run: `.source-down/test-runs/20260921T221341-b5bbd7c5a8d3/results.json`.
- Instrumented E2E and reading: `.source-down/e2e/runs/20260921T221349-bd39562f60fc/results.json`.
- Standalone release-mode acceptance: `.source-down/e2e/runs/20260921T221608-bc58ff5f2e3f/results.json`.
- Extracted artifact (7 portability tests and 136 E2E modules): `.source-down/test-runs/20260921T221809-96865f1a74cc/results.json`.
- Relocated-source E2E: `.source-down/e2e/runs/20260921T221840-c89f0d09c75d/results.json`.

Raw gate logs and the pilot summary are retained under
`.source-down/test-parallelism/`. These are local, ignored evidence; the recorded
counts and commands above remain in this document. Historical and current full
timings are not a controlled same-binary A/B measurement. In particular, the
release-mode standalone timing must not be compared as if it used the instrumented
binary. Warm build caches and this host's resources affect all figures.

The last runner edit made worker-log links relative to their run directory. The
focused scheduling tests, standalone full acceptance and complete release gate
ran after that edit. Worker logs were confirmed readable after retaining the
relocated-source run. Subsequent edits only completed this documentation.

## Limits and rejected changes

The longest instrumented scenario remains the six-language watch workflow
(57.41 seconds in the full run): its edits, waits, whole-project generation,
plugin checks and final search are causally ordered. An experiment selecting
only six files failed the project's complete-reference check and was discarded.
No scenario was weakened, skipped or given shorter observation windows to obtain
these timings.

The first sandboxed native run passed 133/136 E2E cases; three real permission
fixtures failed because credential changes were forbidden. The subsequent full
coverage, acceptance and release gates ran with those OS operations available and
passed all 136. An early full coverage attempt also exposed a bug in the new test
fixture's report selection: lexicographic UUID ordering is not creation order.
The fixture now selects the newly created report by a before/after path-set
difference; the successful full gate above includes that correction.

This record establishes Linux execution only. macOS and Windows native results
remain CI evidence to obtain; the workflow uses the same inventories and keeps
platform-specific applicability rules. No remote CI run or release publication
is claimed here.
