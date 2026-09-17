# Source Down verification map

Read this index after [Launch and Doctor](../SKILL.md). Select user workflows here;
the [specification index](../../../../docs/specs/README.md) remains the behavior owner
and the coordinator's discovery remains the runtime scenario inventory.

## Baseline preconditions

- Run commands from the Source Down repository root after a successful build/doctor.
- Use the built CLI and project plugins. The harness creates each scenario's inputs
  and configuration in its own temporary project; no credentials are needed.
- Keep the build and checkout fixed until the selected runs finish. Cases within a
  run execute serially; independent runs use separate project and evidence paths.

## Driving conventions

- Each recipe invokes `tools/acceptance.py` with an exact `--case` selector and `--review`.
  The selector is relative to `tests-e2e/cases/`. Read the selected source for its
  exact inputs, public commands and assertions before executing it.
- Run every recipe that covers a requested entry point. A passed neighboring path
  does not verify an unrun path. Feature files seed common user workflows; retained
  native tests and additional discovered scenarios still supply their own evidence.
- Use the existing cases for repeatable verification. Put new product assertions in
  those cases under the repository's spec-first E2E workflow.

## Proof and skip reporting

- Associate the feature/sub-feature IDs and user entry point with each printed run ID.
- Report selected/applicable/executed cases, skips, platform, tests and documentation
  separately. `--case` success is partial; `--list` is discovery only.
- Keep the current run's command bytes and results after process/project cleanup.
  Follow [Evidence](../SKILL.md#evidence) when actual generated files must be retained.
- A generation result proves its selected inputs and observed assertions. Reference
  coverage, line coverage and full semantic conformance are separate claims.

## Features

| Feature | User paths |
| --- | --- |
| [Render and material inclusion](render.md) | Source/Markdown inputs, include, output location, failure preservation |
| [Page navigation](navigation.md) | link in prose, generated targets, custom output, external composition |
| [Search and read](search-read.md) | Search then handle read, stale snapshot read, direct entity read, continuation |
| [Watch and repair](watch.md) | Native watch, explicit polling, editing/discovery, repair, cancellation |
| [Project extensions](extensions.md) | Configured Python/Rust plugins, protocol requests, reports, failure/recovery |
