# Declarative E2E helper verification

This behavior-preserving migration implements Proposal 001 from the working plan.
The owning tool contract is [Readable end-to-end acceptance](e2e.md); product
specifications remain unchanged. No commit or push is part of this task.

## Baseline and scope

The starting HEAD is `5ba6303feb6f53d3a09d0dd4b83dd238b2be8dc4`.
All 22 planned cases passed in `20260909T214650-f7dcf1cd8125`. That 68-case
baseline had two sandbox `setgroups` failures, both rechecked successfully with
native permissions in `20260909T214831-1d1ecc43b0bb` and
`20260909T215217-8968ff0fd60e`.

The original scenario sources, IDs, titles, owning clauses, subtests and actual
commands are preserved in `/tmp/source-down-e2e-api-5ba6303/baseline.json` and its
sibling source copy. The planned 22 cases keep their discovery identity. The later
46 cases remain; two watch callers follow the shared self-use method rename.

## Tool contract evidence

The original external coordinator mutation check passed before replacement: wrong
expected output and wrong exit status fail, restored expectations pass, and each
run renders its own results. The new render-observation test failed before the
facade existed, then passed with real command execution, frozen output and input
restoration after assertions and interruption. A second RED identified that pathlib
iteration hid an output-capture error; explicit directory enumeration now preserves
that error and checks command status before accessing artifacts.

`tests/e2e_helpers_test.py` exercises the saved-copy coordinator with bounded
artifact and wire mutations. It checks complete output, selected files/trees,
Markdown reports and ordering, cross-root comparisons, absent artifacts, duplicate
anchors, source sets and repetition, full versus partial bodies, invalid cursor and
range, final markers, character budgets, full collision IDs and order, independent
JSON views, and input restoration. Controlled Python wire programs test the harness;
product acceptance separately uses the real supplied Source Down binary and plugin.

The continuation driver follows returned offsets with no page-count limit. Its
monotonic total deadline bounds each command; tests retain timeout logs and verify
process-scope cleanup, an explicit longer budget, and single reads that ignore the
multi-page budget.

## Completion evidence

| Gate | Result |
| --- | --- |
| Complete acceptance with reading | `20260909T221926-19545b8a506d`: all 68 cases passed, 69 reading pages |
| External runner and helper tests | 26 tests passed; bounded negative cases retain failures/errors in their own reports |
| `mise run lint` | Formatting, Clippy and documentation/AGD checks passed |
| `mise run test` | All Rust/Python tests and the E2E bridge passed |
| Coverage gates | Rust core 94.56%, Rust spec plugin 96.43%, Python project plugin 94.17% |
| `mise run review` | 193 project pages generated |
| `mise run release` | Linux x86-64 GNU extracted binary and relocated source rebuild passed |
| Relocated source E2E | `20260909T221913-6d689636fbd2`: all 68 cases passed; run retained after source cleanup |

The 22 original IDs, titles, owning clauses, all 92 commands and 33 subtests match
the original run. The comparison normalizes only disposable project/mutant paths,
executable locations and the actual returned short handles. It does not reorder
commands or ignore flags, statuses or matrix entries. The comparison and raw logs
are retained under `/tmp/source-down-e2e-api-5ba6303/`.

A private-copy ablation removes the remaining-budget bound from the continuation
command. The over-budget operation then succeeds, and the unchanged external test
rejects the result. Restoring the implementation passes. This independently proves
the new total-timeout check instead of treating the original unbounded loop as
existing evidence.

Four repeated fixture includes were deduplicated after reviewing the reading pages.
Their executable ASTs are identical; the final complete acceptance run uses the
updated source. The release run preserves its own earlier reading-comment copy.
All three guide-reading scenarios include exactly the shared expectation source
saved and executed by that run. No product implementation or specification changed.
No remote CI was triggered; this delivery's runtime evidence is from Linux.

## Review boundaries

Guide expectations retain the independently declared literal destinations required
by the current link-based guide. The helper supports these mappings and ordinary
authored links without implementing the product directive evaluator. It preserves
the existing source-excerpt matcher and call-site evidence boundary. JSON remains
unfiltered; omitted expectations do not imply a full response validator.

## Owner and failure review

RunContext and ProcessScope remain the only command/log and cleanup owners. The
SourceDown facade encodes options and freezes facts; it never picks a successful
result. OutputSnapshot owns one immutable capture, including I/O failure. Reading
assertions use real sources; independently authored SourceRegion values own file
expectations. The pure page inspection owns progress decisions for both driving and
assertions. The artifact and body negative cases establish the scope of each check.

The observation copies prevent subsequent edits from rewriting baseline evidence.
Explicit preservation scopes catch missing, extra and changed outputs; they also
allow reports to change when the scenario permits it. Current links and historical
text remain separate requirements. The original source-excerpt recognition and
call-site predicates are retained, with their documented evidence limits. No new
parser, subprocess runner, discovery layer, report framework or dependency is added.
Implementation deviations and unresolved specification gaps: none. Runtime checks
on macOS and Windows were not executed in this Linux session.
