# Search index storage integrity correction

Scope: F1 in `/tmp/source-down-completion-audit-by5m0wqe/REPORT.md`.
The original audit is retained unchanged. Its reproduced failure supersedes the
earlier claim that no search-plan findings remained open.

Status: **PASS** on 2026-09-08. The required-field defect is fixed; the final shared
source passes the aggregate checks and the independent validator's 173-command
matrix. The earlier compilation and source-to-binary evidence gaps described below
are closed.

## Contract and implementation

[SPEC-SRH-002](../specs/search.md#spec-srh-002) requires closed storage objects,
explicit null fields, complete effective configuration and SHA-256 of canonical
stored content excluding `snapshot`. [SPEC-SRH-003](../specs/search.md#spec-srh-003)
requires the same integrity checks in default and snapshot modes. These clauses
already define the required behavior; no specification change is needed.

[Reader::open](../../src/search/mod.rs) retains the parsed JSON and requires
serialization of the decoded index to equal that original value before accepting
its identity. This rejects missing fields that Serde otherwise fills with `None`
or configuration defaults. The existing canonical SHA-256 calculation therefore
operates on the same object as the stored JSON. Required fields remain enforced
even when an altered object has a recomputed snapshot. The original JSON is released
after this comparison. No CLI-specific or per-field exception is added.

The P1–P6 design check keeps invalid storage separate from freshness; preserves
missing versus explicit null; puts validation in the common loading owner; compares
the complete stored value; covers occurrence, dependency-state and effective-config
fields together; and describes the current storage invariant. The added check
protects lossless decoding. Existing strict JSON parsing, typed schema validation,
content identity, record/source validation, collision detection and freshness checks
remain in place. No dependency, duplicate schema or product switch is added.

## Reproduction and regression

The first public CLI test failed with `left: Some(0), right: Some(1)` after omitting
`occurrence.plugin:null` while keeping the stored snapshot. The same test passed
after the loader change. Logs are `red.log` and `green.log` under
`/tmp/source-down-index-integrity-fix/`.

The expanded [search test](../../tests/search.rs),
`spec_srh_002_storage_fields_cannot_be_omitted`, runs a real render with a plugin
report, a directory dependency on a file and a file dependency on a directory.
It covers nine nullable locations, including all four occurrence fields and all
three dependency-state fields, plus seven complete-configuration fields. Each
omission is checked with unchanged and recomputed snapshot hashes through
search/read × default/snapshot: 128 negative invocations, all requiring exit 1,
empty stdout and an index/rebuild diagnostic. Four positive invocations preserve
explicit nulls, change JSON whitespace and Unicode escape spelling, and still return
the exact original body or search result.

The full search suite passes 34 tests, including the saved format-1 fixture,
freshness, source/cursor identity and publication failures. Logs are `matrix.log`
and `search-suite.log` in the same evidence directory.

## Final command evidence

Commands use the pinned mise environment, with `MISE_DISABLE_TOOLS=java`,
`MISE_CACHE_DIR=/tmp/source-down-mise-cache` and
`TMPDIR=/root/sidework/source-down/target/task-tmp`. Inherited `CC`, `AR` and GNU/musl
linker variables are cleared so `tools/build.py` selects the target toolchain.

| Command | Observation | Log in the evidence directory |
| --- | --- | --- |
| `mise run check` | PASS: 187 Rust tests, 24 Python tests, fmt, Clippy and documentation; core 6094/6380 lines (95.52%), spec plugin 297/308 (96.43%), Python plugin 110/114 (96.49%) | `final-check.log`, `final-coverage-summary.json` |
| `mise run review` | PASS: 85 selected pages, spec coverage report and current search index | `final-review.log` |
| `mise run acceptance` | PASS: five predeclared top-k queries at both output roots; 1,036,584 Markdown bytes across 86 pages/reports; file reads, four publication mutations and both collision classes | `final-acceptance.log` |
| `mise run benchmark` | PASS: six generation workloads and both search workloads within the original time/RSS budgets | `final-benchmark.log`, `final-benchmark.json` |

These final runs include `drop(value)` and the completed Linux stderr-drain changes
from the parallel platform task. The 152 authored files captured before the runs in
`current-final-manifest.json` remained byte-identical through check, acceptance,
benchmark and the current-release CLI replay below. Updating this evidence document
afterward does not change the validated code. Earlier successful command logs and
measurement files remain as historical observations.

The predeclared query file and ranking implementation are unchanged. Acceptance
still requires `top_k = 1` for `code_span`, its exact source span in `src/render.rs`,
and the complete function bytes read through the first hit's handle, as recorded in
the [user-approved criterion](search-cli-verification.md#user-approved-query-criterion).

## Performance

The final enlarged fixture has 20,001 records, 20,500 occurrences and a 10,155,461-byte
index. Query invocations take 0.5811/0.5756/0.5749 s; snapshot reads take
0.5073/0.5092 s. Maximum query/read RSS is 232,696 KiB, below the original
524,288 KiB budget. Self-use queries take 0.0415/0.0397/0.0434 s; reads take
0.0232/0.0233 s. Current-file reading remains measured separately.

The first passing performance run retained the original JSON until `Reader::open`
returned and reached 329,076 KiB on the enlarged fixture. Releasing it after the
comparison avoids retaining that duplicate through subsequent identity/freshness
checks. Both runs and the unchanged budgets are retained; earlier published
measurement files are preserved. Measurements use fresh processes with OS caches
retained and prove only the measured workloads.

## Fresh-build independent verification

A fresh validator received only the specification excerpts and the F1 requirement
ledger. It designed criteria before reading the implementation and ran its own real
CLI fixtures after a locked build from the frozen source copy
`target/task-tmp/index-integrity-final-qik38855`. Its report and complete command
records are `/tmp/source-down-index-integrity-fresh-build/REPORT.md` and
`cli-matrix.json`; `CRITERIA.md` preserves the predeclared criteria.

| Requirement | Verdict | Machine evidence |
| --- | --- | --- |
| R1: required occurrence and dependency-state fields | PASS | Seven nullable fields × two snapshot variants × four command modes: 56 rejections, all exit 1 with empty stdout and index/rebuild diagnostics. |
| R2: complete, closed stored configuration | PASS | Nine fields and one unknown field × two snapshot variants × four modes: 80 correct rejections. |
| R3: canonical identity, explicit null and reformatting | PASS | Omission probes reject with both unchanged and recomputed identities. Eight valid explicit-null/reversed-key/pretty/escaped-JSON commands return exact results. |
| R4: format 1, freshness and ordinary corruption | PASS | 26 commands: 20 corruption rejections, two default freshness rejections, two historical successes and two saved format-1 successes. Four focused integrity tests also pass. |
| R5: fresh source build and fixed executable | PASS | Locked bins/examples build exits 0; all 173 CLI invocations use the immediately copied executable whose SHA-256 is recorded below. |
| R6: source-to-build correspondence | PASS | All 148 authored files match the frozen manifest before and after validation; no missing, extra or changed files. Formatting passes. |

The independent build's executable SHA-256 is
`9082c235766291cfe82eff98ec99fe0af53ab7d65b023f6c312d71aa197b0fc5`.
The full matrix contains 173 commands: R1–R4 plus one render and two baseline calls.
Every expectation passes. Build logs, binary hashes and before/after source manifests
are retained alongside the report.

## Current-release replay

The shared source later received platform-task changes, so the frozen-copy result
alone does not claim correspondence with the final shared tree. The parent ran the
final aggregate checks above and replayed the independent CLI probe against the
current release build. Only the script's evidence-directory and checkout-path
constants changed; its assertions and fixtures remain identical.

Evidence is in `/tmp/source-down-index-integrity-current/`: `source-manifest.json`,
`binary-sha256.txt`, `cli_probe.py`, `cli-probe.log`, `cli-matrix.json`,
`cli-matrix-summary.json` and `final-provenance.json`. The copied
current release executable has SHA-256
`86ae935c07f51ab2d74d95813b76ce50d7797edfdacfa5cdc3036d9b130c3767`.
All 173 commands pass again, with the same R1–R4 counts and expected results.
All 152 captured authored files remained unchanged through this replay. This parent
replay closes correspondence with the final shared source; it is distinct from the
validator's independent frozen-source run.

## Retained earlier failures and evidence limits

The first independent runtime report,
`/tmp/source-down-index-integrity-independent/REPORT.md`, remains unchanged: 169
commands passed against its retained executable, but its fresh-build and shared-tree
immutability gates were UNVERIFIED then. The fresh-build pass and current-release
replay above close those gaps; they do not retroactively change that first report.

Concurrent platform edits temporarily caused a dependency-resolution conflict, an
extra `>` in `src/platform.rs`, and a missing `path_text` import in `src/config.rs`.
The latter compiler errors were corrected, a needless borrow was removed, and Rust
formatting was applied. The parallel task owner completed the dependency/platform
changes and corrected its blocking-stdout fixture to actually exceed pipe capacity.
The final aggregate check includes that test. Failed logs are retained as
`check.log`, `check-complete.log`, `current-build-recheck.log`,
`current-check-final.log` and related focused rechecks. The mistakenly combined mise
invocation is retained in `acceptance.log`. None is counted as the F1 regression RED.

Implementation deviations: none adopted for F1. Specification gaps: none found for
F1. Missing evidence: none for this defect's search/read contract on the measured
Linux target. Native platform artifact acceptance remains the separate release task
identified by the original audit; this correction does not claim a new
`mise run release` result.
