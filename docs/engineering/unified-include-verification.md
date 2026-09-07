# Unified include and authored Markdown acceptance

This historical acceptance snapshot covers the 2026-09-08 implementation of the unified include and structural selector plan, including the authored Markdown milestone. Its interface examples and measurements describe that tested baseline. Current product behavior belongs to the [standard directives](../specs/standard-directives.md), [entity mappings](../specs/entities.md), [directive syntax](../specs/directives.md), [rendering](../specs/rendering.md), [CLI](../specs/cli.md), [model](../specs/model.md) and [plugin protocol](../specs/plugins.md) specifications. Search and snapshot handles remain outside this scope.

The current include parameter surface is checked in [include selection acceptance](include-selection-verification.md).

## Implementation and migration

`include` owns material loading, selection and presentation. `selection` interprets names and indices without language keywords; language adapters provide actual declaration names, ranges and child inventories. A node's own extractability is separate from the completeness of its children. These facts prevent unsupported declarations from disappearing out of same-name indices and prevent incomplete inventories from producing a false unique match.

The old built-in `code` handler and registration were removed. Code presentation, line ranges and language labels now belong to `include`; structural `id` and explicit Markdown `anchor` have independent namespaces. Former `section` arguments were migrated to the appropriate selection form. A project can still register its own `code` directive, while declaring it as a built-in override fails. Unrecognized extensions and extensionless text retain Markdown interpretation; `format="markdown"` explicitly selects that interpretation for recognized code extensions. Configuration and protocol versions remain 1.

`DocumentKind` distinguishes Markdown from language sources. Authored pages keep their raw prose and headings while using the existing directive, batch, provenance and publication contracts. [The guide](../guide/index.md) is a four-page work arranged around reading source, expanding directives and building pages. Review, acceptance and archive rendering include these inputs.

The change preserves original byte slicing, CRLF and missing-final-newline handling, adaptive fences, single expansion, complete plugin input inventories, independent material dependencies and output protection. Selection errors never fall back to a different search or presentation mode. Existing process lifecycle and publication owners retain their responsibilities.

## Structural selection acceptance

An independent validator received the original plan and its nine acceptance rows, without implementation summaries or completion claims. All nine rows passed.

| Criterion | Status | Evidence |
| --- | --- | --- |
| True JSON arrays, string/array path equivalence and exact name/index domains | PASS | `tests/directives.rs`, `tests/materials.rs`, `tests/standard_directives.rs`: nested arrays and objects cross a real plugin process; Unicode, punctuation, empty names, decimal indices and invalid data retain distinct meanings |
| Actual Markdown hierarchy, same-name siblings and empty headings | PASS | `tests/standard_directives.rs`: direct-parent selection, skipped heading levels, setext headings, duplicate owners and explicit empty heading names |
| Missing, ambiguous, invalid, out-of-bounds and unsupported selections | PASS | `tests/standard_directives.rs`: unsupported same-name candidates retain indices; incomplete inventories cannot claim a unique result; parent ambiguity is resolved before descent |
| Source edits use current-order indices without claiming permanent identity | PASS | Independent real-CLI mutation probe: different-name insertion retained the target, same-name insertion changed index 0, and a unique name becoming duplicated failed with `selection_ambiguous`; `tools/acceptance.py` also mutates Rust declarations |
| Six language mappings and complete original declaration ranges | PASS | `tests/standard_directives.rs`: Rust impls/docs/attributes, OCaml groups/shadowing/interfaces, JavaScript members, TypeScript overloads/namespaces, Go receivers/init and Python nested/decorated definitions; exact text and source slices |
| Literal contexts, dynamic structures and syntax failures | PASS | `tests/directives.rs`, `tests/standard_directives.rs`: literal examples remain literal, all six malformed language fixtures fail, unsupported inventories fail explicitly and `as="code"` cannot bypass structural errors |
| Raw payload, byte/line spans, presentation and single expansion | PASS | `tests/standard_directives.rs`, `tests/materials.rs`: exact CRLF and fence payloads, unchanged source spans across presentation, precise call sites and returned directive text remaining literal |
| Registration, complete batches, dependencies and failure publication | PASS | `tests/materials.rs`, `tests/external.rs`, `tests/session.rs`, `tests/publication.rs`, `tests/pages.rs`: real processes, zero requests, custom `code`, missing materials, protected paths and checked/execution failure outcomes |
| Line ranges, language labels, anchors and all-extension Markdown migration | PASS | `tests/standard_directives.rs`, `tests/materials.rs`: independent anchor selection, selector conflicts, README and notes.txt, explicit Markdown interpretation of code extensions, migrated and rejected old interfaces |

The validator's focused run passed 72 tests across these seven suites. It independently ran the release build and self-use acceptance. Its mutation probe reported: `PASS: different-name insertion retained target; same-name insertion moved index 0; unique-to-duplicate failed selection_ambiguous`.

## Authored Markdown acceptance

A separate independent validator checked the authored Markdown requirements. Its focused `materials` and `self_use` suites passed. A disposable complete-project render produced 68 pages, and its independent navigation/provenance probe reported `NAVIGATION PASS` and `PROVENANCE PASS`.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Explicit Markdown document kind and normal input selection | PASS | `src/model.rs`, `tests/materials.rs`: real `.md` inputs, directory discovery, exclusions and mixed code/Markdown batches |
| Full Markdown context and author-controlled prose | PASS | `tests/materials.rs`: handwritten expected page, Unicode, CRLF, no final newline, literal fences/lists/quotes/HTML and accurate directive bytes |
| Common plugin, provenance, appendix and report contracts | PASS | `tests/materials.rs`, `tests/pages.rs`: complete input inventory, zero-request plugin, real response data, source metadata and single expansion; the final supplemental test directly appends to an authored page under both output roots |
| Distinct output identities and empty pages | PASS | `tests/materials.rs`: `.rs`, `.md` and `.rs.md` inputs produce distinct pages; empty Markdown has an empty body |
| Multi-page authored work in reading order | PASS | `docs/guide/`: index plus three chapters explain source reading, directive expansion and page construction using actual declarations |
| Current-output navigation under default and nested output roots | PASS | `tools/acceptance.py` plus the independent disposable render: chapter links and explicit anchors resolve within the newly generated page set |
| Repeated excerpts and changing referenced source | PASS | `tools/acceptance.py`: repeated `parse` excerpts share content/source with distinct call sites; insertions, duplicate declarations, explicit index selection and reordering update or fail as specified |
| Complete self-use and required static checks | PASS | `mise run review`, `mise run acceptance`, `mise run check`; all enabled project plugins participate in the complete input batch |

Before and after both validators ran, SHA-256 snapshots of all 116 repository files matched. Validators edited no repository files. This is independence through separate prompts and verified snapshots, not a separate filesystem sandbox. The later appendix assertion, diagnostic wording correction and this record were checked by the main task's final gates.

## Development and final gates

Behavior was developed through public boundaries: general array parsing first failed against the scalar-only parser; Markdown paths, unified presentation and each language mapping received failing selection tests before their implementation; authored Markdown first failed at input selection; the authored guide was then included in complete self-use. The expected small narrative page is handwritten in `tests/fixtures/narrative.expected`, with explicit framing assertions in `tests/materials.rs`.

A review question about `["f",1]` exposed an unnecessarily narrow capability choice: a simple JavaScript variable binding already has a static name and contiguous declaration range. The owning clause now permits extracting simple JavaScript/TypeScript `const`, `let` and `var` declarations. A public include test first returned `unsupported_selection` for `const f = () => 1;`, then passed after the adapter selected the complete declaration rather than rejecting the binding. Further tests verify grouped bindings, duplicate names, CRLF ranges, optional semicolons and `export`/`declare` prefixes. A class-field regression also exposed a grammar fact mismatch: JavaScript fields expose their name through `property`, while TypeScript uses `name`. The adapter now reads both grammar-defined fields, retaining unsupported class fields at their correct same-name positions.

A fresh validator checked the revised binding requirements separately. It ran `cargo test --locked --test standard_directives` (21 passed), formatting, strict all-target Clippy and a binary build. Its independent real-CLI fixtures established the following results. Before/after SHA-256 snapshots of all 117 repository files matched.

| Revised criterion | Status | Independent evidence |
| --- | --- | --- |
| JavaScript simple bindings, including `["f",1]` | PASS | The generated page returned the full `const f = () => 1;`; separate let/var cases also succeeded |
| Complete groups, prefixes and exact spans across JS/TS/TSX | PASS | Both names selected the same full export declaration; TSX declare/export, optional semicolons and source byte ranges matched the original files |
| Same-name ordering and unsupported candidates | PASS | Repeated var bindings retained indices 0 and 1; the field between two methods returned `unsupported_selection: field_definition "same" at byte 20 cannot be extracted` for index 1 |
| Existing container and unsupported boundaries | PASS | Object methods were selectable; dynamic/destructured inventories failed explicitly; a named function expression returned `selection_not_found: no direct child named "inner"` |

Verdict: PASS for the original acceptance ledgers and the revised binding requirements.

| Command or gate | Result |
| --- | --- |
| `mise run check` | PASS: formatting, strict all-target Clippy, documentation/AGD checks, all Rust/Python tests and the three coverage gates |
| Rust core coverage | 3858/4062 lines, 94.98% |
| Rust spec plugin coverage | 274/285 lines, 96.14% |
| Python project plugin coverage | 103/107 lines, 96.26% |
| `mise run review` | PASS: release build, 68 pages and one spec coverage report with no unreferenced clauses |
| `mise run acceptance` | PASS: 663,828 Markdown bytes across 69 pages/reports; six languages, two custom names, unified include, authored guide navigation and source edits, four fault mutations, material/argument refresh |
| `git diff --check` | PASS |

Coverage reports are under `.source-down/coverage/`. The selection validator could not independently complete the aggregate `check`: index regeneration was blocked by the protected `.agents` directory, and its disposable compilation exhausted temporary storage. Its focused suites, build and acceptance passed. The main task's complete check passed in the repository; the separate Markdown validator also passed documentation checking in a disposable copy. These environment failures are not counted as successful validator check runs.

Implementation deviations: none identified in the implemented scope.

Specification gaps: none identified for the adopted interfaces. Macro expansion, runtime bindings, import/inheritance resolution and virtual declaration merging remain outside the language support contracts.

Missing evidence: none identified for the acceptance rows above. No new performance or cross-platform claim is made; successful generation and coverage percentages alone do not establish semantic conformance.
