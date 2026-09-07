# Include selection acceptance

Date: 2026-09-08. This record covers the selection-only argument surface in
[SPEC-BLT-003](../specs/standard-directives.md#spec-blt-003).

`include` accepts one file path and optional `id` or `lines`. Markdown headings and
the six source languages use the same structural path algorithm and one per-file
tree cache. The file type selects the parser. The include plugin returns complete
Markdown; project plugins construct their own prose or complete code blocks.

## Public boundary evidence

- A real-CLI contract probe first observed successful generation with each of the
  four parameters outside the new argument surface. After the change, all four
  returned exit 1 with `invalid_arguments`. The probe is retained at
  `/tmp/source-down-include-closed-arguments-probe.py`.
- The 23 tests in [standard_directives.rs](../../tests/standard_directives.rs) pass.
  They check shared Markdown/source paths, exact bytes and spans, duplicate names,
  CRLF and lone CR, line-array equivalence, malformed sources, missing files,
  unknown arguments, dependency retention and safe code fences.
- The first complete self-use check identified five examples using an argument
  outside the new surface. Those examples now select the same chapter through
  its full `id` path; the complete check then passed.
- Existing composition, real plugin, session and publication tests pass, including
  standard calls, refreshed file facts and preservation of old output on failures.

## Final checks

| Command | Observed result |
| --- | --- |
| `mise run check` | PASS: formatting, strict Clippy, documentation, all tests and coverage gates |
| `mise run review` | PASS: 69 pages and one spec coverage report |
| `mise run acceptance` | PASS: 758956 Markdown bytes across 70 pages and reports, including six languages, Rust/Python plugins, navigation, source edits and four fault mutations |
| `git diff --check` | PASS |

Line coverage is Rust core `4075/4275 = 95.32%`, Rust spec plugin
`297/308 = 96.43%`, and Python project plugin `110/114 = 96.49%`.
Release verification uses `mise run release` on the final source archive containing
this record, with an extracted binary and a clean relocated source build.

## Design check

The closed argument check owns rejection before material reads. Structural
selection owns missing, ambiguous and unsupported candidates. Language labels
come from the registered parser, so arbitrary label validation has no input to
protect. File dependencies and actual spans retain their existing owners.
Per-file trees share the round's SourceStore; no new cache lifetime or retry exists.
Adjacent HTML anchor bytes remain part of the original Markdown chapter, and the
project spec plugin owns its definition-anchor checks.

No implementation deviation, unresolved specification gap or missing evidence was
identified for this slice. No new performance measurement is claimed.
