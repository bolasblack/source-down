# Standard URLs and inline directive acceptance

This record covers the 2026-09-09 link and inline-directive delivery. Product behavior
belongs to [standard operations](../specs/standard-directives.md#spec-blt-008),
[cross-language design](../specs/standard-directives.md#spec-blt-009),
[directive placement](../specs/directives.md#spec-dir-006),
[rendering](../specs/rendering.md#spec-ren-011),
[publication](../specs/cli.md#spec-cli-004) and
[search](../specs/search.md#spec-srh-001).

The author supplies the surrounding syntax:

```markdown
[下一篇]({% link "docs/details.md" %}#anchor)
```

The standard operation produces only the relative URL. The label and fragment are
author bytes. The user explicitly replaced the original plan's Markdown wrapper,
`text` parameter and anchor validation with this contract. Earlier wrapper acceptance
and the anchor test's RED are retained as superseded history, not current acceptance.
The revised plan is `/tmp/source-down-link-directive-implementation-plan.md`.

## Public evidence

All cases execute the actual CLI against isolated files. Python and Rust plugins
exchange real protocol messages; assertions read final pages, reports and snapshots.

| Evidence | Observation |
| --- | --- |
| Pure URL RED, `20260909T072621-1c44594a80ad` | The old Markdown wrapper fails exact returned-body assertions |
| Pure URL GREEN, `20260909T072733-896e8e63cb2e` | Pages, placement and argument cases pass after the URL-only change |
| Inline and container RED logs | `/tmp/source-down-link-inline-red.log`, `/tmp/source-down-link-inline-context-red.log`, `/tmp/source-down-link-inline-index-red.log` retain missing expansion and tight-list indexing failures |
| Publication RED log | `/tmp/source-down-link-publication-red.log` retains the unpublished-report-target failure |
| Current link suite, `20260909T080448-b1da32166fca` | All ten scenarios pass, including seven input languages, author fragments, CRLF, multiple calls, failed inline layout, exact source bytes, special filenames, canonical links, stale snapshots, overrides and both plugin languages |
| Authored guide | `self_use/test_guide_navigation.py` verifies independently declared targets in default and custom output roots |
| Predeclared project queries, `20260909T080402-e01919615bac` | All five queries pass; the first `code_span` result still points to the complete accurate function, with `top_k = 1` and unchanged ranking |
| Independent CommonMark parsing | `tests/link.rs` checks actual labels and encoded destinations, including backticks and native-valid question marks |
| Completed failed rounds | `tests/link.rs` checks missing/unselected query dependencies and absence of dependencies for invalid arguments through public Session outcomes |

Run directories under `.source-down/e2e/runs/` retain the preserved cases, binary
identities, original command output and machine result. Filtered runs remain partial;
their successful selected cases do not claim full-suite acceptance.

The include adapter replacement was preceded by the existing readable include case
and a material-corruption mutation (`20260909T071458-47ddad40aeb2`). The operation's
byte/selector/source assertions now use the actual project-plugin and publication
boundary. A real plugin that modifies a material between builtin and delegated calls
proves both consumers retain the same round's original bytes.

## Controlled counterexamples

`/tmp/source-down-link-mutations-20260909/provenance.json` retains exact replacements,
source and binary hashes, commands and assertions. Each private mutant builds and
fails its named readable scenario; production source remains unchanged.

| Mutation | Rejecting run |
| --- | --- |
| Compute URLs from the output root instead of the actual containing directory | `20260909T080735-fd7a8a8d8bbf` |
| Accept an old output page for an unselected target | `20260909T080737-95e2d9c7f6ec` |
| Leave inline calls unsubstituted | `20260909T080739-fe21932bd387` |
| Publish a report URL when this round cannot publish its target pages | `20260909T080741-41e85fb267a7` |

Static documentation checks run on a byte-identical temporary copy because AGD
validation generates managed files. The old checker rejects directive URL expressions;
the current checker passes, while actual guide generation verifies the resulting
destinations. Logs are in `/tmp/source-down-link-docs-check/`. This checker comparison
was recorded after the documentation change, not as a pre-edit RED.
The guide's generated-path and author-anchor checks are owned by its real E2E
scenario. Static lint retains broken literal-path and normative-anchor validation.

## Design review

The selected-page catalog is the only owner of target eligibility. Actual content
placement comes from the evaluator; plugins cannot inject placement or parent sources.
Builtin adapters return descriptions, so ordinary and delegated calls share one
operation and SourceStore. Dependency sorting and validation remain with the result
owner after removal from the adapter.

The renderer and search collector share one substitution projection. Generated URL
bytes have no fabricated original-byte mapping. Valid tag parameters are opaque to
outer Markdown, while code and HTML retain their literal boundary. The CR/LF check
protects exact single-line composition; the report publication check protects this
round's actual page availability. Tight list items need explicit leaf collection
because CommonMark does not emit paragraph events for their implicit paragraphs.

## Measurement and completion gates

The retained pre-development baseline is
`/tmp/source-down-link-watch-baseline-20260909/baseline.json`. On the same Linux host,
the revised 1,002-page workload has 10,000 inline references to 1,001 distinct targets
and 583,130 source bytes. It took 4.879528932 seconds and 317,304 KiB peak RSS; the
predeclared limits are 10 seconds and 488,724 KiB. Raw measurements and the executed
binary hash are in `/tmp/source-down-link-performance-20260909/result.json`.
The original anchor-scan limit was superseded by the user's removal of anchor scanning;
time and memory budgets were preserved.

The complete local checks pass with 192 Rust tests (including the E2E bridge),
41 Python tool tests and 33 readable E2E scenarios. The coverage run records
6,542/6,835 core lines (95.71%), 297/308 Rust spec-plugin lines (96.43%) and
110/114 Python project-plugin lines (96.49%). New production modules are included.
Formatting, strict Clippy and documentation checks pass; complete self-review publishes
139 pages. The six existing generation benchmark workloads and search budgets pass.

`mise run acceptance` records full success and verified reading pages in
`20260909T082208-f0f3e5a82942`. The subsequent language-target extension also passes
in `20260909T082302-2db3abe1d91d`, checking links to Markdown and all six source languages.

`mise run release` passes for Linux x86-64 GNU. The extracted CLI has SHA-256
`d36a4d48d1e65b21b89dd9871840ca492045e3a314178c332b07a951ef3cb092`.
Its full 33-case acceptance runs are `20260909T081619-ac29bd1725d2` and, with the
relocated rebuilt source/plugin, `20260909T081718-ada710656cb7`. The retained source
archive SHA-256 is `cd92a7c7e0b04dfd6734e1b4d689aedd2e35f03eafd244e97146849ac1576e70`;
the binary archive is `432be36e1e8c648b72ec49f8a1feb30b9b4f8aa22a11f12705fc1c075a0f39e4`.
These archive hashes identify the tested release checkpoint before this record's
final result annotation and the additional language-target assertion.

No implementation deviation or unresolved specification gap is recorded for this
slice. [Native CI run 34328996521](https://github.com/bolasblack/source-down/actions/runs/34328996521)
at `29060c0c076f8bd292b1da3208024c9c29db50e9` passes Linux and macOS. Windows passes
32 of the 33 E2E scenarios but rejects the relative-symlink fixture with native error
123. That fixture passed a slash-separated string as Windows reparse-point data;
it now supplies a native `Path` to `os.symlink`. Query and URL expectations remain
unchanged. The original Windows artifact is verified against SHA-256
`f2fc505fdad42c10f01871b11f282c5102c96d010106b0e44982cc09599058c8` and retained in
`/tmp/source-down-link-ci-20260909/run-34328996521/`.

The fixture correction is committed as `22b68150eca0e51cc2bf2a8dab3cf4558eacf267`.
[Native CI run 34331033821](https://github.com/bolasblack/source-down/actions/runs/34331033821)
passes all three jobs: Ubuntu 24.04, macOS 15 and Windows 2022. The exact-head run
and job metadata are retained in `/tmp/source-down-link-ci-20260909/run-34331033821/`.

The separate watch implementation and its acceptance remain governed by its own plan.
