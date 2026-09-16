# Narrative E2E helper verification

Proposal 002 implements the complete UTF-8, guide-navigation and record-collision
scenario bodies. The owning tool contract is [Readable end-to-end acceptance](e2e.md).
Product implementation and specifications are unchanged. This record separates the
original design checks from execution evidence. All required local gates passed.

## Baseline and preservation

The starting HEAD is `5ba6303feb6f53d3a09d0dd4b83dd238b2be8dc4`, with the existing
uncommitted Proposal 001 implementation. Its complete acceptance run is
`20260909T221926-19545b8a506d`. All 113 saved source/specification hashes and both
supplied executable hashes were checked against the starting files. Original
scenario/support files, command and subtest records, and copies of the exact CLI
and spec plugin are retained in `/tmp/source-down-narrative-e2e-5ba6303/`.

The three scenario ASTs exactly match the approved Python blocks. Their IDs, titles,
owning clauses and action order remain. Other scenario bodies are unchanged; the
shared guide expectation file only updates its description to name its two refresh
callers. Its concrete expectations are unchanged.

| Scenario | Preserved evidence |
| --- | --- |
| UTF-8 continuation | Entity 88,062 bytes; file 88,074 bytes; four CRLFs and no final newline. Bad configuration/index unchanged. Three original requests use offsets 0, 32965 and 65965; response bytes match the baseline. Protection remains the index bytes and absent pages path. |
| Guide navigation | Same project, input list and two output subtests. All nine literal URLs, four exact source paths and the two distinct-page occurrences of `src/source.rs` match the original expectations. |
| Record collision | Same normal publication, first actual search hit, changed inputs, private zero-handle mutation and three failed commands. Every step protects the same complete old output; production source hashes remain unchanged. |

The three scenarios retain 11 actual commands, including the private mutant build,
and five subtests. The comparison normalizes only disposable project/mutant roots
and the actual first search handle, independently read from each run's raw search
response. It checks every flag, command order, exit code and completed cleanup.
`audit.py`, `audit-partial.json` and `audit-full.json` in the evidence directory
retain that comparison against both the focused and final complete runs.

The collision report changes exactly these three labels. The read argument remains
the first hit returned by the normal binary, rather than a computed or unique-hit
expectation.

| Original subtest parameter | Current subtest parameter |
| --- | --- |
| `command=['render', '0.md', '1.md']` | `operation='render changed inputs'` |
| `command=['search', 'needle', '--snapshot', '--json']` | `operation='search saved snapshot'` |
| `command=['read', handle, '--snapshot', '--json']` | `operation='read saved snapshot'` |

## Helper contracts and owners

| Interface | Implementation and verification |
| --- | --- |
| `renderSuccessfully`, `searchSuccessfully` | Existing actions execute once and return that observation. Shared ordinary run/index checkers serve both action and TestCase wrappers. Render checks exit 0, empty stdout and optional captured record count; search checks exit 0 only. |
| `withBinary` | A separate entry passes its bound binary through the existing project executor for render, search, handle reads and every file-read page. The original entry and context keep their binary. |
| `readEntityToEnd` | The existing continuation driver starts at offset 0, follows inspected responses and keeps its per-command and total budgets, stop reasons, raw pages and exception classes. |
| `assertCompleteUtf8Read`, `assertReadFromFile` | Both independently check every page's exit status. Existing page inspection owns cursor/range/termination checks; SourceRegion derives the full-file hash and exact unique selection from independent fixture bytes. |
| `assertPageLinks` | Existing navigation checks own generated-page lookup, literal URL presence, captured targets and exactly one named anchor. Additional links remain allowed. |
| `assertSourceExcerptsMatchOriginals`, `assertSameExcerptOnDifferentPages` | One shared matcher serves the existing and named assertions. Original byte slices, file links, page-level call sites, exact source set and count/distinct-page/range/body equality keep their separate scopes. |
| `assertRecordCollision` | Existing raw-stderr parsing checks exit 1, empty stdout, two distinct lowercase 64-hex record IDs and optional exact order. Failed query JSON is never decoded. |

No facade creates a TestCase, accepts an assertion callback, adds a command or retry,
or owns subtests. RunContext and ProcessScope remain the command/log and cleanup
owners. There is one success checker, one index-count checker, one page inspector
and one excerpt matcher. Existing public assertion forms retain live callers.

File-read checking retains the closed eight-field top level and five-field body;
it does not add value checks for id, format, language or format_version. Cursor
checks retain the exact integer and boolean conditions, with no page-count or
page-fill requirement. Excerpt evidence remains an original-byte and page-call-site
check; it does not prove independent entity selection, per-excerpt call association
or all displayed line numbers.

## RED, GREEN and bounded failures

Before replacement, the existing coordinator navigation/output-scope sensitivity
tests and collision diagnostic test passed. New external tests first failed for
missing success actions, local binary binding and named collision/read methods.
The actual UTF-8 and guide cases also failed when their new methods were absent.
These are missing harness-API RED states, not evidence of missing product behavior.
The owning engineering contract was updated before implementation.

The actual migrated cases passed with their own reading output:

| Case | Run |
| --- | --- |
| UTF-8 | `20260910T092211-51b50e453831` |
| Guide | `20260910T092703-933e2113bcb0` |
| Record collision | `20260910T092831-6529906bb452` |

The saved-copy developer tests exercise the real coordinator, status recording and
reading generation. Controlled Python responses and artifact edits are harness
probes; the product scenarios separately use the supplied real CLI and private
Rust mutant. Logs are retained in the evidence directory.

- Success probes reject nonzero exits, render stdout and wrong record counts with
  command context. Search help output passes without hidden JSON/hit validation.
  JSON decode and output-capture faults retain their original error classes.
- Binding probes cover raw and successful actions, all continuation pages, path,
  limit, snapshot and custom-output options, the unchanged default, and rebinding.
- Read probes follow actual returned offsets, stop on bad cursors/ranges/JSON, keep
  raw nonzero results, and independently fail either named assertion on exit error.
  Deadline probes preserve timeout logs, reap descendants and honor an override.
- Guide probes reject missing links, changed excerpts, wrong source sets, duplicate
  anchors and same-page repetition. Valid named reading assertions return `None`.
- Collision probes reject reversed/duplicate/malformed IDs, record/scope confusion,
  successful exit and nonempty stdout. Three-operation probes retain statuses
  failed/passed/passed after the first identity error, and failed/failed/failed when
  a new output file persists; later phases execute without resetting the baseline.

The initial full developer-tool run passed all 32 tests. Final gates below use the
completed code, including the explicit snapshot-option forwarding assertion.

The actual three-block collision scenario was also exercised in disposable copies,
using the supplied real CLI and freshly built Rust mutant. Changing only the first
expected handle produced failed/passed/passed in `20260910T095054-260e8f038c13`.
Adding a persistent output file after the first command produced three failures in
`20260910T095100-a190f411d6d8`. Restoring the exact source passed all three blocks in
`20260910T095105-e69fbfaf85ec`. Each run executed all six original commands, kept
the production source unchanged and generated its own reading pages. These runs
are retained under `collision-probes/` in the evidence directory.

## Project gates and remaining boundary

| Gate | Result |
| --- | --- |
| `mise run test` and three coverage gates | Passed in 249.22 seconds, including 57 Python developer-tool tests and the native E2E bridge. Core 94.57%, Rust spec plugin 96.43%, Python project plugin 94.17%. |
| `mise run lint` | Formatting, Clippy and documentation/AGD checks passed. |
| Complete readable acceptance | `20260910T094800-9e5d576280a3`: all 68 cases passed, 69 reading pages, all 113 saved source hashes match the final executable collection. |
| Full source review | `mise run review` passed and published 193 project pages. |
| Native release and relocated source E2E | `mise run release` passed in 149.77 seconds for Linux x86-64 GNU: extracted binary execution and relocated source rebuild. Retained run `20260910T095420-37029666bdf9` passed all 68 cases. |

This delivery runs on Linux. macOS and Windows runtime checks are not claimed, and
no remote CI is triggered. No commit or push is part of this implementation task.
Implementation deviations: none. Specification gaps: none identified for this
behavior-preserving slice. Missing required local evidence: none. The final plan
and delivery-record updates follow the recorded runs; their saved executable
scenario/support sources remain unchanged. All 31 local documentation links and
explicit anchors passed a separate check.
