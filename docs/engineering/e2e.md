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

Use Python's standard `unittest` assertions and ordinary control flow. Cases own
initial inputs, action order, expected identities and exact preservation scopes.
Shared domain assertions own byte comparisons, output selection, source provenance,
pagination and diagnostic parsing. Named actions on `project.sourceDown` execute
the supplied real CLI through `project.run()` and retain its original streams and
logs. Ordinary actions only save observations. Names ending in `Successfully`
explicitly guarantee exit 0; `renderSuccessfully` also guarantees empty stdout and
checks an index record count and captured output files when declared. These actions and TestCase wrappers
share ordinary internal checkers, raise `AssertionError` on a failed expectation,
and preserve parsing/I/O exception types. They do not create TestCases, retry,
add commands or create subtests. `withBinary` binds a separate entry to one program
without changing the project or runner defaults, including every continuation call.
`project.run()` returns `CompletedProcess[bytes]`.
New helpers and parameters use camelCase. Proposal 003 authorizes the 68-to-99
identity mapping recorded in the [complete-suite verification record](e2e-readable-suite-verification.md).
Unsplit scenarios retain their discovery identities. Each old assertion and subtest
must have a named new case or stage with the same scope and failure-continuation
behavior before its old owner is removed. The map is migration evidence; standard
discovery remains the only runtime inventory.
Subtest label changes require an explicit migration mapping and preservation of
their scopes, actual argv, order and failure-continuation behavior. Expected identities, ranking and ranges are not
calculated using product code.
Only explicit UTF-8 decoding converts output to text; malformed text and newline
contracts use exact bytes. Shared long input and expected material lives once in
`fixtures/`, used both by the test and its comment's include directive.

Controlled Python programs with exact stream-byte expectations write explicit
bytes to stdout or stderr. Their newline-sensitive checks also exercise CRLF text
stream translation on every host; process capture and assertions retain the
original bytes, including deliberate LF/CRLF differences.

Read concurrently published files through `project.read_bytes()`. Its native
reader permits replacement and deletion while a read handle is open, so an
observation cannot manufacture a Windows publication failure. Deliberate file
locks belong to explicit failure fixtures. A held reader must keep the old file's
bytes while a new reader sees the completed replacement.

Permission scenarios that lower process credentials place their disposable project
in the Unix shared temporary directory. They must work with a private inherited
`TMPDIR` without changing permissions on repository or user-directory ancestors.

Concrete expectations belong in case files or an included ordinary shared file.
The dedicated guide scenario lists its nine URLs, four sources and repetition
relationship directly. Two refresh scenarios use and include the ordinary
`cases/self_use/guide_expectations.py` file. This small duplication makes the
dedicated scenario reviewable in one file; changes to these concrete expectations
must be checked in both locations. Long source and fault material remains in a
single fixture. Support owns the verification mechanism, without adding implicit
success checks, `subTest` scopes or recovery actions. Each case owns a separate
mutable project. Mutation builds have private work directories and record the
replacement, source hashes and the executable used by each command.

Render observations freeze the complete output, including failures. Capture errors
are retained and reported only when an assertion requires those artifacts; exit
status is checked first. Omitted expectations differ from `None` and empty bytes.
Whole output, selected files, selected trees and all Markdown are distinct scopes.
Explicit files must exist on both sides; output protection compares the same project
and output root, while cross-root Markdown comparisons are explicit.

`editing` restores input bytes after normal completion, assertion failure or
interruption. Cases still run the next render to demonstrate product recovery.

`Project.writeInPlace(path, content)` directly opens, truncates and writes the
target. `str` is encoded as UTF-8 without newline conversion; bytes stay exact.
An existing file retains its identity and permissions; hard links see the edit
and symbolic links follow the operating system's ordinary open behavior. A new
file may be created, but its parent must already exist.
`Project.atomicReplace(path, content, *, temporaryPath)` exclusively creates the
explicit, different temporary path, writes and closes it, then calls `os.replace`
once. Both parents must already exist. It replaces the destination name with the
new file, using normal creation permissions and umask. It does not copy metadata,
choose a temporary directory, retry, fall back to an in-place write or promise
crash durability. Native failures propagate; cleanup removes only a temporary
file successfully created by this call, without masking the original error.
Equal temporary and destination paths are rejected before any write.

`writeFiles`/`writeBytes` remain preparation operations that create parents.
`replaceFile` consumes an already prepared file. Link operations,
`writePreservingTimes` and `editing` keep their distinct uses. Runtime edits use
the explicit save operation only when parents and event order are equivalent.
Pre-watch replacements remain prepared before startup; moving and restoring
configuration files retains their original file identities. Required permissions,
repair waits and rendering remain explicit case actions.

Continuation reads preserve each raw response and use one pure page inspection
owner for both driving and checking. Invalid responses stop further requests.
The monotonic total budget defaults to 30 seconds, can be overridden, and bounds
each command by its remaining duration. Timeout is an execution error with process
cleanup and retained logs. No merged JSON response or arbitrary page limit is used.
`readEntityToEnd` starts at offset 0 and preserves this same driver and observations.
`assertCompleteUtf8Read` checks successful pages and the complete supplied body;
`assertReadFromFile` independently checks successful pages, file fields, fingerprint
and source selection. Neither assertion requires the other to run first.
`assertCompleteSinglePage` reuses the existing complete-body check: one successful
page, the exact five body fields, supplied text, UTF-8 range and total, no truncation
and no continuation. `assertReadMetadata(fields=...)` compares only the declared
top-level fields; it adds no closed-object or implicit entity requirement.

`assertPageLinks` uses author paths and explicit URLs; source-excerpt assertions
use author directories and share the existing matcher and provenance checks.
`assertSourceExcerptsMatchOriginals` returns the existing frozen excerpts. Explicit
cross-round comparisons use those saved bodies, optionally filtered by the same
source on both sides, without rereading an earlier round from current files.
`assertRecordCollision` checks exit 1, empty stdout and full diagnostic identities
without decoding failed query output as JSON. The record-collision scenario uses
three independent `operation` subtests for changed-input render, saved-snapshot
search and saved-snapshot read, protecting the same frozen output after each.

The helper contract is exercised through the coordinator in disposable checkouts.
Bounded negative inputs cover output scopes, independent observations, restoration,
navigation, sources, read bodies/cursors and collision identities. Missing artifacts
and wrong hit counts produce named unittest failures; malformed JSON retains its
ordinary exception classification. New behavior and migration sensitivity receive
separate evidence from successful product acceptance.

Result composition uses explicit observation types:

| Assertion family | Accepted observations |
| --- | --- |
| Process facts | Raw `CompletedProcess[bytes]` and the existing command observations; no JSON parsing |
| Search result and hit assertions | `SearchResult` or raw `CompletedProcess[bytes]` |
| Read metadata, text and alias assertions | Raw `CompletedProcess[bytes]`, `CommandResult` (including `ReadPage`), or single-page `ReadResult` |
| Complete read, pagination and source selection | `ReadResult`, which retains requested offsets and traversal facts |
| Index assertions | `IndexView`, `RenderResult`, `OutputSnapshot`, or captured index `bytes` |
| Render, output protection, navigation and source excerpts | Their existing observations with project/output context |

Adapters only interpret saved facts. They neither execute commands nor assert
success, read current files or invent offsets, output roots or project ownership.
Search assertions share one adapter; simple read assertions reject other domain
results and multi-page reads. Index adaptation stays with the index assertions;
the output snapshot adapter retains its own narrow responsibility. Process
expectations run before declared content expectations. A non-JSON failure can
therefore be checked by exit/stream alone; asking for JSON retains its parsing
error. Omitted values, `None` and empty values remain distinct. Raw results and JSON
views keep their defensive copies.

`assertReadMetadata`, `assertIndexMetadata` and `assertIndexManifest` use `fields`
for selected top-level keys. Each selected value is compared in full, including
nested objects; absent keys fail. Ordered complete lists such as dependencies,
dependency paths and expansion texts keep `equals`. `renderSuccessfully` and
`assertRenderResult` use `includesFiles`: every listed artifact must be present,
and additional artifacts are allowed. They retain process-first checks and their
distinct existing ordering of file/count expectations.

The complete-suite migration extends the existing command, artifact, read and
reading owners. `index_assertions.py` owns narrow index comparisons over `IndexView`;
`watch.py` wraps the existing `RunningCommand`; `native_fixtures.py` prepares the
existing real OS fault windows and probes. They do not duplicate process scopes,
logs, native readers or discovery. Fixed plugins live once in ordinary fixtures.
Short initial files, expected values, edits, repair/release actions and protection
capture points remain visible in case bodies or explicit reading includes.

Watch waits observe only declared facts and retain their original timeouts,
early-exit and exception behavior. Log checkpoints precede edits. Exit-only and
exit-plus-stdout checks remain distinct, as do final-window log comparisons and
whole-window native event capture. Tests observe product process reaping before
context cleanup. Native shims keep their real build paths, system calls and pause
handshakes; helpers never repair a fault or retry a business operation implicitly.

Watch waits return frozen facts from the successful attempt:

| Wait | Result |
| --- | --- |
| `waitForOutputState` | `OutputObservation(projectRoot, files, presentFiles, absentPaths)` |
| `waitForDiagnostics`, `waitForPublishedPages` | `LogObservation(stderr, checkpoint)` |
| `waitForEventCount` | `EventObservation(path, content, count)` |
| The two search waits | The existing `SearchResult` |

`files` is a read-only copy of the bytes actually read, keyed by the supplied
paths relative to the project root. `presentFiles` and `absentPaths` are tuples.
Each attempt checks presence, absence, changed bytes, contained bytes, then index
manifest fields, with the existing short-circuit and error behavior. The last
three conditions share one read per supplied path key in that attempt; aliases
are not canonicalized. Presence/absence alone never reads bodies. Empty bytes
and empty mappings are successful observations too. A subsequent write, rename
or deletion cannot change the saved observation. Multiple paths need not belong
to the same publication. Waiting neither scans output nor adds commands.

`checkpoint()` requires an entered watch and returns a `WatchCheckpoint` bound to
that actual start and its stderr byte offset. Before entry or after exit it raises
`RuntimeError`. Omitted `since` starts at byte zero; an explicit value must be a
checkpoint (`TypeError` otherwise), from this watch with an in-range integer
offset (`ValueError` otherwise). Misuse fails before waiting. Each log attempt
reads stderr once, matches its slice, and saves that slice and its exact end
checkpoint. The point can start the next wait on the same watch; it does not
drain events or attribute later diagnostics to an edit. `assertWatchDiagnostics`
checks either the current complete watch stderr or a saved observation's interval.

Event observations retain the complete bytes used for substring counting, with
the existing presence prerequisite and strict `count > greaterThan`. Output-only
search waiting and successful-search waiting keep distinct exit-code conditions.
All waits reuse `RunningCommand.wait_for`; missing files, malformed JSON, timeouts,
early exits and process cleanup keep their existing classifications and ordering.
`waitForProcessExit` and `wait()` retain their existing return values.

`notificationPublicationFault(project, mode="error" | "rescan")` is the fixed
native fixture triggered while checking `pages/docs/z.md.md` after
`pages/docs/a.md.md` has appeared. `waitUntilCallbackReturned` observes only the
callback's marker through a presence wait. The separate recovery-batch pause,
explicit release (also in `finally`), final publication assertions and product
reaping checks retain their own places in the scenario. The configuration
fixture's two-stage handshake remains independent.

The configuration read-window fixture pauses the first `starting` diagnostic after
the watch baseline and before Session construction. Its real preload hook only
controls that I/O boundary. The case edits the configuration, explicitly releases
construction, observes the plugin's actual initialize options, and restores the
configuration before releasing the plugin response. `configurationReadWindow`
owns compilation and marker setup; waits and releases remain explicit in the case.
Its optional `afterLoaded` boundary pauses the missing-index adoption diagnostic
after Session construction. This lets the absent-configuration scenario restore
the same file before generation, preserving its identity and bytes.

The [complete-suite verification record](e2e-readable-suite-verification.md) binds
every original check to its migrated owner, platform, command and run evidence,
records split preparation costs and bounded sensitivity experiments, and reviews
all 99 bodies for visible initial state, action and expectation. All applicable
completion gates run against the final frozen collection.

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

The [narrative helper verification record](e2e-narrative-verification.md) records
the three-scenario migration, deliberate subtest label mapping and runtime evidence.
The [API composition verification record](e2e-api-verification.md) records result
adapters, frozen wait observations, explicit saves, naming migration and their
independent negative evidence.
