# Default snapshots, short handles and current-file reads

This is the initial acceptance record. A later audit reproduced a required-null
storage defect (F1) outside its probes. The [integrity correction record](search-index-integrity-verification.md)
contains the repair and subsequent evidence; the original measurements below remain
historical observations, not a claim about concurrent platform work.

Scope: the 2026-09-08 user plan for default snapshot publication, CLI simplification,
64-bit public handles and current-file structural reading. The behavior owners are
[the search specification](../specs/search.md), [CLI](../specs/cli.md),
[material selection](../specs/standard-directives.md#spec-blt-007) and
[entities](../specs/entities.md). The original M2 measurements remain in
[search-verification.md](search-verification.md).

The implementation uses one handle owner and one material-selection owner. A Material
retains the original SourceFile used to build its tree. Include caches these materials
per canonical file within a round; direct reading creates one from the current file.
Each caller presents the selected facts. File reading does not depend on a Reader,
configuration, plugin routing or renderer output. Both read modes use the same body
slice and cancellable stdout owners.

## Test-first evidence

The default Session test failed when ordinary preparation did not produce an index;
the public roundtrip failed on the 129-character handle; accepted `--kind` and
`--max-chars` failed their usage-error tests. The first direct-file test failed with
`unexpected argument '--id'`. Each passed after its owning implementation changed.
Logs are `/tmp/source-down-cli-{a,b,c,d,e}-{red,green}.log` (some slices also retain
suite logs). The first file fixture's expected indentation/newline was corrected to
the declaration-token boundaries already defined by SPEC-ENT-006; the selector's
range behavior was preserved.

Public regression evidence is in [search tests](../../tests/search.rs),
[file-read tests](../../tests/file_read.rs), [publication tests](../../tests/publication.rs),
[Session publication](../../tests/session_publication.rs),
[include tests](../../tests/standard_directives.rs) and
[plugin composition](../../tests/composition.rs).

## Acceptance ledger

The 19 rows below retain the user plan's acceptance set.

| Row | Required observation | Runnable evidence |
| --- | --- | --- |
| 1 | Default render and Session publish, discard writes nothing | `spec_cli_004_default_session_publishes_only_complete_selected_rounds` and ordinary CLI fixtures |
| 2 | Rebuild replaces snapshot, new handle reads current content | `spec_srh_003_published_pages_reports_and_ordinary_render_are_part_of_freshness` |
| 3 | XXH64 and Base62 full-width vectors | `spec_srh_002_fixed_xxh64_and_base62_vectors` |
| 4 | Stable identity; changed snapshot with unchanged record | `spec_srh_002_short_handles_bind_snapshot_and_reject_old_forms` |
| 5 | Hit, scope, read, context and human handles | Search roundtrip, context and human-output tests |
| 6 | Both collision classes refuse publication and loading | `tools/handle_collisions.py`, run by acceptance |
| 7 | Invalid and old long handles fail; exact case lookup | Short-handle public tests |
| 8 | Three paginated lists and invalid/cross-target/cross-snapshot cursors | Scope, repeated-material and synthesized-source tests |
| 9 | Exact large UTF-8/CRLF/EOF snapshot continuation | `spec_srh_006_read_handle_continues_exact_utf8_snapshot_bytes` |
| 10 | Main-first context budget and occurrence selection | `spec_srh_006_context_is_adjacent_and_cannot_starve_the_main_body` plus repeated-material test |
| 11 | Format 1 loading, stale generator, historical read | `spec_srh_002_format_one_index_remains_readable_with_new_handles`, actual pre-change fixture |
| 12 | Close, preparation, partial publication, last-index and cancellation faults | Search, publication and Session publication suites |
| 13 | All kinds, paths, ranking, counts and limits | Search suite and five predeclared top-k queries, with the user-approved source criterion below |
| 14 | Removed flags rejected; help and early usage checks agree | CLI usage tests and direct-file option-conflict matrix |
| 15 | Files read without generation, config, index or plugins | `spec_srh_007_no_config_index_plugin_or_render_exclusion_dependency` and acceptance |
| 16 | Explicit modes and root containment | `spec_srh_007_explicit_mode_and_root_containment_are_unambiguous` |
| 17 | Shared six-language/Markdown structure and raw source | Six-language include comparison, Markdown/path and selector-error tests |
| 18 | Current-file continuation, relative offsets and changed versions | Fixed-budget file test and current/historical comparison |
| 19 | Closed JSON, classification and executable quoted continuation | Exact Python JSON, human shell execution and actual flush-failure tests |

The controlled collision check changes only a temporary source copy to produce a
constant hash. One-record and two-record projects force record-scope and record-record
collisions. Real mutant render/search/read commands exit 1, expose both full targets
and the conflicting handle, emit no stdout and preserve every previous output byte
without temporary-file residue. `/tmp/source-down-cli-collision.log` records both PASS
results. This is injected fault evidence; normal XXH64 behavior is checked separately
by vectors and real roundtrips. No runtime hash option or environment switch exists.

## User-approved query criterion

Removing `--kind` changes the candidate set. The existing scoring and tie ordering put
the include expansion of `code_span` ahead of its source-page code record. The first
full check and extracted-release acceptance therefore failed the original kind/input
assertion. The user explicitly accepted this top result because it contains the full
implementation, and requested that ranking remain unchanged.

The [original predeclared query file](search-queries.json) is preserved byte-for-byte.
For this query, `top_k = 1` remains required: acceptance checks only the first hit,
requires its one source to equal the actual function's exact path, bytes and lines in
`src/render.rs`, then reads that hit's handle and checks the complete contiguous
function bytes in the returned body and the same source span. Neither kind nor the
occurrence's generated page is restricted. Other queries retain their original
criteria and top-k values. Section 7 of the user plan records the same clarification.
The original failure log is `/tmp/source-down-cli-query-adjustment-red.log`.

The revised real CLI acceptance passes at default and custom output roots. For the
current fixture, the first hit points to `src/render.rs`, bytes `[418,680)`, lines
14–22; its handle reads the complete 262-byte function. Query ranking implementation
and the original query JSON match their pre-clarification SHA-256 inventory.

## Dependency and design audit

`xxhash-rust = 0.8.15` is pinned with default features disabled and only `xxh64` enabled.
Its [published manifest](https://docs.rs/crate/xxhash-rust/0.8.15/source/Cargo.toml)
has no normal transitive dependencies; the crates.io release metadata reports
2024-12-30T00:30:43.667195Z, not yanked, BSL-1.0. The OSV crates.io screen returned no
vulnerabilities; optional GitHub advisory lookup did not succeed and is not counted
as evidence. Raw screen: `/tmp/source-down-short-handle-dependency.log`.
The [official XXH64 API](https://xxhash.com/doc/v0.8.3/group___x_x_h64__family.html)
and fixed vectors establish the classic seeded 64-bit algorithm. Encoding rules live
only in SPEC-SRH-002.

| Design gate | Result |
| --- | --- |
| P1 | `--id` explicitly selects current-file mode; JSON labels current file and snapshot separately. |
| P2 | Full snapshot/record hashes and cursor identities remain intact; file results retain complete file hash and selected SourceSpan. |
| P3 | Handles, material selection, publication and stdout each have one owner. |
| P4 | Mode dispatch uses the supplied option; lookup uses the exact derived map; byte boundaries and scalar budgets use their actual units. |
| P5 | Shared selection replaces duplicate parser paths; file reads never reconstruct entities from search fragments. |
| P6 | Current call sites use ordinary render, all-kind query and fixed-budget read. Historical evidence and explicit rejection tests account for old interface names. |

Added guards protect map collisions, exact handle lookup, strict selector decoding,
file-mode option compatibility and cancellation at material/output boundaries.
Existing SourceStore containment and text validation own path and source errors;
Tree owns ambiguity, candidate completeness and range selection. Shell quoting
preserves selector/root/file values, including leading hyphens and quotes.

Removed index booleans controlled an optional product mode; every successful round
now builds one snapshot. Candidate index Option still represents a failed check with
reports only. Removed kind filtering does not remove Kind facts or identifier ranking.
Removed configurable body limits retain their boundedness protection in one fixed
constant. Long-handle parsing is replaced by exact map resolution; complete identity
validation and cursor binding stay at their existing owners. Include's cached tree
now retains its source facts as a Material, with the same per-round lifetime. No
additional retry, timeout, fallback parser or persistent history registry was added.

## Initial task results

Commands use the pinned mise environment; this host sets
`MISE_DISABLE_TOOLS=java MISE_CACHE_DIR=/tmp/source-down-mise-cache` to bypass unrelated
global Java discovery and use a writable mise cache. Later tasks set
`TMPDIR=/root/sidework/source-down/target/task-tmp` after the host's 8 GiB `/tmp` filled.
Only completed validation build artifacts were relocated to recover temporary space;
the failure to start that sandbox was an environment failure, not a product RED.

| Command | Result |
| --- | --- |
| `mise run check` | PASS; all Rust/Python tests and static checks. Rust core 5990/6266 lines (95.60%), Rust spec plugin 297/308 (96.43%), Python project plugin 110/114 (96.49%). Every required scope exceeds 90%. |
| `mise run review` | PASS; 81 selected pages, current spec report and complete search index. |
| `mise run acceptance` | PASS; 984771 Markdown bytes across 82 pages/reports; five top-k queries at both output roots, direct-file continuation and both public collision fault classes. |
| `mise run benchmark` | PASS; six generation workloads, including default Session publication, and both search workloads within all original time/RSS budgets. Current-file CLI and parsing/selection measurements are separate. |
| `mise run release` | PASS; extracted binary, clean offline relocated source build, self-use, file reads and collision checks. Local archives/checksums are in `dist/`. |

Raw command logs: `/tmp/source-down-cli-{check,review,acceptance,benchmark,release}.log`.
The standalone real-plugin pagination probe in `/tmp/source-down-cli-pagination-probe.log`
collected all seven source paths, seven distinct occurrences and seven input paths
through the returned cursors, comparing each complete list with its authored fixture;
all three passed without omissions or duplicates.

## Initial measurements

[search-cli-measurements.json](search-cli-measurements.json) is a copy of the final
benchmark result. It preserves all individual process samples, stage timings, source
sizes, platform details and original budgets. Process starts are fresh; OS caches are
retained. Build time includes generation and final snapshot publication.

| Workload | Inputs / bytes | Records / occurrences | Index bytes | Build s, first / repeat | Query s, first / repeats | Snapshot read s | Current-file read s | Peak RSS KiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Self-use | 81 / 702762 | 633 / 646 | 1257753 | 0.2035 / 0.1938 | 0.0387 / 0.0379 / 0.0371 | 0.0201 / 0.0193 | 0.00268 / 0.00250 | 27584 |
| Enlarged | 100 / 699500 | 20001 / 20500 | 10155461 | 0.5662 / 0.5664 | 0.5594 / 0.5560 / 0.5646 | 0.4912 / 0.4723 | 0.00102 / 0.00083 | 244216 |

The first query's load/freshness/ranking/result times are respectively
0.015165/0.002966/0.016670/0.000128 s for self-use and
0.461056/0.002468/0.051144/0.014160 s for the enlarged fixture.
Independent file read/parse/select/hash/slice work takes 0.00178 s for the SourceStore
selection in `src/model.rs` and 0.000124 s for the first Retry policy section in the
enlarged fixture. These are not snapshot load timings; the existing 3 s / 5 s read
budgets also bound the separate current-file CLI measurements.

Independent acceptance: **PASS**, 19/19 rows with no FAIL or UNVERIFIED entries.
The fresh validator received the frozen user requirement plus its later clarification,
the 19-row ledger and an isolated checkout; it excluded implementation narratives.
It ran 69 focused integration cases, two handle unit cases, all 186 Rust tests,
debug/release builds, fmt, Clippy, documentation and public acceptance, including both
collision fault classes. Its own top-1 probe confirmed the 262-byte function and exact
source span. [The full report](search-cli-independent-verification.md) records commands
and results. The parent independently repeated the SHA-256 inventory comparison:
140 expected authored files, zero missing, zero changed and zero unexpected authored
files; normal generated artifacts were excluded. That validator reported no open
findings; the later F1 audit and correction are linked above.

Implementation deviations: none adopted.

Specification gaps: none unresolved. The candidate-set acceptance conflict was resolved
by the user's explicit source-based top-1 criterion, preserving the ranking contract.

Missing evidence at this stage: the required-null omission case was not covered.
Its later regression and acceptance evidence are in the integrity correction record.

Limits: collision detection covers one current snapshot, not every historical
snapshot pair. File calls read current bytes independently; callers must compare file
SHA-256 and selection before concatenating pages. Tests and predeclared queries prove
their observed cases, and performance measurements retain OS caches. Generated pages
prove generation of their selected inputs, not complete semantic retrieval.
