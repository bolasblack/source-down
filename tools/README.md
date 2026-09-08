# Project tools

These files move with the project. The Python scripts use the standard library; coverage measurement invokes separately installed development tools. [.mise.toml](../.mise.toml) manages tool versions and task entry points.

- `project_docs.py` is Source Down's own project plugin. `package` reads the name and version from Cargo.toml and accepts one optional text label; `modules` lists Rust modules under src and their line counts. It initializes once per session, reads NDJSON runs until stdin EOF, flushes every response, uses the public JSON protocol, and shares material reads within each batch. It declares a file dependency before each material read; `package` depends on Cargo.toml, and `modules` declares the recursive src directory plus every Rust file it reads. All caches and dependencies are rebuilt for each run.
- `spec_plugin.rs` implements this project's `spec` directive through the persistent v1 protocol. `mise run build` compiles it as the `spec-plugin` Cargo example. It reads and indexes actual spec headings once per run, expands short IDs, rejects unknown or ambiguous references, and returns a coverage report even when there are zero requests. It reuses the library's generic CommonMark section reader; spec numbering and coverage rules stay in this project plugin.
- `acceptance.py --binary PATH` coordinates the readable `tests-e2e/cases` scenarios. `--list` discovers without executing; `--case` selects an exact file or workflow subtree; `--review` renders this run's preserved cases, fixtures and real outcomes. Every run prints its own absolute results and entry paths. Product assertions live in the cases, including original self-use checks and both compiled handle-collision mutations. See the [E2E contract](../docs/engineering/e2e.md).
- `benchmark.py --binary PATH --output PATH` compiles a minimal C launcher, then uses Linux wait4 to measure six fixed workloads. It measures three CLI invocations and three rounds in one persistent session per workload, saving raw elapsed time, maximum RSS, actual initialization counts and maximum frame bytes. `session_benchmark.rs` drives the public Session API for this measurement.
- `check_docs.py` checks local documentation links, SPEC IDs, explicit anchors, and AGDs. It rejects SPEC clause IDs anywhere in decision records, including link anchors and code examples, with file/line diagnostics. `mise run lint` runs it alongside formatting and Clippy; `mise run check` combines lint with the test and coverage task.
- `test.py` runs all Rust and Python tests, collects fresh profiles, generates HTML/JSON reports, and enforces separate 90% production line coverage gates. `coverage.toml` configures Python subprocess measurement; see the [coverage guide](../docs/engineering/coverage.md).
- `cc` and `ar` adapt the Zig version selected by mise for compilation and archiving. `cc` translates Rust target names for Linux x86_64 GNU builds and forwards linker symbol arguments used by coverage instrumentation.
- `release.py` packages the existing release binary and relocatable project source, runs real smoke tests after extraction, rebuilds the source independently, and records SHA-256 checksums.

New projects can write their own process plugins or reuse this example's implementation. This consuming project owns `package`, `modules`, `api`, and `spec`. `acceptance.py` accepts `--spec-plugin PATH` when the executable is outside the CLI's adjacent `examples/` directory.
See [source-down.toml](../source-down.toml) at the project root for registration and the [plugin specification](../docs/specs/plugins.md) for public fields and failure semantics.

## Returning composed content

The Python project plugin's `api` example accepts one nonempty, single-line entity name. It returns introductory text, a standard include of that exact name in src/model.rs, and closing text. It constructs ordinary dict/list values and does not read the delegated material. The [authored guide](../docs/guide/expanding-directives.md) uses `api "SourceSpan"` in the actual self-use run.

The following success item corresponds to `// {% api "Cache" %}` followed by LF in `src/notes.rs`. The host calculates the included material's source; the two text nodes explicitly use the parent call's actual source.

```json
{
  "id": "d1",
  "status": "ok",
  "content": [
    {"kind":"text","text":"## Cache","sources":[{"path":"src/notes.rs","start_byte":3,"end_byte":20,"start_line":1,"end_line":1}]},
    {"kind":"standard_call","directive":"include","arguments":{"positional":["src/cache.rs"],"named":{"id":["Cache"]}}},
    {"kind":"text","text":"The cache implementation is shown above.","sources":[{"path":"src/notes.rs","start_byte":3,"end_byte":20,"start_line":1,"end_line":1}]}
  ]
}
```

Insert this item in the `results` array of the existing result message, include the other required top-level fields, and send one flushed NDJSON line. The same `content` object works in appendices (with `page`) and report values. Nodes are complete Markdown blocks: they cannot share an open fence or HTML block. Their text, including directive examples, is terminal content. A standard call always selects the distribution's include even when the project overrides the author's include route.

Both `lines: "12-27"` and `lines: [12,27]` select the same inclusive range. The Rust spec plugin resolves each definition and constructs a standard include with `[start_line, end_line]` from its actual SourceSpan. The core supplies exactly that section's bytes and sources without searching its anchor again. Definitions and coverage remain plugin-owned, and delegation adds neither a reference nor another batch. This example uses the Rust public model; Python uses plain JSON without an SDK. A returned descriptor does not synchronously return material to plugin code. The core combines delegated dependencies with the plugin's own declarations.

Existing complete `markdown`/`sources` responses remain supported with identical output bytes. They cannot be mixed with `content`. Configuration and protocol versions remain 1; plugins returning `content` require a core that supports this extension. A main call's material error fails the check and permits valid reports to update. An appendix or report call error aborts the round and preserves all old artifacts.

CommonMark also recognizes lone CR as a heading newline, while physical source lines use LF. If a spec section starts or ends inside such an LF line, the spec plugin returns its exact Markdown and SourceSpan through the existing form. Whole-line sections use standard include. This preserves precise section ownership without enlarging a byte range to a whole line.
