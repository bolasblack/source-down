# Project extensions

Projects configure local plugins that expand directives, compose standard content and
publish reports through the [plugin protocol](../../../../docs/specs/plugins.md).
Source Down's own `spec` directive has its separate
[project-owned contract](../../../../docs/specs/project-directives.md).

## Sub-features

- `plugin-composition`: execute a configured Python plugin and preserve node order.
- `plugin-standard`: compose standard include/link in page, appendix and report positions.
- `plugin-protocol`: drive the real Rust spec plugin's NDJSON request/response boundary.
- `plugin-failure`: distinguish check errors from invalid responses and recover.

## How to get to it (user POV)

- Register a command and directive names under `[plugins.<id>]` in `source-down.toml`,
  write those directives in authored files, then run render/watch.
- As a plugin author, start the plugin process and exchange the protocol's initialize,
  ready and run messages through stdin/stdout.
- Read generated `reports/<plugin>/<name>.md` and stderr diagnostics after a run.

## Driving it with acceptance.py

Preconditions: complete [Launch and Doctor](../SKILL.md). Use the repository's local
Python/Rust plugins and fixture configurations. Never substitute an arbitrary project
plugin with unknown external side effects for these fixtures.

- **Configured Python entry (`plugin-composition`).** Run
  `mise exec -- python tools/acceptance.py --case self_use/test_project_composition.py --review`.
  The real plugin's title, included SourceSpan code and following explanation appear
  in order; returned directive-looking text remains literal.
- **Standard content/report entry (`plugin-standard`).** Run
  `mise exec -- python tools/acceptance.py --case link/test_rust_plugin.py --review`.
  A built Rust plugin composes content into the page, appendix and report with exact
  URLs, source records and dependencies at each position.
- **Protocol author entry (`plugin-protocol`).** Run
  `mise exec -- python tools/acceptance.py --case self_use/test_spec_delegation.py --review`.
  The recorded protocol response includes the ready message and one standard include
  descriptor with line bounds derived from the preserved clause text. This is plugin
  boundary evidence; the render recipes separately prove CLI integration.
- **Failure/recovery entry (`plugin-failure`).** Run
  `mise exec -- python tools/acceptance.py --case render/test_plugin_check_failure.py --review`,
  then `mise exec -- python tools/acceptance.py --case render/test_plugin_missing_response.py --review`
  and `mise exec -- python tools/acceptance.py --case link/test_publication.py --review`.
  Check errors preserve the expected pages/index and recover after restoration;
  missing responses preserve complete old output. Report publication follows the
  case's actual standard-link targets and error class.

## Gotchas

- The project's `spec` names, numbering and coverage policy belong to that plugin;
  they are not requirements on every Source Down project plugin.
- Source spans establish provenance, not the correctness of a plugin's interpretation.
- The external process protocol permits local fixture fault injection. It does not
  justify replacing the CLI, filesystem or publication path with internal setters.
- Watch-driven plugin restart/repair belongs to the [watch map](watch.md). Full pipe,
  timeout and Session coverage also includes retained native tests.
