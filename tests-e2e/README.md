# Readable E2E

The [engineering contract](../docs/engineering/e2e.md) defines development order,
execution and report semantics. The [migration ledger](../docs/engineering/e2e-migration.md)
separates the reading collection from retained native evidence and pending migrations.

```sh
mise run acceptance
mise run acceptance -- --jobs 4
mise exec -- python tools/acceptance.py --list
mise exec -- python tools/acceptance.py --case search --review
mise exec -- python tools/acceptance.py --case read/test_current_entity.py
mise exec -- python tools/acceptance.py --binary /path/to/source-down --spec-plugin /path/to/spec-plugin
```

The coordinator prints absolute paths for its own `results.json` and reading entry.
Each run has a unique directory under `.source-down/e2e/runs/`; there is no mutable
latest-success page. A filtered run is partial and listing executes no tests. Inspect
test status separately from documentation status. A failed run retains its results
and command logs. `mise run test` runs these modules alongside native Rust and Python
tool tests under one shared worker limit. Add `-- --review` to render reading from
that same execution. Direct `cargo test` reaches this coordinator through `bridge.rs`.
Python tool tests use the separate `*_test.py` pattern.

Independent scenario modules run in separate processes. The default worker limit is
the available CPU count; `--jobs N` or `SD_TEST_JOBS=N` overrides it. `--jobs 1` keeps
ordered execution for diagnosis. Operations and fixtures within a module retain
their order. The coordinator prints completed cases and timings while tests run.

One `cases/<workflow>/test_*.py` file describes one user scenario. Use ordinary
`unittest` assertions, a one-line test docstring for its title, complete owning clause
IDs in `specs`, and standalone comments for prose. Keep inputs, actions, exact expected
bytes/JSON and preservation assertions visible in the case. `E2ECase.project()` creates
an isolated mutable project. `project.sourceDown.render/search/read/readEntity`
execute the supplied CLI and save observations; domain assertions check only
declared expectations. `renderSuccessfully` guarantees exit 0 and empty stdout;
`searchSuccessfully` guarantees exit 0. `withBinary` selects a program for a separate
entry without changing the original. `readEntityToEnd`, `assertCompleteUtf8Read`
and `assertReadFromFile` express complete reading and file provenance separately.
Index assertions accept `rendered.index` as well as render/output observations or
captured index bytes. Search assertions accept the raw `project.run()` result;
simple read metadata/text/alias assertions accept one saved response. Complete
reading assertions require the `ReadResult` with its actual traversal facts.
Use `fields` for selected top-level metadata/manifest keys and `includesFiles`
for required render artifacts; complete ordered lists still use `equals`.
`project.run()` remains available for explicit command
matrices and returns raw byte streams. `subTest` records matrix outcomes. Explicit `platforms` metadata
retains inapplicable cases with a reason; ordinary skip/expected failure cannot pass
full acceptance.

The coordinator copies this collection, fixtures and linked specifications before
discovery. Python executes that preserved copy and Source Down renders those same
files. Self-use and mutation projects are separate. Place long shared inputs or
expected bytes in `fixtures/`, load them through `self.fixture()`, and include that
same path in the case's explanation. Root review excludes fixtures as inputs; an
explicit include can still show a textual fixture. Do not put spec-plugin directives
in these comments: the isolated reading root uses only builtin include.

For runtime saves, `writeInPlace(path, content)` keeps the target file object;
`atomicReplace(path, content, temporaryPath=...)` creates the named temporary
file exclusively and replaces the target after closing it. Both require existing
parent directories. Keep `writeFiles` for preparation that creates parents and
`replaceFile` for a replacement prepared earlier in the scenario.

Watch waits return saved observations: output `files` contains only the bytes
actually read by the successful attempt, logs contain the matched interval and
its end checkpoint, and events contain counted bytes and their count. Obtain a
watch-owned `checkpoint()` before editing and pass it as `since`; it marks a log
position without attributing events to the edit. Presence-only waits do not read
bodies, and multi-file observations do not promise one atomic publication.

Support supplies project preparation, named operations, immutable observations and
domain verification. Cases declare inputs, operations, concrete expectations and
preservation scopes. The dedicated guide case lists its URLs and source relationships
directly; refresh cases include a shared expectation file. Keep the two locations
in agreement when those expectations change. `editing` restores inputs; a subsequent
explicit render proves recovery. The collision cases declare the zero-handle
mutation, full record identities and unchanged output. Native parser, Session,
syscall and process tests remain in Rust and continue to run in the full suite.
