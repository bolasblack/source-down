# Page navigation

Authors link their reading pages using `{% link "docs/details.md" %}` and ordinary
Markdown labels/fragments. The owner is [SPEC-BLT-008](../../../../docs/specs/standard-directives.md#spec-blt-008).

## Sub-features

- `link-pages`: compute relative URLs between selected input pages.
- `link-inline`: preserve surrounding prose, author fragments and literal examples.
- `link-output`: compute URLs under default and custom output roots.
- `link-errors`: reject invalid arguments and unavailable/outside-root targets.
- `link-composed`: resolve links at page, appendix and report output positions.

## How to get to it (user POV)

- Write `[Next]({% link "docs/details.md" %}#anchor)` in Markdown or source prose.
- Render both the author file and target, including via a selected directory.
- Choose another `--output-dir`, or configure a plugin that composes standard links.

## Driving it with acceptance.py

Preconditions: complete [Launch and Doctor](../SKILL.md). The build includes the Rust
navigation example needed by the complete link group.

- **All mapped navigation paths.** Run
  `mise exec -- python tools/acceptance.py --case link --review`.
  Read the case/subtest results: page URLs and source annotations must be exact;
  inline prose/code examples retain their structure; failures preserve the asserted
  old output. Default and custom output are distinct subcases.
- **Focused page entry (`link-pages`).** For a narrow reproduction, run
  `mise exec -- python tools/acceptance.py --case link/test_pages.py --review`.
  The two authored pages link to `details.md.md` and `index.md.md`; sources and index
  dependencies identify the original author inputs.
- **Composed entry (`link-composed`).** Run
  `mise exec -- python tools/acceptance.py --case link/test_rust_plugin.py --review`.
  A real Rust plugin returns include/link content. The page, appendix and report
  use URLs appropriate to their actual positions and preserve material bytes.

## Gotchas

- A material read by include does not thereby become a generated page. Link targets
  must be selected inputs; check the unselected/material-target failure cases.
- The author owns the fragment. A valid page URL does not prove the fragment exists.
- Platform-inapplicable symlink cases remain skipped with a reason; another case
  cannot establish their result on that platform.
- The focused page recipe proves only `link-pages`; use the group for all listed paths.
