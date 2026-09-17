---
name: verify-source-down
description: "Verify Source Down CLI behavior through its real render, link, search/read, watch, and project-plugin workflows. Use when asked to verify a Source Down change, reproduce a user workflow, or produce acceptance evidence with the existing readable E2E harness."
---

# Verify Source Down

Work from the Source Down repository root. Read the [feature map](features/README.md)
and select the requested user paths before running commands. This repository-local
skill uses the existing CLI and Python acceptance coordinator. Its recipes use a
POSIX shell; platform-specific cases retain their own applicability declarations.

[Specifications](../../../docs/specs/README.md) own product behavior. The
[E2E engineering contract](../../../docs/engineering/e2e.md) owns execution and
report semantics. Keep new behavioral assertions in `tests-e2e/cases/`; update the
owning specification and observe E2E red before implementing changed behavior.
This map supplies verification navigation, not another behavior specification.

## Launch

Use the toolchain pinned in [.mise.toml](../../../.mise.toml). A fresh checkout needs
`mise trust` and `mise install` as described in the [build instructions](../../../README.md#build-and-use).
Then build once:

```sh
mise run build
```

Require exit 0. The build produces `target/release/source-down` and the project
examples, including `target/release/examples/spec-plugin` and `navigation-plugin`.
On Windows these executables have `.exe` suffixes. Build failure is an unmet
precondition; preserve the error before attempting any feature drive.

No server, port, account, credentials, seed database, or `.env` file is required.
Mise supplies `PYTHONUTF8=1` and the repository's `ZIG_GLOBAL_CACHE_DIR`; no secret
values belong in evidence. Preserve inherited coverage variables when using the
runner from a coverage task.

The CLI is noninteractive. The existing harness launches each drive as a subprocess
in an isolated temporary project, with captured byte streams. Watch processes and
their plugins belong to that case's process scope. Separate runs have unique
projects and evidence directories; keep repository inputs and built executables
fixed while runs are active. See Cleanup for normal and interrupted teardown.

## Doctor

After building, or whenever a drive looks wrong, run this read-only check. It checks
the two required executables, CLI startup/version/commands, and their identities.
It does not exercise the plugin protocol; the extension scenarios do that.

```sh
python3 -B - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tomllib

root = Path.cwd()
suffix = '.exe' if os.name == 'nt' else ''
paths = {'binary': root / ('target/release/source-down' + suffix),
         'spec_plugin': root / ('target/release/examples/spec-plugin' + suffix)}
facts = {}
for label, path in paths.items():
    if not path.is_file() or not os.access(path, os.X_OK):
        raise SystemExit(f'Build prerequisite missing: {path}')
    facts[label] = {'path': str(path.resolve()),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
version = subprocess.check_output([paths['binary'], '--version'], timeout=10).decode().strip()
expected = tomllib.loads((root / 'Cargo.toml').read_text())['package']['version']
assert version == f'source-down {expected}', (version, expected)
help_text = subprocess.check_output([paths['binary'], '--help'], timeout=10).decode()
assert all(command in help_text for command in ('render', 'search', 'read', 'watch'))
print(json.dumps({'version': version, **facts}, indent=2))
PY
```

Require exit 0 and retain the printed identities with the verification report.
Compare them with this run's `results.json`; a version string alone cannot identify
a build. `--list` is a discovery action that writes a run directory, so it is not
the read-only doctor.

## Drive

Read the selected feature file and its linked scenario source. Choose all entry
points relevant to the requested claim. A single quick workflow is:

```sh
mise exec -- python tools/acceptance.py --case search/test_search_then_read.py --review
```

Every feature recipe uses this coordinator with an exact `--case` file or directory.
Run selectors separately; the flag does not accept a list or substring match.
Use `mise exec -- python tools/acceptance.py --list` to inspect current discovery.
Listing executes no cases. For the complete E2E collection and reading material:

```sh
mise run acceptance
```

The harness drives real CLI commands, files and plugin processes. Its cases keep
initial state, actions and assertions together. Rust Session and native boundary
tests supplement the map; `mise run test` owns the broader suite and coverage gates.
A selected run is always partial, even if its command succeeds. Follow the existing
release workflow when the claim concerns a packaged artifact or another platform.

## Evidence

Use the absolute `E2E results:` and `E2E reading:` paths printed by this invocation.
Each run lives under `.source-down/e2e/runs/<run-id>/`, which is gitignored. Retain:

- `results.json`: selection, platform, git/build identities, real case/subtest states,
  command argv/cwd, exit codes, process IDs, and cleanup observations.
- `logs/`: original stdout/stderr and any recorded protocol stdin or failure logs.
- `tests-e2e/` and `docs/specs/`: the preserved sources used by this run.
- `results.md` and, when documentation succeeds, `reading/pages/index.md.md`:
  readable actions, expectations, actual results, and links to their evidence.

Require `tests_status == "passed"` for the requested selected cases and separately
check `documentation.status == "passed"` when using `--review`. Report `scope`,
`full_pass`, skips and unrun entry points as recorded. Failed tests still have useful
reading material; successful page generation does not establish product conformance.

Inspect the recorded command and resulting state, including filesystem preservation,
source bytes/ranges, reports, and plugin cleanup where the scenario requires them.
Use real public paths; fixture plugins model the existing external process boundary.
Internal setters and test-only endpoints do not substitute for user actions.

E2E reading pages describe the executed tests. A scenario's own generated pages and
indexes usually live in a temporary project and its in-memory observations. When
actual output bytes must remain inspectable, use [raw output capture](references/capture-output.md)
before teardown. It saves inputs, logs and product artifacts separately from scratch.
Label it supplemental evidence, with its own scope and executable identity.

There is no verification dry-run flag. Rendering writes outputs and project plugins
can have their own side effects. Use the harness's isolated projects and known local
fixtures. If adapting a dry-run/test mode, observe files, processes, network or refs
relevant to its claimed exclusions instead of trusting the flag's name.

## Cleanup

Let the coordinator finish. Case context managers remove their temporary projects;
owned subprocess scopes reap their children, including after failures. For a running
coordinator you started, send Ctrl+C/SIGINT to that recorded process and wait for its
exit; interrupted acceptance exits 130. Preserve the resulting incomplete report.
Never kill by process name or terminate another run's watch/plugin instance.

After every successful, failed, or interrupted drive, inspect each started command's
`cleanup_complete` and terminal `exit_code` in `results.json`. If cleanup is missing,
inspect the exact recorded process scope and its current ownership before acting;
report the gap. Follow the raw-capture recipe's trap for its separately owned scratch.

Confirm this run's `results.json`, referenced logs, preserved sources and reading
entry still exist after cleanup. Keep the evidence directory; do not clean all of
`.source-down`. Report the feature IDs, entry points, selected results, remaining
gaps and absolute evidence paths. Evidence is never committed.

## Helpers

This skill ships instructions only. `tools/acceptance.py` and the existing
`tests-e2e/support/` code own execution, isolation, assertions and logs; invoke them
through the commands above. Use `/maintain-verification-skill` to audit this map as
the CLI and scenarios change.
