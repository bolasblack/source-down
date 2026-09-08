# Source Down

Source Down is a **literate programming tool** for writing and maintaining explanations and source code together. Authors explain a program's ideas, assumptions, and design alongside its implementation, then weave them into traceable Markdown. The [product model](docs/specs/model.md#spec-mod-001) defines its scope.

Write in Markdown chapters or native source files: standalone comments become prose, code appears in fenced blocks in its original order, and directives expand related material at their original positions. Source Down supports `.md` narrative inputs and Rust, OCaml, JavaScript, TypeScript, Go, and Python source inputs.

| Language | Extensions |
| --- | --- |
| Rust | `.rs` |
| OCaml | `.ml`, `.mli` |
| JavaScript / JSX | `.js`, `.mjs`, `.cjs`, `.jsx` |
| TypeScript / TSX | `.ts`, `.mts`, `.cts`, `.tsx` (including `.d.ts`) |
| Go | `.go` |
| Python | `.py`, `.pyi` |

Python `#` comments become prose; docstrings remain source code. JavaScript, TypeScript, Go, and Python inputs require complete, parseable syntax; type errors and undefined names do not prevent conversion. See the [source rendering specification](docs/specs/rendering.md) for the exact boundaries.

```ocaml
(** # Bounding a retry delay

    Keep retries at least one second apart to avoid a busy loop.
    Cap the delay at one minute so a retry stays responsive.
*)
let retry_delay seconds = max 1 (min 60 seconds)
```

Write directives as template tags, with quoted positional arguments and named arguments in `name=value` form:

```text
{% include "docs/design.md" %}
{% include "docs/design.md" id=["Overview",0,"Details"] %}
{% include "src/source.rs" id="parse" %}
{% include "notes.txt" lines="1-3" %}
{% include "notes.txt" lines=[1,3] %}
```

`include` accepts a file path and an optional `id` or `lines` selector. Markdown headings and source entities use the same structural paths: array strings are exact names, and numeric indices select same-name siblings in current source order. Each parent must be unique before traversal continues. The file type determines its parser. The include plugin returns complete Markdown, using prose for Markdown material and fenced blocks for source code; project plugins generate their own Markdown. See the [six-language entity rules](docs/specs/entities.md) for declaration ranges and capability limits. Projects can write external plugins in any language. A conflict with a built-in name is a configuration error unless an explicit `override` is declared. See the [directive specification](docs/specs/directives.md) for the full syntax and the [built-in directives](docs/specs/standard-directives.md) for content selection.

`link` accepts one input path and returns only its generated page URL. Use it inside ordinary prose, including a Markdown link:

```markdown
[Next page]({% link "docs/details.md" %}#anchor)
```

From `docs/index.md`, this becomes:

```markdown
[Next page](details.md.md#anchor)
```

The author owns the label and fragment; `link` accepts no named parameters. All standard directives share the same syntax and semantics across Markdown and the six source languages. Inline results must contain no line breaks; use a standalone directive for block content. Code examples and escaped tags remain literal. The [Rust navigation plugin](examples/navigation-plugin.rs) demonstrates standard calls in page content, appendices and reports.

## Build and use

The first release acceptance target is Linux x86_64 GNU. [.mise.toml](.mise.toml) pins Rust 1.90.0 (with rustfmt, Clippy, and LLVM tools), Python 3.14.7, Zig 0.15.2, and the coverage tools. Zig provides the C compiler and linker. After installing mise, run these commands from the project root:

```sh
mise trust
mise install
mise run build
./target/release/source-down render src --root /path/to/project
mise run review
```

`--root DIR` sets the project root. Relative input, configuration, and output paths are resolved against that root. A single invocation accepts multiple files or directories and processes them in canonical path order. By default, it reads `source-down.toml` from the root if that file exists.

Each input gets its own page: `src/queue.mli` becomes `.source-down/pages/src/queue.mli.md`. Plugin reports go to `.source-down/reports/<plugin>/<name>.md`. A Markdown input `docs/guide/index.md` becomes `.source-down/pages/docs/guide/index.md.md`, keeping the authored title and executing its own directives. Use `--output-dir review` to change the output root. Render progress and diagnostics go to stderr.

Use `source-down watch src docs` to keep pages and the search snapshot current while editing.
It generates immediately, then uses native file notifications; stderr identifies the actual
backend and each complete round. A newly discovered dependency may require a discarded
discovery round before the first publication. Healthy plugins stay available across rounds.
Changes to configuration or external plugin dependencies rebuild the session. Stop with Ctrl+C.

Use `source-down watch src docs --poll` on filesystems that do not reliably send notifications,
including some network and shared mounts. Native backend resource or I/O failures report the
reason and switch to content polling. Silence alone does not cause a switch. Polling compares
complete bytes, including edits that preserve file size and mtime.

Watch preserves previous reading material while waiting for an observable repair after an
input, configuration, plugin or publication failure. Diagnostics describe the repair scope.
It observes ordinary project files for first-failure recovery, while skipping `.git`, `target`,
`node_modules`, `.source-down` and generated trees; explicitly known programs and dependencies
remain observed across these ordinary exclusions. Repairing disk space or an unobservable
environment change may require editing an input/configuration or restarting. It only prunes
pages published by this process or safely adopted from a valid index for the same invocation
scope; orphaned and manually edited pages are preserved. See [watch acceptance](docs/engineering/watch-verification.md).

The render CLI validates a complete round and closes every external plugin before preparing outputs; each file is then replaced atomically. Valid plugin check errors preserve existing source pages and update reports that contain no standard page references; a report with a standard link to an unpublished page prevents publication. Execution, protocol, source, or preparation failures preserve all existing outputs. Publication failures stop further updates and identify completed paths. Each piece of material includes its source file, line numbers, and byte range so readers can return to the original.

An expanded directive has a **Call site** paragraph linking to its position in the source, followed by **Content source** paragraphs linking to the material returned by the plugin.
Paths appear as inline code inside links, preserving punctuation. The core renders these annotations from each content block's source spans, then places that block's Markdown immediately below them. Inline calls share the surrounding prose's source area, keeping the resulting Markdown structure intact.

Read the [authored guide](docs/guide/index.md), then run `mise run review` and open `.source-down/pages/docs/guide/index.md.md`. Its navigation targets generated pages and explicit display anchors. Included material stays literal: directives inside returned Markdown or quoted source are not executed again.

Build pages and their search snapshot with `source-down render src docs`, then query with
`source-down search SourceStore --path src`. Pass a returned 11-character handle to
`source-down read HANDLE --context 1` to read the exact stored fragment and its neighbours.
Both commands support `--json`, bounded results and continuation. They check current
files and outputs by default; `--snapshot` reads saved content with unchecked source links.
See [search and continued reading](docs/guide/searching.md) for scope, repeated occurrences
and pagination. `mise run review` builds the complete project's search snapshot.

For a known file and declaration, use `source-down read src/cache.py --id 'Cache.get'`
or `source-down read docs/retry.md --id '["重试策略",0]'`. This reads the current entity or
complete Markdown section directly, with its source span and file SHA-256; it needs no
configuration, plugin or index. Both read modes use a fixed 12000-character Unicode
budget and byte offsets. Compare file hashes and selected spans before joining chunks
from separate current-file calls. Add `--json` for structured output.

## Project extensions

Source comments:

```rust
// {% package "Build identity" %}
// {% modules %}
// {% spec "plg-001" %}
```

Project configuration:

```toml
config_version = 1

[plugins.project]
command = ["python3", "tools/project_docs.py"]
directives = ["package", "modules", "api"]

[plugins.spec]
command = ["target/release/examples/spec-plugin"]
directives = ["spec"]
```

This is the configuration Source Down uses for its own documentation. The [metadata plugin](tools/project_docs.py) reads package metadata and the module list. The [project spec plugin](tools/spec_plugin.rs), built by `mise run build`, expands numbered clauses from `docs/specs` and checks their references. Short and full IDs are case insensitive. Unknown references, duplicate definitions, invalid anchors, and unreferenced clauses fail the check. Each run writes `.source-down/reports/spec/coverage.md`, including reference locations and missing IDs. Its contract is in the [project directive specification](docs/specs/project-directives.md).

The coverage check compares the complete spec inventory against the selected source files. Use `mise run review` to review this whole project, including implementation and tests. Selecting only a subset still checks the full inventory. The plugin's optional `options.spec_dir` selects a different spec directory.

Each configured plugin initializes once per session and processes one complete batch per run, even with zero matching directives. It receives all selected file paths and all requests assigned to it, then returns request results, page appendices, named reports, diagnostics, and filesystem dependencies. Appendices identify their target by the original source path; report names determine their automatic output paths. Configuration stays at `config_version = 1`; the process exchange uses `protocol_version = 1`. See the [plugin protocol](docs/specs/plugins.md) for the complete fields and the [engineering handoff](docs/engineering/README.md#persistent-sessions) for the reusable Session API.

To replace a built-in name, set both `directives = ["include"]` and `override = ["include"]` in the corresponding plugin configuration.

Plugins can return ordered `text` and `standard_call` nodes in `content` for a request, appendix, or report. A standard include supplies its own material sources and always uses the distribution's implementation. Text and included Markdown remain literal output, including directive examples. The Python `api "SourceSpan"` example composes explanation and model source; the Rust spec plugin delegates its resolved clause through an include with an actual `lines` pair. See the [wire example and compatibility rules](tools/README.md#returning-composed-content).

## Verification and relocation

```sh
mise run check       # Both lint and test
mise run lint        # Formatting, Clippy, documentation, and AGD independence
mise run test        # All tests, HTML/JSON reports, and 90% line coverage gates
mise run review      # Pages, reports and search snapshot for the complete project
mise run acceptance  # Readable E2E, real plugins, self-use, and recorded fault injection
mise run benchmark   # Generation, search/read stages, scale and memory budgets
mise run release     # Local binary/source archives, extraction checks, and SHA-256
```

Line coverage must reach 90% separately for the Rust core, the Rust spec plugin, and the Python metadata plugin.
Both unit and integration tests contribute, including real CLI and plugin processes. `test` prepares the isolated Python coverage environment automatically; `check` depends on both `lint` and `test`.
Reports appear in `.source-down/coverage/`; see the [measurement scope and report guide](docs/engineering/coverage.md).
Spec reference coverage remains a separate check of clause usage.

`acceptance` prints absolute paths to this run's results and generated reading entry
under `.source-down/e2e/runs/<run-id>/`. The entry groups scenarios by workflow and
links their actual status, preserved source and owning clauses. Use
`mise exec -- python tools/acceptance.py --case search --review` for a partial run,
or `--list` for discovery only. See the [E2E writing and execution guide](tests-e2e/README.md)
and [migration ledger](docs/engineering/e2e-migration.md) for retained native evidence.

To start a new repository, extract the source archive or copy the versioned project files from this directory. Build caches, development toolchains, and generated material live in the ignored `target/`, `.source-down/`, and `dist/` directories and can be recreated in the destination. See the [release acceptance record](docs/engineering/verification.md) for measured verification results and performance baselines.

When developing in a subdirectory of another repository, mise merges parent configuration files.
To use only this project's configuration, set `MISE_CEILING_PATHS` to the parent of this project root before running the commands above.

| Topic | Entry point |
| --- | --- |
| Authoritative product requirements and stable SPEC IDs | [Specification index](docs/specs/README.md) |
| Language, architecture, development, and release decisions | [AGD index](.agents/INDEX-TAGS.md) |
| Rule 0 work rules | [AGENTS.md](AGENTS.md) |
| Modules, verification, and tool maintenance | [Engineering notes](docs/engineering/README.md) |

Source links connect the woven explanation and code to their original files and locations. Relative links within included prose retain their original spelling.

The product name is **Source Down** and the command is `source-down`. A [SourceDown plugin for Sublime Text](https://github.com/bordaigorl/sublime-sourcedown) also uses the name; this project is the independent CLI defined here. Package registry and code hosting release locations will be determined at publication time.
