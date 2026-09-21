# Test coverage

[AGD-008](../../.agents/decisions/AGD-008_enforce-ninety-percent-test-coverage.md) owns the acceptance gates and shared test task.
[AGD-018](../../.agents/decisions/AGD-018_parallelize-independent-tests-under-one-budget.md)
records the shared process budget; the [parallel-runner verification](test-parallelism-verification.md)
records external-entry checks, full-suite results and timing limits.
Run from this project root after `mise install`:

```sh
mise run test
mise run check
mise run test -- --review
mise run test -- --no-coverage --jobs 4
```

`test` prepares the isolated coverage environment through `coverage-setup`, runs all Rust and Python tests, writes reports, and enforces the 90% gates.
`lint` runs formatting, Clippy, documentation and AGD checks. `check` depends on both `lint` and `test`.
mise shares the same test task when these entry points are requested together.
`--jobs N` (or `SD_TEST_JOBS=N`) bounds parallel test processes; the default is the
available CPU count. `--jobs 1` gives ordered diagnostic execution. `--review`
publishes readable E2E material from the same run, avoiding a second scenario run.
`--no-coverage` runs the same inventories without profile collection and is the
native macOS/Windows CI entry. `--artifact PATH --spec-plugin PATH` runs E2E and
native portability against supplied release artifacts without building substitutes.

## Continuous integration

The [test workflow](../../.github/workflows/test.yml) runs on branch pushes, pull requests and manual dispatch
using Ubuntu 24.04, macOS 15 and Windows Server 2022. Each native runner builds all
binaries and examples, runs the complete native and Python test collections and
readable E2E under one process budget, and runs formatting and Clippy.
Platform-specific syscall and signal fixtures declare their actual applicability;
the shared native portability suite runs on all three systems.

Release-tag pushes trigger [draft-release](../../.github/workflows/draft-release.yml),
which runs full development acceptance and verifies the native release artifacts.

Linux also runs the existing `mise run test` coverage gates, documentation lint,
review and benchmark tasks. macOS and Windows run the same Cargo and Python test
collections without coverage collection, following the development acceptance
scope in [AGD-012](../../.agents/decisions/AGD-012_release-native-platform-artifacts.md).
The matrix completes every operating system even when another fails, and retains
check command logs, E2E run evidence and available coverage reports
after failures. Command logging preserves the original failure status.

CI installs the pinned mise tools from scratch. The action's cache does not
include the rustup toolchains referenced by mise's Rust installation; restoring
only those links loses the configured components. See the upstream
[Rust cache issue](https://github.com/jdx/mise-action/issues/215).

## Denominators and thresholds

| Scope | Production files | Required line coverage |
| --- | --- | --- |
| Rust core | All `src/**/*.rs`, including the CLI, language adapters, and directive modules | 90% in aggregate |
| Rust spec plugin | `tools/spec_plugin.rs` | 90% independently |
| Python project plugin | `tools/project_docs.py` | 90% independently |

These are executable line counts, with per-file detail in each report. Tests, examples, development helpers, dependencies, and generated files are outside the production denominator.
The Rust plugin is a Cargo example target, but its production source is explicitly included. The module-only `src/lib.rs` is recorded as having no executable lines;
the checker inspects its source and requires measurement if executable code is added.

The gate compares raw covered and total counts. A displayed rounded percentage cannot turn a value below 90% into a pass.
Missing production files, zero measurable production lines, excluded Python executable lines, malformed reports, failed tests, and failed collection commands fail the task.
Each scope must pass separately. Adding test source to a report cannot increase the production percentage.

## Collection

[.mise.toml](../../.mise.toml) pins cargo-llvm-cov 0.6.21 and coverage.py 7.11.0. Rust uses the `llvm-tools-preview` component matching Rust 1.90.0.
The Python tool lives in `.source-down/coverage-env`, separate from the project's runtime plugin environment.

[test.py](../../tools/test.py) obtains instrumentation settings from `cargo llvm-cov show-env`, builds the CLI and spec plugin,
and compiles Cargo's discovered test artifacts. The common scheduler runs every
listed native Rust test, Rust doctests, discovered Python tool tests and readable
E2E modules. Independent Python methods get separate processes; class/module
fixtures keep their shared lifecycle. Real CLI and Rust plugin subprocesses inherit
the profile destination. The same E2E coordinator runs once against the instrumented CLI;
direct `cargo test` reaches it through the explicit `e2e` bridge.
Its coordinator records the exact executable hashes and inherited profile destinations.
The Python tool suite uses `*_test.py`, which does not rediscover E2E `test_*.py` files.
E2E reading is requested by `test --review` or the standalone `mise run acceptance`.
Python tests execute the metadata plugin through its actual stdin/stdout protocol; coverage.py's subprocess patch collects those child processes.
The compiler wrapper is tested by compiling and running a Rust probe and verifying its emitted profile.
Each invocation also saves `.source-down/test-runs/<run-id>/results.json` and raw
job logs, including failures and jobs that did not start. Test failure retains the
current evidence and prevents a passing coverage result.

A lock serializes coverage runs in the same checkout. Before each run, `cargo llvm-cov clean --workspace` clears workspace profiles and build artifacts;
dependency caches remain reusable. Python profiles and generated reports are recreated. Old test executions therefore cannot fill gaps in the current run.
Run ordinary Cargo builds in the default target directory; `target/coverage` belongs to this task.

## Reading the results

All generated paths are relative to `.source-down/coverage/`:

| Artifact | Contents |
| --- | --- |
| `summary.json` | Raw per-scope and per-file counts, gate results, declaration-only file inventory |
| `rust/html/index.html` | Rust line-by-line HTML coverage |
| `python-html/index.html` | Python line-by-line HTML coverage |
| `rust.json`, `python.json` | Original tool reports |

`python3 tools/test.py --check-only .source-down/coverage` rechecks existing reports against the current source inventory;
fresh acceptance evidence comes from `mise run test` or `mise run check`.
The gate tests use known counts to verify exact 90%, values just below it, missing files, and invalid denominators.

Coverage directs attention to code that tests have not executed. Assertions and specification review establish whether behavior is correct.
The spec plugin's `.source-down/reports/spec/coverage.md` measures references to specification clauses, independently of execution coverage.

Tool references: [cargo-llvm-cov](https://github.com/taiki-e/cargo-llvm-cov/tree/v0.6.21),
[Rust instrumentation](https://doc.rust-lang.org/rustc/instrument-coverage.html),
and [coverage.py subprocess measurement](https://coverage.readthedocs.io/en/7.11.0/subprocess.html).
