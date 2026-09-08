# Search implementation evidence

This is the original M2 acceptance record. Current CLI and file-read results are in
[search-cli-verification.md](search-cli-verification.md); measurements below retain
their original scope and are not measurements of the updated interface.

Scope: the complete M2 search design and implementation plan, with product behavior
owned by [the search specification](../specs/search.md). Verification date: 2026-09-08.
The eight core acceptance rows passed independent verification. Final task results
and the publication recheck are recorded below.

The public acceptance boundaries are the real CLI, temporary project files, real
external plugin processes, output publication, and the existing public Session API.
The plan and repository work rules already authorize these seams.

## Design checks

The proper-fix gate was applied before each public behavior slice; each slice first
failed at the real CLI/file/process boundary, then passed with its implementation.

| Gate | Resulting design |
| --- | --- |
| P1: truthful names | `render --index` requests an additional published artifact; `--snapshot` explicitly skips current-fact checks. |
| P2: complete facts | Record bytes, exact mappings, provenance, occurrences, call sites and plugin identities stay distinct. |
| P3: one owner | The engine supplies validated blocks; search owns snapshot/query/read facts; publication owns every output replacement. |
| P4: actual invariant | Current reads compare bytes, identities, discovery and declared dependencies, independent of timestamps and plugin reruns. |
| P5: causal scope | Shared output preparation handles index, pages and reports; one snapshot validation boundary protects all readers. |
| P6: resulting system | Current contracts describe stored records and complete generation; the path-only `config_materials` field was replaced by retained configuration source facts. |

The smallest measured implementation uses one canonical JSON file and a deterministic
record scan. It adds no service or database. The query scan's `ponytail:` comment names
the measured budget and the condition for considering an inverted table.

## Baseline and predeclared queries

[search-baseline.json](search-baseline.json) records M1's measured file and byte counts,
the enlarged fixture and time/RSS budgets before index implementation.
[search-queries.json](search-queries.json) declares the self-use query expectations before
query implementation. Measurements must separate build, load, current-fact verification,
candidate/rank, and snippet/JSON time; first and repeated processes both count.

SHA-256 uses sha2 0.10.9. The dependency screen passed with OSV's `crates.io` ecosystem
name; the skill script's `cargo` spelling gives OSV HTTP 400. OSV returned no advisories
for the selected version. The [upstream release documentation](https://docs.rs/crate/sha2/0.10.9)
dates this release to 2025-04-30, beyond the 30-day age minimum.
The [historical SHA-2 advisory](https://rustsec.org/advisories/RUSTSEC-2021-0100.html)
is patched from 0.9.8. Raw screening logs are under `/tmp/source-down-search-*-check.log`.

## Acceptance ledger

The runnable cases are in [tests/search.rs](../../tests/search.rs) and
[tests/publication.rs](../../tests/publication.rs). The independent validator received
only the original requirement, its eight-row ledger, the normative specifications and
an isolated repository copy. It ignored implementation narratives and compared the
authored file inventory before and after its commands: all 132 files stayed identical.

| Plan row | Status | Machine evidence |
| --- | --- | --- |
| 1 | PASS | Selected code/prose, unreferenced Markdown, real-plugin expansion/appendix/report tests; independent unselected-material query returned zero. |
| 2 | PASS | Six real language files, Chinese/English, snake/camel names, special path encoding and repeated-heading tests. |
| 3 | PASS | UTF-8/CRLF/EOF reads, cleaned-comment byte mappings and Markdown entity/emphasis/code mappings; independent byte chunks `0..12` and `12..49` reconstructed the exact Chinese/English body. |
| 4 | PASS | Seven repeated occurrences and seven-source pagination; independent two-plugin probe kept distinct records, provenance and a zero-source plugin owner. |
| 5 | PASS | Corruption/version/old-handle/usage/zero-result tests; plugin start counters stayed `1/1` across search and reads; bounded lists and blocked-stdout cancellation passed. |
| 6 | PASS | All five freshness cases passed: equal-size/mtime edits, add/delete/rename, config, file/directory/link dependencies, pages/reports and ordinary render. |
| 7 | PASS | Real publication I/O failures and SIGINT at report, page and final-index boundaries preserved the old snapshot; hard links, missing file dependencies and excluded output inputs were rejected. |
| 8 | PASS | Fixed ranking/filter/count/context/continuation cases; independent metadata-only hits had `body_range=null`, and filtered counts agreed. |

The independent pass ran `cargo test --locked --test search -- --nocapture
--test-threads=1` (26 passed), `mise run lint`, `mise run build` and
`mise run acceptance` (five predeclared queries passed). Subsequent public regression
cases cover project-root output and final stdout flush errors. The latter failed first
against `/dev/full` with exit `0` instead of `1`; the same four search/read and JSON/human
checks pass after making the output owner propagate its final flush result.

Independent verdict: **PASS** for all eight core rows. The prompt boundary is not a
permission sandbox; the unchanged authored-file inventory is the evidence that this
validator did not edit the checked implementation.

Final publication/freshness recheck: **PASS**. A fresh validator checked rows 6–7 on
the updated output-root and directory-fact implementation. It ran the 27-case search
suite, the complete Rust test suite after building the project plugin, fmt, check,
Clippy, documentation validation, release build and self-use acceptance. Independent
equal-size/mtime, add/delete/rename and configuration probes each returned exit `1`
for current reads and `0` for snapshot reads. All 133 authored files stayed identical.
Its first direct full-test invocation lacked the debug spec-plugin executable;
building examples and rerunning both the affected nine tests and the full suite passed.
The later stdout flush fix was verified separately by the red/green public regression
and the final 28-case search suite within `mise run check`.

## Final task evidence

Commands use the repository's pinned mise environment. On this host, the prefix
`MISE_DISABLE_TOOLS=java MISE_CACHE_DIR=/tmp/source-down-mise-cache` avoids an unrelated
global Java lookup and places mise's cache in a writable directory.

| Command | Result and artifact |
| --- | --- |
| `mise run check` | PASS; all tests including 28 search cases; Rust core 5823/6117 lines (95.19%), Rust spec plugin 297/308 (96.43%), Python project plugin 110/114 (96.49%). Each required scope exceeds 90%. Reports: `.source-down/coverage/`. |
| `mise run build` | PASS; locked optimized CLI and examples. |
| `mise run review` | PASS; all enabled project plugins, 77 selected pages plus the spec report and complete search index. |
| `mise run acceptance` | PASS; 927955 Markdown bytes across 78 pages/reports; five predeclared top-k queries at both default and custom output roots, exact reads, bounded continuation, source links and four fault mutations. |
| `mise run benchmark` | PASS; six generation workloads and both search workloads meet their time/RSS budgets. Raw results: [search-measurements.json](search-measurements.json). |
| `mise run release` | PASS; extracted binary, clean relocated source build and self-use. Archives and checksums: `dist/`. |

The local command logs use `/tmp/source-down-search-{check,build,review,acceptance,benchmark,release}.log`.
The stdout regression's red/green logs are `/tmp/source-down-search-stdout-{red,green}.log`.

## Measurements

The raw measurement artifact is an unchanged copy of `.source-down/benchmark.json`.
It includes tool versions, platform, process wall/user/system time, peak RSS and every
first/repeated sample. Each query/read starts a fresh process; OS caches are retained.
Generation measurements include preparation and publication, and default reads include
current-fact verification.

| Workload | Inputs / input bytes | Records / occurrences | Index bytes | Build seconds, first / repeat | Query seconds, first / repeats | Read seconds, first / repeat | Maximum RSS, KiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Complete self-use | 77 / 655758 | 612 / 625 | 1188582 | 0.241 / 0.190 | 0.0340 / 0.0337 / 0.0334 | 0.0184 / 0.0186 | 27068 |
| Enlarged fixture | 100 / 699500 | 20001 / 20500 | 10155359 | 0.527 / 0.546 | 0.544 / 0.540 / 0.544 | 0.472 / 0.466 | 244008 |

Source material totals are 798467 and 699541 bytes respectively. Deduplication preserves
all occurrences while sharing 13 self-use and 499 enlarged-fixture content copies.
The first query's internal stages are separated below; process wall time additionally
includes startup, bookkeeping and teardown.

| Workload | Load, seconds | Current facts | Candidate/rank | Snippet/result construction | JSON encoding | Query result bytes |
| --- | --- | --- | --- | --- | --- | --- |
| Complete self-use | 0.014118 | 0.002749 | 0.015231 | 0.000109 | 0.000019 | 13710 |
| Enlarged fixture | 0.452955 | 0.001738 | 0.046119 | 0.014489 | 0.002188 | 11479 |

The preimplementation M1 baseline had 69 inputs / 513253 bytes and rendered in 0.141 s.
Current self-use includes the search implementation, tests and guide as well as index
construction, so those two timings do not isolate index overhead. The predeclared
self-use budgets are 15 s build, 3 s query/read and 262144 KiB RSS; enlarged budgets are
30 s, 5 s and 524288 KiB. All samples pass. Snapshot loading dominates the enlarged
query, while record scanning stays within budget; the evidence supports retaining the
single-file scan for this scope.

## Defensive behavior audit

| Owning boundary | Protected concern |
| --- | --- |
| Snapshot loader | Strict JSON, closed objects, format/hash identity, record identity, valid ranges, ordered occurrences and referenced paths reject corrupt persisted facts before query/read; historical mode retains these checks. |
| CLI/read options | Numeric bounds, nonempty query, relative filters, UTF-8 offsets and incompatible cursor options preserve the documented usage errors. Handles and list cursors bind snapshot, record and list so a rebuilt index cannot redirect an old handle. |
| Freshness | Full byte hashes, canonical targets, file identities, selection rescans, complete dependency facts and published output/report checks protect the stated current-file guarantee. |
| Directory facts | Applying known writes, removals and parent creation describes successful publication, including missing/NotADirectory transitions; all other members remain checked. |
| Publication | Shared target/temp preparation, source/config/file-dependency path ownership, hard-link identity and ancestor/parent checks prevent overwriting material. Last-index replacement preserves the old snapshot when prior publication fails. |
| Text positions | Parser positions and byte-equal mapping runs retain authored CRLF/UTF-8 boundaries; synthesized text keeps provenance without asserting a verbatim source mapping. |
| Bounded reads | Main-body-first budgets, finite adjacent context and independently paginated metadata keep responses bounded while permitting complete continuation. |
| Stdout | Nonblocking writes, EINTR handling and bounded poll waits observe cancellation on a stalled pipe; explicit final flush propagates write errors. Original file flags are restored by the output owner. |

Removed defenses were checked separately. Configuration write protection now derives
from the retained configuration SourceStore rather than `config_materials`.
Report enumeration moved to `publication::report_files`, preserving owner/name/type
validation for pruning and freshness. Shared output exclusions preserve existing rules
and add the owned search subtree. Large source mapping arrays remain complete inside
the index; public results expose the specified mapping capability plus paginated origins.
No other defensive behavior or product concept was removed; no expedient fallback was adopted.

## Scope and limits

Implementation deviations: none adopted. The plan's optional inverted table was not
needed within the recorded budgets; the public result contract does not depend on it.

Specification gaps: none unresolved for this delivery. Storage fields, mapping
capabilities, continuation, directory facts and stdout failure behavior were fixed in
their owning clauses before the corresponding acceptance checks.

Missing evidence: none for the planned acceptance scope.
Recorded tests prove their fixtures and the five predeclared queries. Filesystem matches
do not establish undeclared external plugin facts, atomic checkout capture or complete
semantic retrieval. Performance runs retain OS caches and report that condition explicitly.
