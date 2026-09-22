# Parallel test runner verification

Verified on Linux x86_64 on 2026-09-21 UTC (2026-09-22 in Europe/Amsterdam), using
the repository's pinned tools and 12 test workers. The
[E2E contract](e2e.md) was updated before the external-entry regression tests and
implementation. [AGD-018](../../.agents/decisions/AGD-018_parallelize-independent-tests-under-one-budget.md)
records the scheduling and ownership decision. The initial implementation kept
product code, scenario assertions and coverage thresholds unchanged. Later native
CI findings and fixture corrections are recorded below.

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

These initial measurements establish Linux execution only. Native CI evidence
from the subsequent follow-up is recorded below. No release publication is claimed.

## Runtime follow-up

The first parallel implementation was committed as `d27841f`. Its
[draft-release verify job](https://github.com/bolasblack/source-down/actions/runs/35663125477/job/106543062921)
passed in 12 minutes 2 seconds: tool setup took 15 seconds, and the combined
development gate took 11 minutes 39 seconds. Public job metadata does not expose
the individual commands inside that combined step. On the same commit, the
[regular CI run](https://github.com/bolasblack/source-down/actions/runs/35663250781)
reported these Linux step durations: Clippy/formatting 34 seconds, tests/coverage
436 seconds, and documentation/review/benchmark 228 seconds. macOS passed; Windows
failed in the missing-page adoption scenario. These are remote measurements of
the first implementation, not measurements of the follow-up changes below.

The follow-up preserves the test inventories and assertions while addressing
four measured costs:

- Dispatch alternates between E2E, Python and native queues. Previously, only the
  first E2E module could start before the complete Python and native queues.
- Only third-party dependencies use development optimization level 2. The CLI,
  library and spec plugin retain optimization level 0, debug information, debug
  assertions and overflow checks. The same six-language watch scenario took
  50.410 seconds before and 16.25 seconds with this dependency setting in isolated
  runs. No input selection or plugin check changed.
- LLVM uses its locked profile pool per binary signature without a process ID in
  the filename. Samples still accumulate from every child, and each gate clears
  prior workspace profiles and artifacts. The original run retained 3,334 raw
  files (2,938.7 MiB); the final follow-up run retained 201 (81.18 MiB).
- Private mutation builds explicitly retain unoptimized dependencies because
  each temporary target is discarded. Both real mutation scenarios passed with
  two workers before and after this override: 20.88/21.00 seconds became
  8.33/8.37 seconds. Source hashes, executable identity and collision assertions
  remain part of their evidence.

The external Cargo-fixture entry test now requires a second E2E module to
participate before the Python queue drains. It failed with the earlier dispatch
order and passed after interleaving (0.752 seconds). The new
[coverage runtime test](../../tests/coverage_runtime_test.py) executes the actual
coverage entry twice in a dependency-free Cargo project. It proves concurrent
left/right counts of 6/6, then counts of 12/0 and a failed coverage gate on the
second run. Before profile pooling, its file bound failed with 26 files instead
of at most six; the passing two-run test took 2.371 seconds.

The existing failure/crash fixture also demonstrated that console output omitted
saved failures. The coordinator now prints retained failure tracebacks and worker
errors. All five scheduling tests passed after this change (1.700 seconds).
CI exposes lint, tests, project review and benchmark as separate steps so their
durations and failures are directly visible; the gate order remains unchanged.

After all runner and build changes, `mise run test -- --review --jobs 12` passed
480 jobs (210 native, 134 Python and 136 E2E modules) in 53.26 seconds including
coverage reporting. The scheduler/build portion took 47.000 seconds. In that
shared run the six-language watch scenario took 23.102 seconds and started with
the first dispatched jobs. All 136 E2E cases passed and reading was published.
Coverage was Rust core 9,034/9,495 (95.14%), spec plugin 297/308 (96.43%) and Python
plugin 113/120 (94.17%). Every individual production file retained its previous
coverage denominator.

Reports and retained measurements:

- Combined test run: `.source-down/test-runs/20260921T225703-eaf0a225c83e/results.json`.
- Instrumented E2E and reading: `.source-down/e2e/runs/20260921T225711-b8635d7de80e/results.json`.
- Isolated original watch: `.source-down/e2e/runs/20260921T223215-a67225491020/results.json`.
- Isolated dependency-optimized watch: `.source-down/e2e/runs/20260921T223447-65db21ddc0f7/results.json`.
- Mutation build comparison: `.source-down/e2e/runs/20260921T225132-44d4d55c09e7/results.json`
  and `.source-down/e2e/runs/20260921T225302-725d4e0d5152/results.json`.
- Raw red/green logs, build profiles and before/after coverage summaries:
  `.source-down/test-runtime/`.

The independent `mise run acceptance -- --jobs 12` gate also passed all 136
scenarios and published reading
(`.source-down/e2e/runs/20260921T225838-7ea0596d9632/results.json`). Formatting,
strict Clippy and documentation/AGD checks passed. `mise run review` published
276 pages with passing project checks. `SD_TEST_JOBS=12 mise run release` passed
Linux GNU extracted-artifact portability/E2E and the relocated-source rebuild;
its reports are
`.source-down/test-runs/20260921T230016-2e648dd064c1/results.json` and
`.source-down/e2e/runs/20260921T230048-f0c7e2131f94/results.json`. Subsequent edits
only completed this verification record and the explanation of CI step visibility.

## Native CI diagnosis and follow-up

The first native follow-up, [run 35666437718](https://github.com/bolasblack/source-down/actions/runs/35666437718)
at `bbebc5e`, passed shared Linux verification and macOS. Linux tests/coverage and
reading took 283 seconds, down from the first parallel implementation's 436
seconds; the whole verification job still took 590 seconds. Release compilation
and project review consumed 83 seconds, and benchmarks added another 142-second
serial tail. macOS took 378 seconds and Windows failed after 526 seconds. These
cold runs do not establish an overall cross-platform speedup.

The following [run 35667727709](https://github.com/bolasblack/source-down/actions/runs/35667727709)
at `8658565` passed Linux verification and macOS, and reported dependency cache
misses on all three hosts. macOS's test entry took 246.81 seconds, including
59.38 seconds for build/discovery. Windows's entry took 384.12 seconds, including
91.01 seconds for build/discovery. Its two private mutation builds took 77.54
and 78.45 seconds each. The scheduler was concurrent; significant compilation
and native process startup costs remained.

Native diagnostics identified three distinct fixture problems:

- Watch adoption tests incorrectly required successful publication in round one.
  A Windows trace showed a correctly discarded first candidate followed by
  successful publication in round two. Seven waits now observe the published
  page count, keeping the same timeout and every downstream content, preservation,
  deletion, search and shutdown check. All 63 watch scenarios passed locally;
  the next Windows run passed the complete watch inventory and 12 independent
  missing-page adoption repetitions.
- The real continuation-deadline helper intermittently failed with `WinError 32`
  while deleting its temporary project. Its intentionally surviving descendant
  still owned the working directory after the job handle was closed. A separate
  native repetition reproduced the same error. Waiting for zero active job
  processes alone still failed in the next CI run. Cleanup now captures members'
  process handles before termination and waits for their signaled exit state,
  then confirms the job is empty. The existing real-process fixture checks both
  timeout cleanup and a successful parent with a surviving child. Command records
  retain captured and waited Windows PIDs for failure diagnosis.
- The Rust initialization/close fixture allowed only 200 milliseconds for the
  native Python interpreter to start and reach the blocked phase. CI timed out
  before the fixture could write its PID. It now uses the other plugin fixtures'
  3-second phase budget, retains both phase-specific timeout and process-exit
  assertions, and adds a 10-second elapsed bound against its 30-second blocking
  scripts. Product deadlines and watch observation windows did not change.

The local continuation helper passed in 5.014 seconds, the five process scheduler
regressions passed in 1.713 seconds, and the Rust deadline fixture passed in 6.06
seconds after these changes. Formatting, strict Clippy and documentation/AGD
checks passed. The subsequent native Windows process confirmation is recorded below.

The shared verification workflow now resolves one exact commit, then runs its
verification and benchmark jobs on separate hosted machines. Benchmarks retain
exclusive machine use and remain a required gate. Branch CI and draft-release
still call the same workflow. Cargo dependency caches are separated by host,
toolchain, manifests and build-wrapper settings; verification and benchmark jobs
use distinct keys. Workspace programs, test outcomes and raw profiles are not
cached. Test notices expose build/discovery time, total time and the ten slowest
jobs, while retained artifacts keep full logs and reports.

With warm verification/native dependency caches, [run 35668868642](https://github.com/bolasblack/source-down/actions/runs/35668868642)
at `be7a1c3` passed Linux verification and benchmarks in 5 minutes 14 seconds from
the identity job's start, compared with the initial draft preflight's 12 minutes
2 seconds. macOS passed in 4 minutes 17 seconds. Windows took 6 minutes 17 seconds
but still failed the continuation helper, including one independent repetition;
the Rust startup-deadline failure no longer appeared. Linux build/discovery fell
from 71.02 to 18.30 seconds, macOS from 59.38 to 22.57 seconds, and Windows from
91.01 to 34.90 seconds. The new benchmark cache was cold and its 4-minute-26-second
job overlapped verification. This run validates the scheduling/cache gains, while
also supplying the red evidence that job accounting alone was insufficient.

[Run 35669854886](https://github.com/bolasblack/source-down/actions/runs/35669854886)
at `960f12e` passed the original Windows continuation helper plus all four
independent repetitions after process-handle waits were introduced. All 12
missing-page adoption repetitions also passed. The temporary CI repetition step
was then removed; those scenarios remain in the normal inventory.

The full Windows run exposed another assertion that counted attempts as successful
publications: the content/mtime scenario expected exactly two plugin batches, but
observed three. It now checkpoints before the edit, waits for publication, requires
exactly two successful publications and accounts only for explicitly reported
discarded candidates in the batch count. The same-size/same-mtime assertions,
updated page/index/search checks and 1.1-second unchanged event/index window remain.
An additional publication or unexplained batch still fails.

In that run, Linux verification, macOS tests and benchmark measurements passed.
The macOS and benchmark jobs separately failed GitHub artifact finalization with
HTTP 403; Linux and Windows evidence uploads subsequently succeeded. These upload
errors are distinct from test outcomes and have not been ignored or waived. The
[branch workflow](https://github.com/bolasblack/source-down/actions/workflows/test.yml)
reports the final aggregate status after the content/mtime correction.

The next [run 35670787409](https://github.com/bolasblack/source-down/actions/runs/35670787409)
passed Linux verification, macOS and benchmarks, including every evidence upload.
The Windows content/mtime correction passed. Its native-watch scenario instead
exposed an ambiguous startup wait: `published` also matched `candidate not
published`, allowing an edit and output read before the first page directory
existed (`WinError 3`). This last bare publication wait now requests the actual
one-page publication. The output wait's missing-file error classification remains
unchanged. The other watch startup predicates were checked for this ambiguity.

Local copies of native job metadata, check annotations and focused regression
logs are retained under `.source-down/test-runtime/`.
The earlier exclusive benchmark gate remains evidence for the unchanged product
code and release profile.

The 83.28-second first implementation and 53.26-second follow-up both used this
Linux host and 12 workers, with warm dependency caches. They are full gate
measurements, not a promise of the same time on a four-worker CI runner with a
fresh checkout and cold build caches. Dependency optimization increases first
compilation cost, and release compilation and benchmarks remain separate costs.
The Windows excerpt identifies a 15.51-second failure but omits the assertion
and watch stderr. Linux success does not establish its cause or a Windows fix;
the retained Windows traceback is still needed.

The CI follow-up exposes retained failures as escaped GitHub check annotations,
including worker errors and native/Python failures. The existing real-process
failure fixture proves that percent signs and embedded workflow-command text stay
inside the diagnostic. It failed before annotations existed and again when raw
console lines could be interpreted as commands; both paths are now covered.
Branch CI and draft-release now call the same reusable `verify.yml`. The former
uses the triggering commit; the latter still requires the supplied tag identity
before returning the verified commit to build jobs. This allows the complete
verification commands to run on ordinary pushes without moving a release tag.
The complete local `mise run check -- --jobs 12` passed 480 jobs and all coverage
gates in 51.98 seconds before the final diagnostic-only escaping correction.

## Native CI follow-up

Commit `bbebc5e` ran the new shared verification entry in
[CI run 35666437718](https://github.com/bolasblack/source-down/actions/runs/35666437718).
Linux verify passed in 9 minutes 50 seconds: lint 52 seconds, tests/coverage/reading
283 seconds, project review (including release compilation) 83 seconds, and
benchmarks 142 seconds. macOS passed in 6 minutes 18 seconds, with 58 seconds of
Clippy and 281 seconds of native tests. These cold runs confirm the first-build
cost of optimizing dependencies, motivating a cache of compiled dependencies.
The cache excludes workspace programs, test results and coverage samples; the
next CI runs must establish both misses and hits rather than assuming a speedup.

Windows failed two observations. Its retained annotation showed the edited-page
adoption scenario discarding round 1 and successfully publishing two pages in
round 2. The test nevertheless timed out waiting specifically for round 1. All
seven publication waits with this assumption now use the expected page count,
while retaining their original timeouts and final page, deletion and search
assertions. This follows the existing watch contract's candidate-discard behavior;
no product behavior changed. The second failure was in the continuation deadline
helper regression: the expected successful override was reported as an error.
The Actions runner truncated this diagnostic at 4,096 characters, so annotation
formatting now retains the identifying prefix and final exception within that
bound; complete logs remain in artifacts. Temporary Windows repetitions collect
native evidence for both cases during the next CI iteration.

## Publication and exited-group follow-up

History consolidation produced `c8328e4` with exactly the same tracked tree as
`a6a5e4f`. Its [native CI run](https://github.com/bolasblack/source-down/actions/runs/35699974704)
passed Linux verification and benchmarks, but failed two watch observations.
Windows failed the empty-discovery repair's search with a missing index; macOS
failed unknown-file repair after process-group cleanup returned `EPERM`.
These failures qualify the earlier successful run; they were not code changes
introduced by consolidation.

The empty-discovery case waited for its replacement page and obsolete-page
deletion, both of which precede the final index replacement. A Linux preload
probe that delayed only that replacement by 300 milliseconds made the original
search fail against the stale index. This proves the premature query without
claiming to reproduce Windows's exact missing-file error. A checkpoint and the
same round's completed-publication diagnostic now precede the existing search
assertion; its timeout, page checks and preservation checks remain intact.
The probe changed from failure in 0.38 seconds to success in 0.74 seconds.

Darwin's group-signal implementation can return `EPERM` when its member filter
finds only zombies. The Unix process owner already attempted to reap its direct
child after a failed signal, but propagated that earlier error even when reaping
removed the last group member. It now accepts that outcome only after a signal-zero
probe reports that the entire group no longer exists. A surviving group or any
other observation error retains the original cleanup failure; no signal retry,
business retry or extra timeout is introduced.

The new readable process-group scenario exercises both real exited/unreaped and
live children through a native syscall fixture. Before the fix, its exited-child
subtest failed on the false cleanup diagnostic while the live-child denial passed.
After the fix both passed in 0.61 seconds, including reaping, successful watch
repair and an explicit cleanup of the deliberately denied live fixture.
Focused evidence is retained at:

- Process cleanup red: `.source-down/e2e/runs/20260922T074949-b76fc4757d2f/results.json`.
- Process cleanup green: `.source-down/e2e/runs/20260922T075141-9fc6efa6cf5a/results.json`.
- Publication-window red: `.source-down/e2e/runs/20260922T074529-84d8712e5b72/results.json`.
- Publication-window green: `.source-down/e2e/runs/20260922T075141-5cd013a13ad7/results.json`.

These controlled results establish their particular boundaries on Linux. The
subsequent native CI result must separately establish macOS and Windows outcomes.

Full local validation passed with 481 jobs sharing 12 workers, including all 137
readable E2E modules and their reading material, in 53.40 seconds. The retained
suite is `.source-down/test-runs/20260922T080155-5cf6c444976f/results.json`; its
E2E run is `.source-down/e2e/runs/20260922T080204-64193152da4c/results.json`, with
every command's cleanup complete. The existing native reaping regression now
requires the original protocol error without a false cleanup error. The process
owner requires both a reaped direct child and an absent group before accepting
the earlier permission error, preserving bounded failure for a live child.
Coverage passed independently for Rust core (95.21%), the Rust spec plugin
(96.43%) and the Python project plugin (94.17%). Formatting, Clippy and document
checks passed; complete project review published 277 pages. Linux GNU release
verification passed extracted-artifact tests and relocated-source rebuild in
66.29 seconds, retaining the latter's E2E evidence at
`.source-down/e2e/runs/20260922T080435-58b24e962e2a/results.json`.
