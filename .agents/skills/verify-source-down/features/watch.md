# Watch and repair

Authors keep reading pages current while editing files, then recover from observable
input/configuration/plugin failures. Read [SPEC-CLI-008](../../../../docs/specs/cli.md#spec-cli-008)
and [SPEC-CLI-009](../../../../docs/specs/cli.md#spec-cli-009).

## Sub-features

- `watch-native`: generate immediately and update through native notifications.
- `watch-poll`: explicitly use content polling, including same-size/same-mtime edits.
- `watch-discovery`: handle added/renamed/deleted inputs within the owned scope.
- `watch-repair`: preserve the required old output, observe a repair and publish again.
- `watch-stop`: interrupt the owned process and observe exit/child cleanup.

## How to get to it (user POV)

- Run `source-down watch src docs` and edit selected inputs or dependencies.
- Add `--poll` for explicit polling.
- Supply `--config FILE` or use the project's default `source-down.toml`.
- Repair a failed input/configuration/plugin or publication path while watch waits.
- Press Ctrl+C in the terminal that owns the watch process.

## Driving it with acceptance.py

Preconditions: complete [Launch and Doctor](../SKILL.md). Use the case-owned watch
instances and their bounded observations. Linux fault cases need the repository's C
toolchain and OS facilities; applicability comes from the actual case metadata.

- **All mapped entries and failure windows.** Run
  `mise exec -- python tools/acceptance.py --case watch --review`.
  Inspect individual cases and subtests, including platform reasons, publication
  preservation, recovery and explicit process reaping before harness teardown.
- **Native entry (`watch-native`, `watch-stop`).** Run
  `mise exec -- python tools/acceptance.py --case watch/test_first_round.py --review`
  and `mise exec -- python tools/acceptance.py --case watch/test_native.py --review`.
  Initial pages appear; stdin closure does not end watch; edits/atomic replacements
  update output; the owned interrupt returns 130 where asserted.
- **Polling entry (`watch-poll`).** Run
  `mise exec -- python tools/acceptance.py --case watch/test_poll.py --review`.
  Diagnostics identify polling and same-size/same-mtime edits change pages/search.
- **Discovery/repair (`watch-discovery`, `watch-repair`).** For a focused check run
  `mise exec -- python tools/acceptance.py --case watch/test_discovery.py --review`,
  `mise exec -- python tools/acceptance.py --case watch/test_configuration.py --review`
  and `mise exec -- python tools/acceptance.py --case watch/test_configuration_explicit.py --review`.
  Page ownership and default/explicit configuration recovery have their own expected
  outcomes. These focused cases do not cover every repair window in the full group.

## Gotchas

- Wait for observed output/log facts; a fixed sleep alone is not proof of publication.
- Native initialization/fallback, explicit polling and healthy native operation are
  distinct paths. A poll pass cannot verify the native path.
- Watch can publish part of a round before a publication failure. Preserve each case's
  exact expected completed paths and old index, rather than assuming global atomicity.
- A harness cleanup flag proves teardown completed. Product cancellation/reaping claims
  require the scenario's explicit observations before cleanup.
- Never attach to or terminate a watch instance that this run did not start.
