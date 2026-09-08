# Watch acceptance

The 2026-09-09 watch implementation passes the local acceptance gates below and
[native CI on Linux, macOS and Windows](https://github.com/bolasblack/source-down/actions/runs/34357208180)
at `3338ec9fe76fc8ac8b12802c83467d443ee3f7dc`.
The product owners are [SPEC-CLI-008](../specs/cli.md#spec-cli-008) through
[SPEC-CLI-012](../specs/cli.md#spec-cli-012), with source/dependency and publication
contracts in the linked model, plugin and search clauses. Configuration, wire and
search formats remain version 1.

[AGD-014](../../.agents/decisions/AGD-014_use-native-notifications-with-explicit-content-polling.md)
records the engineering rationale. Native notifications are hints; complete bytes,
query chains, identities, errors and directory facts come from `filesystem`.
The native callback holds at most 4096 paths, folding excess into rescan. Content
writes, metadata and possible structure changes stay distinct so directory dependencies
do not treat regular member contents or permissions as declarations. The production notification interface
also accepts a controlled delivery adapter in component tests; those tests are
supplemental evidence, not native operating-system acceptance.

The initial control interval is 50ms, quiet coalescing 100ms, maximum coalescing 1s,
and Poll waits 1s after a completed sample. These are engineering parameters.
Native idle periods do not call the content sampler. New coverage is registered
before sampling and retained across plugin cleanup. Per-sample facts are acquired
once per query and kind, while the returned Sample retains all owning scopes.

## Preserved baseline

The in-progress content-polling implementation was archived before native migration
under `/tmp/source-down-watch-v1-checkpoint-20260909/`, including source hashes,
staged/unstaged diffs, archive and the actual binary. Its binary SHA-256 is
`be44afe18fdc8710e847c4bdc7c0c8f6cf5ef636d0a8af4967bf138bae0c3e38`.
The source archive SHA-256 is
`08e04e8154065bc09416525075411dd19212f4a9a971e7d12e8428f3a912a960`.
That evidence covers 17 business scenarios under the earlier observation model.

The native migration retains those business assertions. The check-repair case now
waits for the first successfully published round: an include material without an
exact preceding observation requires a discovery round. It still asserts report
updates, preserved page/index bytes on check failure, accurate recovery and one
healthy plugin initialization.

## Current evidence

Run directories below are under `.source-down/e2e/runs/`; each contains copied
specs/scenarios, exact binary hashes, command logs, results and reading artifacts.
Focused runs are partial acceptance, not a full project gate.

| Behavior | RED or counterexample | GREEN evidence |
| --- | --- | --- |
| Default native, atomic replacement and new directory | `20260909T102037-f658309a0c73`, native diagnostic absent | `20260909T104002-a0ae049eea3a` |
| Ordinary material body cost and native idle reads | `20260909T104343-e5a8b7ad043c`, preserved v1 binary opens and reads the unknown binary material | `20260909T104355-04b804a7ae7d`, Linux IN_OPEN/IN_ACCESS trace with positive source-read control |
| Directory dependencies and output feedback | `20260909T104028-5ed73cfc0c6c`, log content writes cause repeated discarded candidates | `20260909T104343-7c4eadee8125`, accurate output and stable plugin count |
| Rescan after baseline and fallback during subscription | `/tmp/source-down-watch-v2-loss-red.log`, two controlled-interface failures | `/tmp/source-down-watch-v2-loss-green.log`, four component tests |
| One file shared by input, core, program and dependencies | `/tmp/source-down-watch-v2-dedup-red.log`, five acquisitions instead of one | `/tmp/source-down-watch-v2-dedup-green.log` |
| Explicit Poll | `/tmp/source-down-watch-v2-poll-red.log`, preserved v1 binary rejects --poll | Included in the combined run below |
| Native initialization resource fault | Real Linux inotify_init1 boundary returns EMFILE; this is controlled syscall failure, not natural host exhaustion | Included in the combined run below; explicit Poll proves zero initialization calls |

The complete watch matrix `20260909T120502-3388fc5a234e` passes all 34 watch
scenarios on Linux. It includes the preserved business cases and these additional
boundaries:

| Behavior | RED or counterexample | GREEN evidence |
| --- | --- | --- |
| Necessary native registration denied, explicit file still readable | `/tmp/source-down-watch-v2-permission-red.log` | `20260909T113842-5720e7a382c3`, diagnosed safe Poll fallback |
| Regular directory member permissions | `20260909T113836-fe82931c8a48`, repeated discarded candidates | `20260909T114518-bf8936994874` |
| Missing query and all missing parents | `20260909T110718-73aaf7b3003b` | `20260909T110845-1f21c2238ecf` |
| Publish blocker registered before actual cleanup | `20260909T110202-a057dce4d6df` | `20260909T110413-d8578c24d62d`, actual inotify registration identities |
| Known unchanged hints, regular file named target, identical crash marker | `20260909T114716-cca13e9c66c5`, both subcases fail | `20260909T114942-e1b5ea6b9265` |
| Unknown script link repair | `20260909T114943-5a83f0f53918` | `20260909T115209-657b5f71cdb8` |
| Plugin exits during next-round baseline | `20260909T115459-2ccb46b0bde9`, CLI exits 1 | `20260909T115633-e592878ae549`, repair wait and direct-child reaping; scanning cancellation also passes |
| Ordinary unknown script and excluded explicit program repaired during cleanup | Existing implementation passes the new handshake scenario | `20260909T115032-2c945b963546` |
| Input link redirect, escape, repair and later edit | Existing shared resolver passes | `20260909T115717-839f29b33cb1` |
| Controlled Rescan and notification-read EIO during publication | Actual notify reader/decoder is driven after the first page replacement | `20260909T115931-0fdeb509aec1`, ordinary Rescan completes; EIO preserves old index and completed ownership, then Poll recovery cleans owned pages |
| Six-language source edits in an isolated copy of this project | Existing full-generation path passes | `20260909T120127-e6316928d45e`, each page and default search refreshed |
| Missing/adversely linked adoption, outside-tree body reads and cancellation phases | Extended assertions use real files, native notifications and actual plugin PIDs | Complete 34-case matrix above |

`/tmp/source-down-watch-v2-fault-kinds-red.log` and its green run pin the difference
between runtime backend errors, invalid configuration and ordinary missing watches.
`/tmp/source-down-watch-v2-fault-merge-red.log` demonstrates a later missing-path
error erasing an actual backend fault; its green run has 17 component tests.
The same production interface verifies atomic pending exchange while the same path
receives another hint, restored subscriptions after rescan, and zero fact-sampler
calls on healthy control wakes. Repair acquires one cleanup comparison, then no
sampler calls during control-only waits.

The Linux notification publication fixture supplies an EIO or a controlled
IN_Q_OVERFLOW record to the real notify reader. Its next read confirms the previous
handler returned before publication resumes. This is controlled boundary evidence,
not a claim that the kernel naturally overflowed. In the matrix, the paired
publication scenario takes 1.80s including a deliberate 1.1s quiet window; the real
EMFILE/explicit-Poll/cancellation scenario takes 2.30s. Their command timestamps and
subtests retain the individual runs. These small-fixture wall times do not measure a naturally exhausted host.
Large-tree controlled rescan and fallback measurements are recorded below.

Local gates on the implementation: `mise run check` passes in 221.93s, with Rust
core 8815/9322 = 94.56%, Rust spec plugin 297/308 = 96.43%, and Python project plugin
112/118 = 94.92%. Its complete E2E run is `20260909T120636-092f64b0a294` (67 cases).
`mise run review` produces 184 pages. The separate `mise run acceptance` passes all
67 cases in `20260909T121109-f166e3b705e1` and renders the run's reading entry.

The first extracted-artifact run `20260909T121153-1dd27a3f486c` exposed a test
fixture assumption: lowering credentials could not traverse a private inherited
TMPDIR beneath /root. The CLI was not started in those two permission subcases.
Permission fixtures now choose the Unix shared temporary directory through the
ordinary project-construction interface; they do not change ancestor permissions.
This is a fixture correction, not product RED evidence. Both private-TMPDIR focused
cases pass in `20260909T121538-3ddf2220826d` and `20260909T121538-93738ff94756`.
`mise run release` then passes in 154.04s: actual extracted GNU binary execution,
native portability, relocated source rebuild and full E2E. The relocated 67-case
run is retained as `20260909T122323-0de1e96c638c`. Logs are
`/tmp/source-down-watch-v2-final-release-rerun.log`.
The extracted-binary E2E run is `20260909T122154-92d63cc77931`; it also passes all
67 cases. After the fixture correction, the full `mise run check` rerun passes in
227.55s with the same three coverage values and E2E run
`20260909T122212-daa94afcfd5a`.
The source archive SHA-256 is
`38138303da640c49effc45c2e127ae4d85393b9758aa71af904054b0965a6d4b`;
the GNU binary archive is
`95c20746d80137684b5c6e59b2ec8f3feeb75e81b27a16ad165ab8b309fbc2a9`.
These identify the locally verified artifacts before this evidence update.

## Performance declaration

`/tmp/source-down-watch-v2-budget.json` was saved after the first native tracer
bullet and before tuning parameters. Preserve that declaration alongside results.
Measure 1,000 files/10MiB and 10,000 files/100MiB, each with no directives, repeated
include and an external plugin. Record subscription time/handles, first publication,
known edits, unknown dependencies and restart p50/p95 latency, native healthy and
fault idle body access/digests/CPU/RSS, high volume/rescan and Poll costs.

Native quiet body opens, bytes and digests, and unknown body reads on a known-input
round, have zero budgets. Initial machine-dependent limits are 5% of one CPU core
at idle, subscriptions within 3s/15s for the two sizes, first publication within
10s/30s, known-change p95 within 3s, discovery/restart p95 within 5s and 512MiB RSS.
These are the original limits, retained unchanged in
[watch-baseline.json](watch-baseline.json). `tools/watch_benchmark.py`, invoked by
`mise run benchmark`, records the raw samples, body-access traces, CLI CPU/RSS,
handle/subscription counts and plugin initialization/batch counts.

The initial 10240-byte-per-file fixture totaled 9.77/97.66MiB. Its six passing
results remain in `.source-down/watch-benchmark/20260909T112826.159334Z/`; they are
not claimed to meet the larger minimum. The corrected fixture rounds each file
up from the original declared total bytes. Both selected and ordinary materials
are counted; each group selects 10 files and leaves the rest as ordinary material,
with 500 directives in include/external groups. This does not claim all 100MiB is
selected for rendering. Files are freshly written into a warm OS page cache.

Corrected result `.source-down/watch-benchmark/20260909T120625.241010Z/results.json`
passes all budgets. Each Native healthy/fault quiet interval has zero body access;
known-input rounds never open ordinary unknown bodies. The artifact separately
records explicit Poll healthy and recovery costs. IN_OPEN/IN_ACCESS events may
coalesce; nonzero event counts are not exact digest or byte counts. `/proc/io`
rchar includes notification traffic and is explicitly not used as a body-byte
counter. Zero native body activity is cross-checked with the counting sampler.

| Files | Workload | Actual MiB | Initial s | Known p95 s | New dependency p95 s | Config p95 s | Peak CLI KiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1,000 | none | 10.000 | 0.033 | 0.122 | 0.132 | 0.142 | 8,216 |
| 1,000 | include | 10.013 | 0.078 | 0.142 | 0.171 | 0.162 | 11,120 |
| 1,000 | external | 10.007 | 0.232 | 0.152 | 0.234 | 0.203 | 15,044 |
| 10,000 | none | 100.002 | 0.078 | 0.194 | 0.254 | 0.224 | 8,064 |
| 10,000 | include | 100.015 | 0.179 | 0.224 | 0.294 | 0.235 | 10,868 |
| 10,000 | external | 100.009 | 0.280 | 0.243 | 0.374 | 0.284 | 14,752 |

Five samples per latency category use nearest-rank p95. The 4500-file event burst
plus a new selected directory takes 0.232–0.324s across the six workloads. Directory
replacement takes 0.163–0.285s; a subsequent edit takes 0.162–0.275s, proving restored
subscriptions. These stress worksets extend the initial file counts. Results also
record first subscription/baseline time and resource counts; no timing constants
were relaxed to obtain these passes.

The final integrated `mise run benchmark` passes in 126.60s, including the existing
six generation workloads, search/read budgets and all six Native/Poll watch groups.
Its watch artifact is
`.source-down/watch-benchmark/20260909T122204.601875Z/results.json`.
The same notify-reader boundary now supplies controlled loss or EIO on both large
worksets, after the 4500-file stress extension. Rescan completion requires restored
subscription counts and replacement of the old native descriptors, not just a
callback receipt. All six rescan runs read only known bodies and cause zero plugin
initializations or calls; rescan takes 0.124–0.158s and 0.02–0.05 CLI CPU seconds.
Runtime EIO releases native subscriptions and reports Poll in 0.010–0.011s, with
zero business calls for unchanged facts. Explicit and runtime-fallback Poll each
have separate healthy/fault scan cost records. CPU ticks have 10ms resolution on
this host. The injected records/errors remain labeled controlled evidence.

## Design and defensive behavior review

The replacement retained full binary hashes, native identity, safe resolution and
source-byte ownership in one filesystem collector. Search projects the existing
closed format-1 fields. SourceStore preserves stream reads; sampling restricts
file facts to regular files. Existing composition, file-read, search, session and
publication tests verify the shared contracts, including the earlier FIFO
regression discovered during extraction.

| Guard or retained state | Invariant and evidence |
| --- | --- |
| Safe parents, missing-tail kind, link traversal limit and permissions | An unsafe or unreadable query remains an error with observable safe facts; the shared resolver preserves the prior 40-link bound. Link/permission/cleanup cases exercise it. |
| Per-sample query/kind memo | One acquisition can have multiple owners; it is discarded with the sample. The five-read RED became one acquisition without dropping owners. |
| Bounded callback paths, strongest fault, atomic take | Keep every delivered need to recheck without unbounded callback memory or losing a later same-path event; overflow becomes rescan. No callback file I/O or blocking business work. |
| Identity-aware add-before-remove coverage | A path name cannot stand in for a live directory registration. New coverage and a baseline precede retiring handles; controlled rescan and real replacement/later-edit cases verify this. |
| Quiet/max/control/Poll intervals | Bound coalescing and control latency while isolating periodic content scans to Poll. Native quiet body and sampler tests verify the distinction. |
| Unknown dependency preceding-fact gate | A response or directory event cannot prove earlier reads; unknown external dependencies rebuild the Session for the next complete round. The slow dependency-window case withholds old candidate publication. |
| Retained last complete sample and AttemptFacts | A fault during preparation, baseline, cleanup or publication cannot replace pre-failure facts with post-repair values. Actual file/cleanup handshakes and PID checks exercise the windows. |
| Consumed unknown-repair facts | A first safe hint can discover a repair; repeated identical facts cannot restart a crashed plugin indefinitely. Known hints are not promoted to unknown; links supply metadata without target bodies. |
| Publication progress, blockers and page ownership | Only completed operations advance ownership. Blockers are covered before cleanup, including generated paths; old index remains until all page operations complete. |
| Output projection and typed hints | Exact generated subtrees are excluded except for a concrete blocker. Only publication's recorded parent creation is projected away; regular member body/permission writes are not directory membership. |
| Adoption validation | Shared strict index decoding, matching scope, safe ordinary pages and matching hashes grant deletion ownership. Missing/corrupt/changed/linked material never grants guessed deletion rights. |
| Long-command scope and bounded fixture handshakes | One existing ProcessScope owns test children. Every wait has a deadline and finally releases its gate; actual plugin PIDs verify direct-child reaping. |

The removed independent hash/directory/resolution implementations are owned by
`filesystem`; search retains only its serialization projection. Native scheduling
contains no Recovery full-body scan or coverage shortcut. Full recovery body facts
are private to the explicit Poll adapter. No parallel business scheduler, second
plugin process owner, test-only product option or persistent ownership manifest was
introduced.

## Native CI follow-up

The first watch implementation commit `dc74d3a` failed the
[three-system run 34351468640](https://github.com/bolasblack/source-down/actions/runs/34351468640).
The retained logs distinguish four causes:

- macOS `file_read` rejected an absolute path through `/var` when the fixed root
  used `/private/var`. The shared filesystem resolver now identifies the actual
  project boundary before resolving the remaining spelling component by component.
  The readable root-alias case reproduced this on Linux in run
  `20260909T124549-ad9814214628` and passed in `20260909T124721-80e5427127b8`;
  it also rejects an in-project link escaping through the alias. The existing
  file-read, search and composition contracts pass unchanged.
- Five Windows watch cases used translated text logs or marker writes while
  asserting exact LF bytes. Their fixture writers now emit those exact bytes;
  batch counts, restart counts and quiet-window assertions remain unchanged.
- The Python project plugin compared lexical root prefixes when declaring its own
  script dependency. Windows extended and ordinary path spellings can identify
  the same directory. The plugin now matches that directory by `samefile` before
  returning its relative script path. The hot-reload scenario checks that declared
  fact in the published snapshot as well as the updated page and search result.
- Linux process-cleanup acceptance reproduced at iteration 8 locally. Diagnostic
  observation captured the kernel's `X` state, which the platform adapter had
  classified as running. `X`/`x` now map to exited, consistent with
  [the native process-state contract](https://www.man7.org/linux/man-pages/man5/proc_pid_stat.5.html).
  All external-process tests and 100 consecutive repetitions of the original
  failing case pass. The fixture's two-second deadline and direct-child reaping
  assertion are unchanged; temporary diagnostics were removed.

All 34 watch scenarios pass locally in run `20260909T124910-c0755617b097`.
The corrected implementation passes `mise run check` in 223.25s, including all
68 E2E scenarios in `20260909T125148-48dfef297f64`. Line coverage is 94.59% for
Rust core, 96.43% for the Rust spec plugin and 94.17% for the Python project
plugin. Documentation lint passes (53 documents, 76 normative clauses), and
`mise run review` publishes all 185 current pages.
The independent readable acceptance passes all 68 scenarios in 58.17s, run
`20260909T125938-da17576fa95e`. The corrected-head benchmark passes in 98.40s;
its six Native/Poll results are retained in
`.source-down/watch-benchmark/20260909T125658.719479Z/results.json`, alongside
the existing generation and search/read budgets.

The corrected-head GNU release passes in 150.28s. The extracted CLI runs all
68 scenarios (`20260909T125941-90ed6122ff96`). In the relocated source tree,
the extracted CLI and rebuilt project plugin also pass all 68
(`20260909T130107-eacb07fe1370`, retained in the caller's run directory).
The rebuilt CLI's complete rendered output matches the extracted CLI's output.
The archives precede this final evidence paragraph. Their SHA-256
values are `2334b7bd8f6768da43ed6e5a7f2b37b970843ebb3223a2d3c36d500a4ac1b72f`
for source and `d7568718c7ccb393a0f5efbec3cb28893c8dbf96c9bff4af9d39666b534e7e55`
for the GNU binary archive.

The alias resolver keeps link/error facts and the existing root-escape check;
the script collector owns dependency membership; platform owns process-state
classification. These changes add no retry, timeout, polling path or test-only
product control.

The next [native CI run 34354014025](https://github.com/bolasblack/source-down/actions/runs/34354014025)
passes Ubuntu (including coverage, review and benchmarks) and macOS on `7d7b34c`.
Windows passes the six previously failing watch cases and the new root-alias
scenario, but its configuration scenario encounters an index replacement error
while polling that file. This is retained as run `20260909T125932-5e6f038af7d5`.

Concurrent observation now uses one support reader with Windows read/write/delete
sharing. The configuration scenario deliberately keeps an old index reader open
across a complete new publication and verifies both old-handle and new-path bytes.
This also exposes the Windows publication primitive: `tempfile` 3.23 uses plain
MoveFileEx, whereas
[Rust 1.90's native rename](https://github.com/rust-lang/rust/blob/1.90.0/library/std/src/sys/fs/windows.rs)
supports replacement with shared readers. Publication uses that standard-library
primitive through platform, retaining temporary-file cleanup until successful
rename. Windows clears the temporary cache attribute before the rename, as required
for persistent output. Failure still records partial progress and preserves the old
index; no automatic publication retry or relaxed deadline is added. The single-file
reader semantics are explicit in SPEC-CLI-004.

The publication correction passes `mise run check` in 221.88s, including all
68 scenarios (`20260909T131737-4a4b0910d20e`). Coverage is 94.56% for Rust core,
96.43% for the Rust spec plugin and 94.17% for the Python project plugin. The
rebuilt CLI separately passes all 34 watch scenarios
(`20260909T131732-85297623b092`), including held-reader publication and partial
publication recovery; `mise run review` publishes 186 pages in 20.38s.

On `3338ec9`, independent readable acceptance passes all 68 scenarios in 57.99s
(`20260909T132759-325d4a693a9e`). The benchmark passes in 99.16s, preserving every
generation, search/read and Native/Poll budget. Its six watch workloads are in
`.source-down/watch-benchmark/20260909T132441.061203Z/results.json`, with CLI
SHA-256 `88bde0d07055a2037fce64879e957d17654162747855af785d420ebc97dcd543`.

The GNU release passes in 151.63s. The extracted CLI passes all 68 scenarios
(`20260909T132802-63add7f2ca67`); relocated source acceptance with that CLI and
the rebuilt project plugin also passes all 68 (`20260909T132929-4857c6bd1e25`).
The rebuilt CLI then produces exactly the same complete rendered output as the
extracted CLI. These archives precede this final evidence update: source SHA-256
`38dd0d9354c670072bc4c0289c6e4818408d2a9e2dd85211ce6f9e2039da03ef`, GNU binary
archive SHA-256 `3f095e6162f98b2a62b50205676bdb4d1be602bcce2aa4ec20a676e3de45c12f`.

The completed [native CI run 34357208180](https://github.com/bolasblack/source-down/actions/runs/34357208180)
passes all three jobs on the exact `3338ec9` commit: Ubuntu 24.04, macOS 15 and
Windows Server 2022. All jobs pass formatting, Clippy and native tests. Ubuntu
also passes the three coverage gates, documentation checks, complete self-review
generation and benchmarks. The macOS complete acceptance run is
`20260909T132914-7f73aca639b5`; Windows is `20260909T133059-bf7eb6536ca3`.
Both pass the held-index-reader configuration scenario. The Windows artifact
records the exact commit and matching scenario-source hash; its CLI SHA-256 is
`6c36fccac25d0e37ccc5d8eb9586df2c7837002d44a91f73c0de0f00d1036a38`.
Native artifacts include intentional failed runs from the failure-retention tests;
those are separate from each platform's passing complete acceptance run.

## Completion record

Implementation deviations: none identified against the owning clauses. The
permission diagnostic and known/unknown/link repair clauses were clarified before
the corresponding fixes.

Specification gaps: none currently unresolved.

Required plan evidence: complete, including native CI on all three systems.
Natural host-wide resource exhaustion and silently non-notifying filesystems
have not been measured; controlled EMFILE/EIO boundary failures and explicit Poll
are tested without requiring those environments.
