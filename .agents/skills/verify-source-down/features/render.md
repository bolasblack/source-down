# Render and material inclusion

Authors weave source comments, unchanged code and referenced material into Markdown
pages. Read [rendering](../../../../docs/specs/rendering.md),
[include](../../../../docs/specs/standard-directives.md#spec-blt-003) and
[publication](../../../../docs/specs/cli.md#spec-cli-004) for the expected behavior.

## Sub-features

- `render-material`: include Markdown where the author placed the directive.
- `render-languages`: generate the six source languages with code labels and sources.
- `render-output`: select a custom output root and preserve traceable reading material.
- `render-failure`: preserve the specified previous outputs on invalid input/material.

## How to get to it (user POV)

- Run `source-down render` with source files, Markdown files or directories.
- Write `{% include "guide.md" %}` in Markdown or an eligible source comment.
- Add `--output-dir` to choose the generated reading location.
- Edit an input or referenced material, then render again.

## Driving it with acceptance.py

Preconditions: complete [Launch and Doctor](../SKILL.md). Each recipe seeds its own
files; no edits to the real project are required.

- **Material and failure paths (`render-material`, `render-failure`).** Run
  `mise exec -- python tools/acceptance.py --case render --review`.
  [The include case](../../../../tests-e2e/cases/render/test_include_markdown.py)
  places the guide text before the original function. Other cases verify missing
  material, malformed/unregistered directives and plugin failures against explicit
  page/index or whole-output preservation scopes; repair cases then render again.
- **Source inputs (`render-languages`).** Run
  `mise exec -- python tools/acceptance.py --case self_use/test_six_languages.py --review`.
  The real project, examples and plugins generate pages containing all declared
  code labels and Source, Call site and Content source annotations.
- **Output selection (`render-output`).** Run
  `mise exec -- python tools/acceptance.py --case self_use/test_custom_output.py --review`,
  then `mise exec -- python tools/acceptance.py --case self_use/test_guide_source_excerpts.py --review`.
  The custom output matches the expected reading set; guide excerpts preserve their
  original bytes and provenance in both output locations.
- **Retain actual product bytes when requested.** Follow
  [raw output capture](../references/capture-output.md) for `render-material`.
  Inspect its saved generated page and index alongside the command logs.

## Gotchas

- Default configuration is read under `--root`. The harness supplies isolated roots;
  directly rendering a small subset of this repository can fail its project-owned
  full spec-reference check.
- Render progress is on stderr and successful stdout is empty.
- Error classes have different publication rules. Use each case's exact preservation
  scope; a valid plugin check error can update reports while preserving pages/index.
- Include's entity/line selectors have additional native coverage. This seed map's
  simple Markdown inclusion case does not establish every selector or byte boundary.
