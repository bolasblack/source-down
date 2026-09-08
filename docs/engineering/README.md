# Engineering handoff

This document explains how to implement and verify the specifications. Product requirements are defined by the owners listed in the [specification index](../specs/README.md).
The project has a buildable Rust CLI, built-in plugins, an external plugin protocol, and tests at real boundaries. [.mise.toml](../../.mise.toml) defines the acceptance tasks; measured results are recorded in [release acceptance](verification.md), [persistent plugin acceptance](persistent-plugins-verification.md), [unified include and authored Markdown acceptance](unified-include-verification.md), and [plugin content composition acceptance](plugin-composition-verification.md).

The current include parameter surface is checked in [include selection acceptance](include-selection-verification.md).
Search contracts, real boundary evidence, predeclared queries and measurement budgets are tracked in [search acceptance](search-verification.md).
The current default snapshot publication, short handles and direct file reads are checked in [CLI and file-read acceptance](search-cli-verification.md).

## Technology and module boundaries

The project uses Rust, Cargo, Tree-sitter, pulldown-cmark, and clap as specified in [AGD-002](../../.agents/decisions/AGD-002_choose-rust-and-source-range-parsing.md).
It remains a single Cargo package: `lang` registers language adapters; `source` owns generic source segmentation; `directives/syntax` owns tag recognition; `render` owns Markdown composition; `model` owns source references and values; `config` owns configuration and selection; `results` owns generic response validation; `external` exposes serial initialization/run/close operations; `external/driver` owns each session protocol phase, deadline and bounded stderr tail through the process scope supplied by `platform`; `external/protocol` owns closed NDJSON messages and framing; `publication` owns output preflight, preparation, replacement and pruning; and `engine::Session` retains configuration and registration while preparing fresh source and output facts for each round. `PreparedRun` borrows its session until published or discarded. `directives/include` owns unified material selection and presentation through one shared content operation and its public `Plugin` adapter. `selection` normalizes structural paths and selects direct children; `lang` adapters provide declaration facts and `lang/syntax` assembles their scopes. `DocumentKind` distinguishes authored Markdown from language sources. `markdown` owns generic CommonMark section ranges shared by `include` and the project spec plugin. The project's external plugin entry points are `tools/project_docs.py` and `tools/spec_plugin.rs`.

[AGD-011](../../.agents/decisions/AGD-011_share-standard-content-operations-for-plugin-composition.md) records the shared operation and terminal content rationale. `results` first validates the complete description, then evaluates content in request/node order, appendix order and report-name order. `directives::StandardOperations` owns each round's standard operation instances; include keeps one structural tree per canonical file and shares the round's SourceStore. Markdown and language parsers supply nodes to the same selection algorithm. The ordinary Plugin adapter calls the same operation through the same catalog, while project overrides affect only author routing. Evaluated content is a sequence of MarkdownFragment blocks with individual origins. The renderer emits the parent's metadata once and frames each block; returned text never enters directive extraction.

Source parsing is used only to obtain reliable original ranges. The final code payload is sliced from the original input bytes.
`search` collects validated content before renderer framing and prepares a complete snapshot for every successful round. `search/handles` owns public handle derivation and current-snapshot collision checks; cursors retain complete identities. `search/file` exposes current-file reading independently of the snapshot Reader. Include's per-round Material cache and file reads both use `selection::Material`, which retains original file bytes, classification and the parsed tree; each consumer owns presentation. Publication remains the only artifact writer. `search/output` formats both result models and performs the final flush through the cancellable writer supplied by `platform`.
`platform` is the sole owner of operating-system selection, native file identity, explicit file close, path encoding, interrupt registration, process scopes and cancellable I/O. Native test fixtures also use it for file/directory symlinks, process-state observation and process-tree termination; `tests/common` owns fixture programs, waiting deadlines and assertions. Platform observations return I/O errors and preserve observable zombie state so tests can distinguish stopping from direct-child reaping. Callers use one interface and retain all protocol and product policy. Unix uses nonblocking descriptors and process groups; Windows uses bounded pipe workers and a Job Object assigned before the plugin starts executing. Dropping a scope remains the setup-failure fallback; explicit cleanup propagates errors. [AGD-012](../../.agents/decisions/AGD-012_release-native-platform-artifacts.md) records this boundary and the native release matrix.

Keep comment location by language grammars separate from project directive extensions: new languages require validation of their lexical adapters, while project directives use the public process protocol.
Acceptance is based on code order and source ranges in the reading document, together with error propagation.

## Persistent sessions

[AGD-009](../../.agents/decisions/AGD-009_own-persistent-plugin-processes-in-one-session-driver.md) records the driver ownership choice. The product lifecycle is defined by [SPEC-PLG-003](../specs/plugins.md#spec-plg-003) and [SPEC-PLG-008](../specs/plugins.md#spec-plg-008).
A library caller can keep a session and process complete rounds:

```rust
let mut session = source_down::engine::Session::new(
    root, None, None, std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)),
)?;
let first = session.prepare(&["src".into()])?.publish()?;
let second = session.prepare(&["src".into()])?.publish()?;
session.close()?;
```

Each `RunOutcome` includes its batch identity, plugin-owned dependencies, check status, diagnostics and page/report paths. A valid check failure is an outcome with `check_failed = true`; execution faults return an error and terminate the session. Dropping a prepared result discards it and permits the next round. The render CLI calls `PreparedRun::close_session` before publication, preserving its close-before-publication boundary. File dependencies are validated independently of source text and protect both their query paths and resolved identities from replacement or pruning.

The library interface supplies complete-round execution and dependency facts. Watch scheduling, configuration reload and source-page deletion policies require their own specifications before implementation.

## Adding a language

First define the extensions, code labels, and lexical behavior in [SPEC-REN-001](../specs/rendering.md#spec-ren-001), then write a failing test through the existing `source::parse` API and the real CLI.
Implement `Language` in `src/lang/<language>.rs`: declare its name, extensions, and labels, and return comment tokens whose boundaries have been checked.
Add the adapter to the module declarations and `LANGUAGES` list in [lang/mod.rs](../../src/lang/mod.rs).
File scanning, CLI help, and include source labels read the registrations automatically. Add grammar dependencies to Cargo at pinned versions after dependency screening.

Each adapter retains its language-specific lexical decisions. The shared `lang/syntax.rs` owns Tree-sitter calls and generic syntax checks.
`source` validates original token ranges and markers, then extracts prose using the common standalone physical line rules and copies the maximal contiguous source ranges outside those comments.
Registered adapters run in process; implementation changes are delivered by rebuilding. See [AGD-006](../../.agents/decisions/AGD-006_register-language-adapters-and-group-directives.md) for the organization decision.

## Acceptance boundaries

| Slice | Input and public boundary | Completion evidence |
| --- | --- | --- |
| 1. Single-file Rust conversion | A real `.rs` file through the render CLI | Passing byte assertions for complete source range coverage, comment cleanup, code payload, source references, and fences |
| 2. OCaml conversion | `.ml` and `.mli` files | Passing fixtures for nested comments, quoted strings, doc comments, and lexical errors |
| Additional languages | Public parsing APIs and the real CLI for JavaScript, TypeScript, Go, and Python | Passing checks for literals, syntax diagnostics, selection by every extension, source references, and original text preservation |
| 3. Multiple files and publication | Directories, duplicate paths, source pages, and plugin reports | Verified ordering, exclusions, and relative links; passing file tests that preserve existing output on failure |
| 4. Plugin host | A real external program implementing the wire protocol | Passing tests for batch counts, reordered responses, missing or duplicate IDs, pipe capacity, nonzero exits, timeouts, and cancellation |
| 5. Self-use and extensions | The tool's own Rust source, Python tools, examples in six languages, and project plugins | Passing acceptance checks for real document generation, structured arguments, fault injection, and updated inputs taking effect |
| 6. Release verification | A release build and a clean target environment | Passing smoke tests for startup, conversion, and plugin integration on declared platforms |

Start each behavior slice with one failing test of publicly observable behavior. After the smallest implementation passes, refine the structure during subsequent review.
Tests cite their source clauses by ID. Golden files are useful for formatting checks; assert source ranges and code bytes directly as well, so snapshot updates cannot hide lost content.
Include separate boundary cases for empty input, Chinese text and special paths, CRLF, missing final newlines, raw strings, nested comments, Markdown fences, and plugin failures.

`mise run test` enforces the 90% line coverage gates in [AGD-008](../../.agents/decisions/AGD-008_enforce-ninety-percent-test-coverage.md).
`lint` runs formatting, Clippy, documentation links and AGD checks, including the prohibition on SPEC clause IDs in decision records. `check` depends on both `lint` and `test`, following [AGD-010](../../.agents/decisions/AGD-010_keep-decisions-self-contained-and-separate-lint.md).
See the [coverage guide](coverage.md) for production scope, child process sampling, reports, and failure conditions.

## Bootstrapping self-use

Build the main program and the project spec plugin with `mise run build`, then process source code; generated reading documents are artifacts produced after the build.
When a project's own documentation needs extra content, implement the corresponding plugin through the public protocol and prepare its build or runtime environment.
For example, a consuming project can register two of its own names as follows:

```toml
config_version = 1

[plugins.project]
command = ["python3", "tools/project_docs.py"]
directives = ["docs.snippet", "metrics.table"]

[plugins.project.options]
label = "Example project"
```

The example shows how to register arbitrary project names. This project's actual configuration registers `package`, `modules`, `api`, and `spec`; see [tools/README.md](../../tools/README.md) for their behavior and [.mise.toml](../../.mise.toml) for build and acceptance tasks.
See the [syntax specification](../specs/directives.md) for directive notation and parsing precedence, and
[AGD-004](../../.agents/decisions/AGD-004_use-explicit-directives-and-json-arguments.md) for the design rationale.
Review output can go in `.source-down/`, which is excluded from inputs by default.
Use `mise run review` to process `src tools tests examples docs/guide` in one invocation, producing separate pages and a spec coverage report. Record acceptance results as required by [AGD-003](../../.agents/decisions/AGD-003_use-source-down-for-its-own-review.md) and [AGD-007](../../.agents/decisions/AGD-007_check-spec-references-through-a-project-plugin.md).

## Performance verification

Measure real workloads before deciding whether to add execution mechanisms. Record tool and grammar versions, build mode, machine details,
source file and byte counts, plugin input material bytes, directive counts and argument distributions, plugin launch counts, output bytes,
total time, and peak memory. Distinguish first launches from repeated runs and retain the raw measurement output.

Compare three groups: no directives, 500 locations requesting the same result, and 500 locations requesting different results.
Cover both single-file and multiple-file inputs in each group. The count of 500 defines the reproducible experiment's workload, not a product limit.
Verify plugins by their initialization and batch counts and protocol results; each plugin owns its per-round indexing strategy. `mise run benchmark` retains these six workloads and measures both three CLI invocations and three rounds in a single Session for each. The session measurement records first/subsequent round times, total time, peak RSS, maximum physical frame size and actual initialization counts.
Set time and memory budgets after measuring a baseline on the target machine and before making performance changes.

## Documentation maintenance

Keep a single owning clause for each requirement in the specifications; references to the same ID are not duplicate definitions. After edits, check headings, explicit anchors,
relative links, and agreement between plugin JSON examples and field tables. AGDs preserve self-contained decisions; keep links to current product clauses and implementation files here in engineering documentation. Generate AGD indexes with the bundled framework scripts, setting
`CLAUDE_PROJECT_DIR` to the new repository root when running them.

The [authored guide](../guide/index.md) is included in the complete review task. Its links target generated chapter filenames and explicit display anchors. `tools/acceptance.py` verifies these targets against the current output set under both default and custom output roots, checks repeated source provenance, and mutates referenced declarations in a temporary checkout.
