# E2E API composition verification

Proposal 004 is complete on Linux as of
2026-09-16. It changes the Python authoring API and its current callers. All required
local gates pass, including execution of extracted artifacts and relocated source.
Product specifications, Rust implementation, runner formats and coverage thresholds
are outside this change.

## Baseline and migration scope

The baseline is HEAD `5ba6303feb6f53d3a09d0dd4b83dd238b2be8dc4` plus the actual
2026-09-16 worktree: 82 added, 72 modified and 10 deleted staged files, no unstaged
tracked changes, and untracked `plans/`. The index is preserved. No other agent
was active at handover. Source bytes, SHA-256 identities, staged/unstaged patches,
the index listing and API call inventory are saved in
`/tmp/source-down-e2e-api-20260916/`.

Baseline discovery `20260916T195408-cb47599167d5` found **103 cases**, including
57 watch cases. Listing did not execute them. Proposal 003's completed 99-case
migration and its own historical gates are recorded separately in
[its delivery record](e2e-readable-suite-verification.md). Four subsequent watch
regressions belong to the current 103-case baseline.

| Existing call | Target | Preserved boundary |
| --- | --- | --- |
| Index assertions over render/output/bytes | Also accept `IndexView` | Saved bytes, no command or disk read |
| Raw search/simple read results | Shared explicit adapters | Process first, declared JSON only, single response versus traversal |
| Output/log/event waits returning booleans | Frozen successful observations | Original condition order, timeouts, exceptions and cleanup |
| Integer log position | Watch-owned checkpoint | Before-edit capture, interval matching, no event attribution |
| Runtime direct writes | `writeInPlace` where parents already exist | Bytes, file identity, permissions and action order |
| Runtime temporary write then replace | `atomicReplace` with the same temporary path | Temporary creation and replacement stay at the same point |
| Partial metadata `equals` | `fields` | Selected top-level keys, complete values |
| Render `outputFiles` | `includesFiles` | Presence of selected files, extras allowed |
| Notification a/z parameters and handled name | Fixed fixture and callback-returned name | Actual callback/recovery/publish/release boundaries |

Wait caller review keeps presence-only reads explicit. `test_discovery` checks the
captured changed index; the two configuration cases save the manifest observation
for their next edit; `test_configuration` checks the captured removal index; the
configuration read-window case checks the observed initialization bytes. All wait
conditions remain unchanged. Idle-window snapshots and post-presence reads remain
new reads because the previous wait did not capture their bodies or because the
case intentionally starts a later observation window.

## API evidence

The agreed helper boundary is a temporary ordinary case executed by the real
`tools/acceptance.py`. `tests/e2e_helpers_test.py` checks saved case outcomes,
reading generation, actual argv/counts and process cleanup. The local
`check_helpers.py` evidence wrapper only copies each run directory before the
fixture deletes its temporary checkout.

RED/GREEN runs are retained under the evidence directory:

| Slice | RED | GREEN and sensitivity |
| --- | --- | --- |
| Index composition | `red-index.log`: `IndexView` rejected by snapshot adaptation | `green-index.log`: all four input forms work after deleting the current index; wrong saved body fails |
| Search composition | `red-search.log`: raw results rejected | `green-search.log`: raw/wrapped results share checks; wrong count fails; non-JSON process checks work and requested JSON remains an error |
| Simple read composition | `red-read.log`: raw metadata lacks `.data`; wrong domain accepted | `green-read.log`: response matrix, wrong field/text/alias, wrong domain, multi-page rejection and copied JSON/raw facts |
| Output observation | `red-output.log`: repeated reads mix bytes and time out | `green-output.log`: one read per key, frozen bytes after deletion, empty success, presence/absence without reads |
| Log intervals | `red-log.log`: pre-entry checkpoint exposes missing process state | `green-log.log`: explicit ownership/lifetime/offset errors, stale-log rejection, frozen intervals and empty match |
| Events | `red-event.log`: boolean lacks the counted facts | `green-event.log`: captured substring count/bytes after deletion and wrong-body failure |
| Wait boundaries | Existing behavior preserved | `green-wait-boundaries.log`: short-circuit order, JSON/I/O errors, early exit/timeout cleanup, per-attempt cache, non-atomic paths, one log read and distinct search exit conditions |
| In-place saves | `red-in-place.log`: missing operation | `green-in-place.log`: UTF-8, CRLF, missing final newline, arbitrary/empty bytes, hard-link identity, symlink writes, permissions and missing parents |
| Atomic saves | `red-atomic.log`: missing operation | `green-atomic.log`: different-directory temporary file, replacement identity, exclusive creation, missing parents, write/rename failures and cleanup preserving the original error |
| Atomic link names | `red-atomic-link.log`: resolving the final symlink incorrectly rejects a different temporary name | `green-atomic-link.log`: resolve parents for equal-name rejection; replace the final name without following its link |
| Parameter names | `red-names.log`: `fields` and `includesFiles` unsupported | `green-names.log`: top-level subset with complete nested values, wrong/missing fields, artifact inclusion with extras, missing-file failure |
| Complete ordered lists | Existing behavior preserved | `green-complete-lists.log`: dependencies, paths and expansions each reject missing, extra and reversed items |

`helpers.log` records 35 external helper tests passing; `runner.log` records all
16 coordinator tests passing. The subsequent atomic-link boundary has its own
focused green run and is included in the final repository test gate.

## Migration review and controlled mutations

The save ledger (`save-migration.json`) reviews 80 original write calls: 65 become
explicit in-place saves. Of the other 15, the adjacent temporary write/rename in
`test_native` becomes one `atomicReplace` at the same point; 14 retain directory
creation or preparation semantics. The excluded-script replacement remains
prepared before watch starts. Its runtime `replaceFile`, the existing execution
repair rename, the two configuration move/restore sequences, hard links, symbolic
links, permissions, timestamp-preserving saves, native windows and releases remain
explicit. No native C/Python fixture changed.

`migration-audit.json` compares all 103 case sources against their actual baseline:
52 changed, all wait arguments and subTest arguments unchanged. Native operations
and release/cancellation/reaping calls are unchanged except the declared adjacent
atomic save. The original index entries are unchanged. Current API searches and
AST checks (including standalone generated Python strings) find no obsolete
keywords or aliases; complete-list `equals` remains. All 104 protected product,
specification, fixture, toolchain/runner and historical-plan files retain their
baseline hashes. Discovery retains every ID, title, spec list and platform
declaration.

Six bounded mutations change only disposable helper copies. Each makes the
external helper test fail; originals remain green. Exact replacements, before/
after hashes, preserved coordinator results and unittest logs are in
`mutations/summary.json` and the six neighboring run directories.

| Deliberate wrong implementation | Observed sensitivity |
| --- | --- |
| Remove `IndexView` adaptation | Valid saved-view case becomes a TypeError error |
| Re-read files while building the output observation | The one-read/frozen-byte scenario fails |
| Compare a selected nested metadata object as a subset | The wrong nested-value case unexpectedly passes, failing the outer contract test |
| Require the exact render artifact set | Valid subset and empty inclusion cases fail |
| Re-read stderr to compute the returned checkpoint | The saved interval and end offset disagree |
| Implement atomic replacement by writing into the target | The old hard link changes, failing the identity contract |

Local review found no product implementation deviation or specification gap.
Adapters have one owner per domain; the per-attempt byte map exists only to keep
conditions consistent. Checkpoint type/owner/offset guards distinguish invalid
usage before waiting. The temporary-created flag protects pre-existing files;
cleanup suppression preserves the original native failure. There is no new wait
engine, implicit success check, retry, fallback, command or product injection.

## Reading and gates

Watch run `20260916T201511-7b0e26ea5c8f` passes all **57** selected cases and its
reading verification, explicitly recorded as partial. The first sandboxed run
`20260916T201338-e009c0aa75b6` passed 55 and failed two before product startup:
the sandbox rejected their required `setgroups` call. Repeating unchanged tests
with native permission switching enabled passed both; neither was skipped.

`mise run review` passes and publishes **233 pages**. Review covered the six
changed support owners and generated case pages, including atomic saving,
captured manifest/initialization checks, pre-watch replacement preparation,
configuration move/restore and both callback/recovery scenarios. Their key inputs,
ordered saves, waits and exact expectations remain visible in the code/prose.
The real C fixtures remain included in the notification/configuration pages.

The initial `lint` completed fmt and Clippy, then the sandbox's read-only `.agents`
mount prevented the existing validator from regenerating its indexes. Its final
run uses the normal writable repository environment.

## Final gate evidence

Executable and test sources stayed frozen through these gates. Delivery records
and plan status were completed afterward; those reporting edits do not change the
tested API, fixtures or scenarios. Logs below are under
`/tmp/source-down-e2e-api-20260916/`; E2E results are retained under
`.source-down/e2e/runs/<run-id>/results.json`.

| Required command | Observed result | Evidence |
| --- | --- | --- |
| `mise exec -- python tools/build.py -- cargo build --locked --bins --examples` | PASS, current debug CLI and examples built in 3.28 s | Initial build command output; helper commands bind `target/debug/source-down` |
| `mise exec -- python -m unittest discover -s tests -p e2e_helpers_test.py` | PASS, 35 tests; later atomic-link check also passed | `helpers.log`, `green-atomic-link.log`; all 35 included in final test gate |
| `mise exec -- python -m unittest discover -s tests -p e2e_tools_test.py` | PASS, 16 tests | `runner.log` |
| `mise run build` | PASS, release CLI and spec plugin | `build.log` |
| `mise exec -- python tools/acceptance.py --list` | 103 discovered, no execution claimed; metadata unchanged | `baseline-discovery.json`, `final-discovery.json`, `final-list.log` |
| `mise exec -- python tools/acceptance.py --case watch --review` | PASS, 57 selected; partial scope and reading passed | `watch-native-permissions.log`, run `20260916T201511-7b0e26ea5c8f` |
| `mise run test` | PASS, 207 Cargo passes across 22 harness summaries, 76 Python tests, all 103 E2E cases | `test.log`, instrumented run `20260916T201553-ae363b222079` |
| `mise run lint` | PASS, fmt, Clippy and 57 documents / 76 unique normative clauses | `lint-native.log`; generated AGD indexes remain byte-identical |
| `mise run review` | PASS, 233 project reading pages | `review.log`, `.source-down/pages/` |
| `mise run acceptance` | PASS, all 103 cases, zero skips; 104 reading pages including index, 313 recorded commands | `acceptance.log`, run `20260916T201805-efb0a769c120` |
| `mise run release` | PASS, native x86_64 GNU Linux archive execution, portability, relocated source rebuild and matching rendering | `release.log`; extracted run `20260916T201906-ce604fad278b`, relocated run `20260916T202047-178b28ed6aba`, each 103 cases |

The three independent line-coverage gates remain at 90%. Measured coverage is
core **8874/9381 = 94.60%**, Rust spec plugin **297/308 = 96.43%**, and Python project
plugin **113/120 = 94.17%**. Machine reports are in `.source-down/coverage/`.

Release archive identities from `dist/SHA256SUMS`:

| Artifact | SHA-256 |
| --- | --- |
| `source-down-0.1.0-source.tar.gz` | `542222d585f86ce24b9f45e73c400a4943023a52759c5ec55633fd4aeda06551` |
| `source-down-0.1.0-x86_64-unknown-linux-gnu.tar.gz` | `e2344314f4e7a69e2dc91582b240afad8aa1b08a6ba33cb04b706cf1961e9c00` |

Release acceptance intentionally does not generate reading pages; the separate
full readable acceptance supplies that evidence. The retained one-case failing
run `20260916T202039-9edd97569d0d` is the developer-tool regression proving that a
failed relocated acceptance retains its evidence, not a failed product scenario.

No implementation deviation, unresolved specification gap or missing local gate
remains. macOS and Windows execution was not performed in this session; their
native behavior requires the corresponding hosts/CI. No platform skip was added.
