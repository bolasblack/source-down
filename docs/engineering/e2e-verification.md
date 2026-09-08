# Readable E2E delivery evidence

The agreed design is `/tmp/source-down-e2e-design-2026-09-08.md`. Implementation
started from the dirty workspace recorded in
`/tmp/source-down-e2e-implementation/baseline-status.txt`; no Git mutation is part
of this delivery. The original acceptance/collision scripts and self-use bridge
are preserved with their source hashes under that directory's `baseline/` and
`baseline-manifest.json`. Product specifications and ranking rules were reused.

## Contract and RED/GREEN evidence

The [engineering contract](e2e.md) preceded coordinator changes. The first two
scenarios ran directly through standard unittest and the real CLI before helper
extraction. Runner checks then exercised its public command and saved run files.
All logs below are in `/tmp/source-down-e2e-implementation/`.

| Contract exercised | RED evidence | GREEN evidence |
| --- | --- | --- |
| Listing through the actual coordinator | `runner-list-red.log`: unsupported `--list`, exit 2 | `runner-list-green.log` |
| Actual outcomes and independent continuation | `runner-result-red.log` | `runner-result-green.log` |
| Exact filter and partial scope | `runner-filter-red.log` | `runner-filter-green.log` |
| Skip, failed subtest and explicit platform applicability | `runner-events-red.log`, `runner-platform-red.log` | `runner-events-green.log`, `runner-platform-green-final.log` |
| Empty/import/duplicate/incomplete discovery | `runner-discovery-contract-red.log` | `runner-discovery-green.log` |
| Actual supplied artifact, raw command streams | `runner-commands-red.log` | `runner-commands-green.log` |
| Same source/fixture copy drives execution and reading | `runner-reading-red.log` | `runner-reading-green.log` |
| SIGINT persistence, descendant cleanup, fixture setup/xfail events, missing artifact and changed preserved source | `runner-lifecycle-red.log`: five failing outer-entry tests | `runner-lifecycle-green.log`: all 15 outer-entry tests pass |

A controlled wrong fixture and wrong expected exit code each fail the real E2E,
its JSON and generated index; restoration passes in a distinct run. A real
unregistered directive makes reading generation fail while preserving passing
test results, raw JSON/logs and the previous run's unchanged page. Both experiments
are executable outer-entry tests in `tests/e2e_tools_test.py`;
`runner-reading-mutations.log` records their initial passing verification.
Import/setup failures are runner error evidence, not missing product-behavior RED.

## Migration and observed acceptance

The [migration ledger](e2e-migration.md) accounts for all 17 original acceptance
assertion groups and all 100 tests in the nine candidate Rust files. Existing
native tests remain intact. The old acceptance business functions and collision
entry point were removed after equivalent named cases passed; the Cargo bridge
now checks coordinator status without interpreting PASS text.

The complete acceptance run `20260908T191119-3de4f8b9b7f1` passed all 22 scenarios
and generated 23 current reading pages (one index plus the scenario pages).
Its `results.json` and reading entry are under
`.source-down/e2e/runs/20260908T191119-3de4f8b9b7f1/`.
`acceptance-final-after-lifecycle.log` records the `mise run acceptance` command. Results retain
workspace HEAD/dirty evidence, exact binary/plugin SHA-256, saved source/fixture
hashes, per-command argv/cwd/raw streams and the separate documentation status.

Both collision cases build a controlled replacement in a private source/target
directory; both share that one mutant only within their run. The report records
replacement bytes, original/mutated source hashes, mutant executable SHA-256 and
which program ran every command. They verify render, snapshot search and snapshot
read refusals, exact colliding identities, every unchanged output file and unchanged
production source. They are mutation evidence, not execution of an unmodified
release for those three refusal operations.

The original predeclared query file remains byte-identical. The approved code_span
criterion still uses top_k=1 and only its first hit, exact source span and complete
function bytes. Removing kind filtering changed the candidate set; the original
query declaration is retained and ranking was not modified.

## Task gates and limits

`mise run test` passed: 187 Rust tests (including one E2E bridge) and 41 Python
plugin/tool tests. The bridge ran 22 E2E identities once; the developer-tool pattern
`*_test.py` does not rediscover their `test_*.py` names. It uses the built instrumented
CLI and preserves the actual LLVM/Python profile environment. `test-final-after-lifecycle.log`
records the command and `.source-down/coverage/summary.json` owns these counts:

| Production scope | Covered / executable lines | Percentage |
| --- | --- | --- |
| Rust core | 6093 / 6380 | 95.50% |
| Rust spec plugin | 297 / 308 | 96.43% |
| Python project plugin | 110 / 114 | 96.49% |

These are independent line-coverage gates, distinct from spec-plugin reference
coverage. Native Session, raw-byte, syscall, blocked-I/O and plugin-process tests
remain part of this task; the reading set alone does not prove every product clause.

`lint-final-after-lifecycle.log` records successful formatting, strict Clippy and
documentation/AGD validation. `review-final-after-lifecycle.log` records 122 published
current-input pages with all 69 normative clauses referenced. `release-final.log`
records the extracted CLI, native portability suite and offline relocated source
rebuild. Both release E2E runs passed all 22 scenarios; the retained relocated run
keeps its actual workspace/program identities even after the checkout is removed.
`release-final-after-lifecycle.log` records the final repeat after the retention fix.
Current execution is Linux x86_64 GNU. Windows and macOS execution is not established by
this host run. Windows subprocess ownership uses the documented
[Job Object lifecycle](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
with a blocked bootstrap assigned before it can create children; native execution
of that path remains unverified on this host.


## Final failure-path and independent checks

A real SIGINT during the next class's setup exposed an acquired PASS being changed
to error. `interrupted-setup-test-red.log` preserves that failure. The result owner
now clears its current test at stop, and records an active interruption's traceback
before clearing it. `runner-final-green.log` records all 16 runner tests passing.
Independent probes additionally observed setup exit 130 with `[passed, not_run]`,
and active interruption exit 130 with `[passed, error, not_run]`, saved logs, and
an absent descendant process.

A failing real relocated coordinator initially lost its evidence when its temporary
source checkout closed. `release-retention-valid-red.log` verifies the coordinator
had actually failed and written its original JSON before the missing retained-file
assertion. Evidence copying now runs in `finally`; both release tool tests pass in
`release-retention-final-green.log`. An independent extracted-artifact probe checked
the CLI SHA, plugin identity, failure traceback and surviving saved files after
checkout removal. `release-concurrent-red.log` exposed the regression test counting
other runs; it now identifies its saved report using the original run ID. The
paired rerun is recorded in `release-concurrent-green.log`.

Independent review of the runner, migration, source/fixture provenance, reading,
process cleanup and shared entry wiring returned PASS. Its own partial run
`20260908T185915-99619ccaa6ee` kept 21 unexecuted cases and `full_pass=false`; it also
verified the exact 22-case AST inventory and all 100 native ledger names without
missing or extra rows. A fresh two-criterion pass confirmed interruption and failed
relocation retention with real public commands. Validator tree comparisons found
zero authored-file changes (`validator-tree-check.json` and
`validator-followup-tree-check.json` in the evidence directory).

No implementation deviation or product-spec gap remains from this slice. Explicit
evidence limits are the retained/pending native migrations in the ledger and
unexecuted non-Linux platforms; the Python reading set is not a claim of complete
repository conformance. Production source and normative spec hashes match the task
baseline. Original search queries and ranking bytes are unchanged.

## Top-level E2E layout follow-up

The approved follow-up moves the readable suite to `tests-e2e/`, with `cases/`,
`fixtures/`, `support/` and `bridge.rs` directly below it. Standard unittest uses
that directory as its discovery root. Native and developer-tool tests remain in
`tests/`. Cargo, acceptance, review, benchmark, coverage filtering, source packaging
and current documentation use the new paths.

The original 42-file inventory maps to 41 relocated files; only the obsolete root
package marker was removed. An independent comparison found relocation-required
edits and no removed test assertions. Its public listing, Cargo bridge, complete
acceptance, 16 runner regression tests, formatting and strict Clippy checks passed.
The validator left all 196 authored files and Git state unchanged.

Run `20260908T194436-f6310a06c965` passed all 22 scenarios and produced 23 reading
pages under `.source-down/e2e/runs/20260908T194436-f6310a06c965/`. Every retained
source hash matched the current relocated source. The complete project review
produced 121 pages; generation and search/read benchmark budgets passed.

Follow-up logs and the before/after inventory are retained in
`/tmp/source-down-commit-curation-20260908/`. `test-layout-final.log` and
`release-layout-final.log` record the complete follow-up test and release commands.
Earlier run records above preserve their original paths, counts and execution
evidence.
