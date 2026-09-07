# 0.1.0 initial release acceptance

This historical record covers the local release acceptance run on Linux x86_64 GNU on 2026-09-07 and subsequent source metadata validation, before the persistent plugin implementation.
The counts, protocol version and measurements below belong to that earlier snapshot. Current persistent-session evidence is recorded in [persistent plugin acceptance](persistent-plugins-verification.md).
Product clauses are listed in the
[specification index](../specs/README.md); release gates are defined in [AGD-005](../../.agents/decisions/AGD-005_use-mise-and-ship-six-input-languages.md) and extended by [AGD-007](../../.agents/decisions/AGD-007_check-spec-references-through-a-project-plugin.md) and [AGD-008](../../.agents/decisions/AGD-008_enforce-ninety-percent-test-coverage.md).

## Environment and versions

- Host: Linux 7.0.2-6-pve, x86_64, glibc 2.41.
- mise: 2026.6.2; `.mise.toml` pins Rust, Python, and Zig, and all tasks run through `mise run`.
- Rust: 1.90.0, including rustfmt, Clippy, and matching LLVM tools; Cargo.lock pins direct and transitive dependencies.
- Python: 3.14.7; runtime project scripts use the standard library.
- Coverage: cargo-llvm-cov 0.6.21 and coverage.py 7.11.0, pinned through mise; Python measurement uses an isolated development environment.
- Zig: 0.15.2; provides C compilation, archiving, and linking for Linux x86_64 GNU.
- Tree-sitter: 0.25.10; Rust grammar 0.24.0; OCaml, JavaScript, Go, and Python grammars 0.25.0; TypeScript/TSX grammar 0.23.2.
- CommonMark parser: pulldown-cmark 0.13.0.
- TOML: toml 0.9.8, with toml_parser pinned to 1.0.5+spec-1.0.0; explicit regression tests verify rejection of TOML 1.1 extensions.
- serde_json 1.0.145 with float_roundtrip enabled; fixed bit-pattern regressions verify exact decimal-to-binary64 rounding.

The release binary was run on this host. `readelf --version-info` reported a maximum required GLIBC symbol version of
GLIBC_2.29, with dynamic dependencies including libc, libpthread, and libdl. The execution evidence here applies to the host described above;
support records can be extended to other platforms after their artifacts pass the acceptance gates in AGD-005.

## Completed verification

| Boundary | Evidence |
| --- | --- |
| Test suite | 85 Rust tests and 11 Python tests passed through public APIs and real process/file boundaries |
| Execution coverage | Rust core 2822/2967 lines (95.11%), Rust spec plugin 254/267 (95.13%), Python project plugin 65/65 (100%); each scope passes its independent 90% gate |
| Static checks | `cargo fmt --all -- --check`; `cargo clippy --locked --all-targets -- -D warnings` |
| Rust / OCaml source preservation | Complete range coverage, contiguous code/comment segmentation, strings and nested comments, Unicode delimiters, shebangs, CRLF/lone CR, and missing final newlines |
| JS / TS / Go / Python | Consistent direct input and directory scanning for 14 extensions; templates, regular expressions, JSX, raw strings/rune literals, docstrings, comments in expressions, special line separators, and failure protection |
| Module extension | Each of six languages implements `Language`; one registration list connects source parsing, file selection, code labels, and CLI help; directive implementations live in `src/directives/` |
| Markdown | Adaptive fences, explicit fence/HTML endings, encoded source links with literal code labels, separate metadata paragraphs for expansions/appendices/reports, exact included bytes, prose and exact tag positions, and parsed CommonMark structure |
| Tags | Positional/named template arguments, escapes, numeric domains, literal text in containers, error locations, and zero output after errors |
| Plugin routing | Built-in owners by default; explicit override required for conflicts; unused conflicts also rejected; reordered responses restored to their original positions |
| Batch cost | 100 files and 500 directives; a real external program starts once and returns all results |
| Processes and protocol | Protocol v2 with full input scope and mandatory output collections; three-channel exchange exceeding pipe capacity, strict JSON, missing/duplicate/unknown IDs, nonzero exits, timeouts, SIGINT, channels held by descendants, and process group cleanup after failure |
| Output publication | Separate pages and reports, authoritative report sets and stale report pruning, provenance protection, symlink and parent conflicts, close EIO before publication, and partial publication with injected I/O failure or SIGINT and explicit completed/stopped paths |
| Project self-use | `mise run acceptance` renders real Rust source, Python tools, and examples in six languages; project package/modules/spec names, built-in include/code, complete spec reference coverage, determinism, four fault injection classes, and material/argument updates |
| Documentation governance | 53 unique product clauses, explicit anchors, local links, AGD metadata, and generated indexes |

`mise run review` publishes source pages under `.source-down/pages/` and the current
`.source-down/reports/spec/coverage.md` report. All 53 normative clauses have successful references near their owning
implementation or acceptance tests. Unknown IDs, duplicates, missing anchors, literal examples, zero/partial references,
invalid inventory bytes, and recovery are exercised through the real spec plugin process. Configuration remains version 1.

Of the Rust tests, 29 verify behavior in memory through public source/render, directive extraction, and protocol JSON interfaces; 56 use real files, the CLI, or processes.
Four Python tests exercise the metadata plugin's actual JSON exchange, including material errors and empty batches; seven verify the coverage gate and compiler wrapper.
Coverage collection includes instrumented Rust CLI/plugin children and self-use, plus Python plugin children. The gate is checked with exact 90% counts,
89.999% counts that display as 90.00%, missing files, zero measurable lines, Python exclusions, and large unrelated test/plugin denominators.
The compiler wrapper change followed a failing Rust instrumentation build that exposed Zig's handling of linker symbol arguments.
See the [coverage guide](coverage.md) for scope and reproduction; fresh HTML and raw reports are written under `.source-down/coverage/`.
The new behavior was developed from observed failing CLI tests for per-file pages, empty plugin batches, spec expansion,
coverage errors, unknown-reference reports, invalid inventories, appendices, report pruning, planned path conflicts,
and publication progress after I/O failure or cancellation. Existing include tests stayed green during generic Markdown section extraction;
existing behavior tests covered the publication module split.
Source metadata regressions first reproduced collapsed paragraphs through the real spec and external plugin processes, then verified separate CommonMark paragraphs,
literal linked paths containing spaces, brackets, hashes, and backticks, and unchanged spec content after the rendering change.

Direct dependencies were queried against OSV before installation, with no known advisories found. All selected versions had been published for at least 30 days and had not been yanked.
The screening tool's GitHub Advisory query was unavailable, so that source was not counted as successful evidence.
Dependency screening is a record of this point in time; subsequent dependency updates require the same checks.

## Performance baseline

Six workloads were measured with the release build, each with an initial invocation and two repeated invocations. Every group with directives contains 500 of them.
Plugin material comes from arguments, with zero bytes of external material files. The workloads contain approximately 17–24 KiB of source code: a small synthetic corpus designed to isolate
startup and batch processing costs.

| Files | Argument pattern | Source bytes | First run, ms | Repeated runs, ms | Maximum RSS, MiB | Plugin launches |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | none | 17280 | 10.06 | 9.90–11.32 | 5.22 | 0 |
| 1 | same | 24390 | 57.63 | 47.97–58.69 | 12.81 | 1 |
| 1 | different | 21780 | 55.80 | 55.38–55.40 | 12.74 | 1 |
| 100 | none | 17280 | 8.58 | 10.36–10.75 | 5.09 | 0 |
| 100 | same | 24390 | 42.75 | 44.05–44.48 | 12.74 | 1 |
| 100 | different | 21780 | 42.57 | 43.69–43.97 | 12.68 | 1 |

Maximum RSS comes from Linux wait4 in the minimal C launcher, preserving kernel resource statistics for the CLI and its child processes;
it is not the sum of RSS across concurrent processes. Time and memory figures are baselines for these inputs on this host; no absolute performance gate is set across machines.
See [benchmark-baseline.json](benchmark-baseline.json) for the complete raw data, output sizes for each run, and versions.
`mise run benchmark` reproduces the same workload.

## Relocatable artifacts

`mise run release` creates a local binary archive, a complete source archive, and SHA256SUMS. The script extracts both actual
archives, runs the archived binary from the relocated directory, and performs version checks, real self-use fault injection, and review document generation.
It uses the extracted directory's own `.mise.toml` and `mise run build` to build the project spec plugin and CLI from archived source and Cargo registry dependencies. Both the archived and rebuilt programs run against that plugin; every generated page and report must have matching bytes.
The source archive includes this record and the specifications, work rules, implementation, lockfile, tests, examples, and tools needed to repeat the checks.

Successful generation, tests, and source traceability provide acceptance evidence for this implementation and remain inputs to Rule 0 design and review.
