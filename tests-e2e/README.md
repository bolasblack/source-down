# Readable E2E

The [engineering contract](../docs/engineering/e2e.md) defines development order,
execution and report semantics. The [migration ledger](../docs/engineering/e2e-migration.md)
separates the reading collection from retained native evidence and pending migrations.

```sh
mise run acceptance
mise exec -- python tools/acceptance.py --list
mise exec -- python tools/acceptance.py --case search --review
mise exec -- python tools/acceptance.py --case read/test_current_entity.py
mise exec -- python tools/acceptance.py --binary /path/to/source-down --spec-plugin /path/to/spec-plugin
```

The coordinator prints absolute paths for its own `results.json` and reading entry.
Each run has a unique directory under `.source-down/e2e/runs/`; there is no mutable
latest-success page. A filtered run is partial and listing executes no tests. Inspect
test status separately from documentation status. A failed run retains its results
and command logs. `mise run test` invokes this same collection once through Cargo's
`bridge.rs`, without rendering it; Python tool tests use the separate `*_test.py` pattern.

One `cases/<workflow>/test_*.py` file describes one user scenario. Use ordinary
`unittest` assertions, a one-line test docstring for its title, complete owning clause
IDs in `specs`, and standalone comments for prose. Keep inputs, actions, exact expected
bytes/JSON and preservation assertions visible in the case. `E2ECase.project()` creates
an isolated mutable project; `project.run()` uses the supplied actual CLI and returns
raw byte streams. `subTest` records matrix outcomes. Explicit `platforms` metadata
retains inapplicable cases with a reason; ordinary skip/expected failure cannot pass
full acceptance.

The coordinator copies this collection, fixtures and linked specifications before
discovery. Python executes that preserved copy and Source Down renders those same
files. Self-use and mutation projects are separate. Place long shared inputs or
expected bytes in `fixtures/`, load them through `self.fixture()`, and include that
same path in the case's explanation. Root review excludes fixtures as inputs; an
explicit include can still show a textual fixture. Do not put spec-plugin directives
in these comments: the isolated reading root uses only builtin include.

Support supplies temporary files, process scopes, result events, reading projection
and narrow project/mutant preparation. It does not own product assertions. The two
collision cases show exact replacement provenance, original versus mutant commands,
failure identities and unchanged output. Native parser, Session, syscall and process
tests remain in Rust and continue to run in the full suite.
