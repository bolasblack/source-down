# Readable end-to-end acceptance

This engineering contract governs the test runner and reading artifacts. Product
behavior remains owned by [the specifications](../specs/README.md). It was written
before the runner changes for the 2026-09-08 readable-E2E design.

## Development order and boundaries

For a product slice, establish its owning specification, write a readable scenario
through the real public boundary, and record a failure caused by the missing
behavior before changing the implementation. After the smallest passing change,
refactor while green and run the applicable completion gates. Import failures,
missing tools and broken fixtures do not demonstrate missing product behavior.
For test migration, preserve the existing contract and use a controlled test or
program mutation to establish assertion sensitivity before replacing its owner.

The runner's agreed public boundary is `python tools/acceptance.py`, its exit status,
persisted run directory and generated reading pages. Runner changes use this
engineering contract before their external-entry tests. This work adds no product
command or product-format requirement. Public Rust Session workflows retain their
native tests over real files, plugin processes and publication.

## Scenarios and support

`tests-e2e/cases/<command-or-workflow>/test_<scenario>.py` holds one complete user
scenario per file. Each normal package has `__init__.py`. Test methods have a short
one-line docstring and their class declares complete owning clause IDs in `specs`.
Independent `#` comments explain the scenario; docstrings remain source code when
rendered. A language matrix may use `subTest`, whose actual results remain visible.

`tests-e2e/` is a discovery root, with `cases/`, `fixtures/`, `support/` and Cargo's
`bridge.rs`. Cases import the normal `support` package from that root. The runner's
own developer-tool tests and retained native boundary tests live in `tests/`.

Use Python's standard `unittest` assertions and ordinary control flow. The support
layer supplies isolated projects, byte I/O, real command execution and generic byte
or ordering assertions. Inputs, commands, expected results and publication rules
remain visible in the scenario. Expected identities, ranking and ranges are not
calculated using product code. `project.run()` returns `CompletedProcess[bytes]`.
Only explicit UTF-8 decoding converts output to text; malformed text and newline
contracts use exact bytes. Shared long input and expected material lives once in
`fixtures/`, used both by the test and its comment's include directive.

Read concurrently published files through `project.read_bytes()`. Its native
reader permits replacement and deletion while a read handle is open, so an
observation cannot manufacture a Windows publication failure. Deliberate file
locks belong to explicit failure fixtures. A held reader must keep the old file's
bytes while a new reader sees the completed replacement.

Business checks belong in case files. Project-copy and mutant-build preparation
may be shared; assertions about actual rendering, protocol replies, collisions and
unchanged output belong to their named scenarios. Each case owns a separate mutable
project. Mutation builds have private work directories and record the replacement,
source hashes and the executable used by each command.

## Discovery, execution and truthful results

The coordinator creates `.source-down/e2e/runs/<run-id>/`, copies the E2E collection,
fixtures and specifications, and discovers **that copy** with `TestLoader.discover`,
`start_dir=tests-e2e/cases`, `top_level_dir=tests-e2e`, `pattern=test_*.py`. This discovered
collection is the single runtime case inventory. Missing package discovery, empty
modules/suites, duplicate identities and import errors are execution errors.

`--case render` selects that exact directory subtree; `--case
render/test_missing_material.py` selects that exact file. An empty selection fails.
`--list` records discovery without executing tests. Selected cases execute serially;
ordinary failures do not prevent independent cases from running. A filtered run is
always labeled partial, even if every selected case passes.

Each result records identity, title, source, owning clauses, selection, applicability,
start/end times, command/log records, subtests and one of `passed`, `failed`, `error`,
`skipped`, `not_run`. Only actual `unittest` result events determine outcomes. An
ordinary skip or expected failure cannot establish full acceptance. A case's explicit
`platforms` declaration may identify a platform-inapplicable skip with its reason;
the report retains it and names the platform actually exercised. Full success
requires every selected applicable case to execute and pass, and a nonempty executed
set. Listing and partial success never claim full-suite success.

One run context owns the repository, binary, spec-plugin and run paths. Record
original workspace path, HEAD/dirty evidence when available, source/fixture hashes,
platform, selected range, and exact binary/plugin paths and SHA-256. Every subprocess
records argv, cwd, executable identity, status and original stdout/stderr bytes in
logs. Preserve the inherited build and coverage environment, including
`LLVM_PROFILE_FILE`, `SD_COVERAGE_ROOT` and `SD_COVERAGE_DATA`; report only these
relevant facts rather than the complete environment.

Commands have bounded waits and clean up their process scopes on timeout or
interruption. An interrupted run saves acquired results, marks the active case as
interrupted/error and the remaining cases `not_run`, and exits 130. Regular test,
discovery or documentation failure exits 1. Successful complete or selected
execution exits 0, with its scope explicitly recorded.

## Reading artifacts and failure handling

Save `results.json`, raw logs, `results.md` and `index.md` before attempting optional
rendering. The run directory is the reading project's root and contains a minimal
`source-down.toml` with `config_version = 1`. Explicitly render `index.md` and the
discovered scenario files to `reading`; do not recursively render support or fixtures.
Use the same preserved files that Python loaded, and verify they remain unchanged.

The index groups scenarios by workflow and links their status, clauses, source and
generated page. Results include commands, diagnostics and separate test/document
states. Fixture include uses its one preserved input; Python comments become prose
only when their source file is rendered directly. Source included as material stays
a literal code block. Ordinary full-project review excludes fault fixtures from
input selection; explicit include may still display valid textual material.

Verify the generated index, every expected scenario page, local navigation and
source links against this run's output and preserved sources. A failed test still
gets reading material where the renderer works. A rendering failure preserves the
raw JSON/Markdown/logs, records the documentation failure separately, and makes
`--review` fail. Old pages never satisfy a new run. Every invocation prints absolute
paths to its results and reading entry; no mutable latest-success alias is maintained.

## Shared entry points and completion

`mise run acceptance` requests `--review`. `--binary` and `--spec-plugin` select the
actual artifacts for test and release callers; the runner never substitutes a
locally built CLI. Cargo's `e2e` target is a thin bridge to this same coordinator with
`CARGO_BIN_EXE_source-down`, without reading generation. Python developer-tool tests
retain `*_test.py`, so they do not rediscover `test_*.py` scenarios.

`mise run test` keeps all native tests, the single E2E bridge, Python tool tests and
separate 90% line-coverage gates for core, Rust spec plugin and Python project plugin.
Line coverage is distinct from spec-plugin reference coverage. `lint`, full source
`review`, readable `acceptance`, and native `release` must pass. Release verification
uses the extracted CLI and relocates/rebuilds the source package on the executable
host; unexecuted targets remain explicitly unverified. Release retains the relocated
coordinator's run directory in the caller's `.source-down/e2e/runs/` before cleaning
up its temporary source checkout, preserving that run ID and its relative links.

The [migration ledger](e2e-migration.md) tracks each original acceptance assertion and
each candidate Rust test. Only a named new owner with equal assertion strength permits
deleting an old test. Retained library/system tests and pending readable migrations
remain explicit. The first delivery migrates acceptance and both collision classes,
provides render/search/read entry scenarios, and classifies the Rust candidates;
it does not claim the entire repository has moved to Python E2E.

The runner's external tests must exercise wrong exit/output, empty discovery/import
errors, duplicate/incomplete discovery, empty filtering, skips, subtest failure,
partial execution, interruption and reading failure. A controlled scenario/fixture
mutation must fail execution and its report, then pass after restoration. Record the
contract, RED, GREEN, mutation, generated reading and final task evidence in the
delivery record.

The implementation uses [unittest discovery and result events](https://docs.python.org/3.14/library/unittest.html#test-discovery)
and an explicit [Cargo test target](https://doc.rust-lang.org/cargo/reference/cargo-targets.html#tests).
