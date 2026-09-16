# Complete readable E2E suite verification

Proposal 003 implements all **68 original scenarios as 99 discovered targets**:
core 24→29, link 10→17, watch-A 17→32 and watch-B 17→21. All four retained bodies
are unchanged. The implementation, grouped runtime checks, bounded sensitivity
experiments and all 99 source-order readability reviews are complete. All five final
repository gates passed on Linux, including the relocated source release.

## Evidence and baseline

The starting HEAD is `5ba6303feb6f53d3a09d0dd4b83dd238b2be8dc4`. Existing uncommitted
Proposal 001/002 changes were the baseline. This migration changes test expression,
shared test mechanisms and engineering records; it does not change product behavior,
product specifications, ranking, plugin protocol or production test switches.

All machine evidence is retained in `.source-down/e2e/migrations/003/` (abbreviated
**E** below). The original `/tmp/source-down-readable-e2e-003-5ba6303` path remains a
symlink to that directory. Evidence includes the 293 initial git-visible files in
`before/`, `start-hashes.json`, the complete baseline result and supplied executables.
When `/tmp` exhausted inodes, only this task's evidence was moved; all 35,588 moved
file hashes matched. New ordinary temporary projects use a task-owned cache directory;
permission scenarios retain real `/tmp` roots and ordinary credentials.

The baseline Linux run `20260910T094800-9e5d576280a3` passed all 68 cases. Fresh baseline
discovery was `20260910T142430-0cb0d080f59d`. Final live discovery
`20260910T172906-ec9a0459855b` found exactly the 99 planned paths and full IDs, with
no missing, duplicate or extra cases. Listing does not execute tests.

| Supplied artifact | SHA-256 |
| --- | --- |
| release CLI | `88bde0d07055a2037fce64879e957d17654162747855af785d420ebc97dcd543` |
| Rust spec plugin | `109dc680773b52a87cccf12bb2ba0850bc7d552b2f338d3c4aba139a5f03f109` |

`final-implementation-hashes.json` freezes 277 implementation, test, tool, guide and
specification files before final gates. Each run records its own actual executable,
platform, argv, raw stdout/stderr, child lifecycle and source hashes. CLI commands use
the supplied executable; fixed plugins run as real processes. The coordinator's outer
command log is not a separate OS exec trace of every plugin child.

## Complete ownership and readability

`complete-case-and-subtest-map.json` records all 68 original full IDs and original
subTest identities, each new ID/title/platform, its actual run, commands and target
subTest or independent stage. Original checks are individually bound to concrete new
statements in `core-assertion-map.json` (140 sites), `link-complete-check-map.json`
(123 sites), and `watch-assertion-map.json` (216 sites): **479/479** original assertion,
shape and subTest sites. C17/C19's five external guide calls are additionally mapped
in `core-review-guide-call-map.json`; they retain their original rounds and frozen
excerpt inputs. These ledgers are evidence; standard unittest discovery owns execution.

The source/header/explicit-include reviews answer initial state, action and expectation
for every target: `core-readability-review.md` (29), `link-completion.md` (17), and
`watch-readability-review.md` (53). Their source/include hashes are retained alongside
the reports. Core received a separate read-only source review; the watch integration
review was performed by the integration owner. Neither is represented as a blind
independent runtime verification.

The following complete index links to the authored target bodies. Precise old-line
owners, original and new subTest labels, original values and stage order are in the
machine ledgers above. All targets inherit their original specs and platform declarations.

| Original case under `cases/` | Decision | New case(s) | Original→focused commands |
| --- | --- | --- | --- |
| `link/test_arguments.py` | migrate | [arguments](../../tests-e2e/cases/link/test_arguments.py) | 10→10 |
| `link/test_inline.py` | restructure | [inline_rendering](../../tests-e2e/cases/link/test_inline_rendering.py)<br>[inline_sources](../../tests-e2e/cases/link/test_inline_sources.py) | 1→2 |
| `link/test_inline_context.py` | migrate | [inline_context](../../tests-e2e/cases/link/test_inline_context.py) | 1→1 |
| `link/test_inline_failure.py` | restructure | [inline_newlines](../../tests-e2e/cases/link/test_inline_newlines.py)<br>[inline_syntax](../../tests-e2e/cases/link/test_inline_syntax.py) | 5→6 |
| `link/test_pages.py` | migrate | [pages](../../tests-e2e/cases/link/test_pages.py) | 1→1 |
| `link/test_placement.py` | restructure | [delegated_link_placement](../../tests-e2e/cases/link/test_delegated_link_placement.py)<br>[link_override](../../tests-e2e/cases/link/test_link_override.py) | 2→4 |
| `link/test_publication.py` | restructure | [publication](../../tests-e2e/cases/link/test_publication.py) | 4→4 |
| `link/test_rust_plugin.py` | migrate | [rust_plugin](../../tests-e2e/cases/link/test_rust_plugin.py) | 2→2 |
| `link/test_search.py` | restructure | [inline_search](../../tests-e2e/cases/link/test_inline_search.py)<br>[link_snapshot_refresh](../../tests-e2e/cases/link/test_link_snapshot_refresh.py) | 14→20 |
| `link/test_targets.py` | restructure | [target_urls](../../tests-e2e/cases/link/test_target_urls.py)<br>[unselected_targets](../../tests-e2e/cases/link/test_unselected_targets.py)<br>[material_targets](../../tests-e2e/cases/link/test_material_targets.py)<br>[external_targets](../../tests-e2e/cases/link/test_external_targets.py) | 6→9 |
| `mutations/test_record_record.py` | keep | [record_record](../../tests-e2e/cases/mutations/test_record_record.py) | 6→6 |
| `mutations/test_record_scope.py` | migrate | [record_scope](../../tests-e2e/cases/mutations/test_record_scope.py) | 5→5 |
| `read/test_current_entity.py` | migrate | [current_entity](../../tests-e2e/cases/read/test_current_entity.py) | 1→1 |
| `read/test_root_alias.py` | migrate | [root_alias](../../tests-e2e/cases/read/test_root_alias.py) | 4→4 |
| `read/test_utf8_continuation.py` | keep | [utf8_continuation](../../tests-e2e/cases/read/test_utf8_continuation.py) | 3→3 |
| `render/test_bad_directive.py` | migrate | [bad_directive](../../tests-e2e/cases/render/test_bad_directive.py) | 3→3 |
| `render/test_include_markdown.py` | migrate | [include_markdown](../../tests-e2e/cases/render/test_include_markdown.py) | 1→1 |
| `render/test_missing_material.py` | migrate | [missing_material](../../tests-e2e/cases/render/test_missing_material.py) | 2→2 |
| `render/test_plugin_check_failure.py` | migrate | [plugin_check_failure](../../tests-e2e/cases/render/test_plugin_check_failure.py) | 3→3 |
| `render/test_plugin_missing_response.py` | migrate | [plugin_missing_response](../../tests-e2e/cases/render/test_plugin_missing_response.py) | 3→3 |
| `render/test_unknown_directive.py` | migrate | [unknown_directive](../../tests-e2e/cases/render/test_unknown_directive.py) | 3→3 |
| `search/test_project_queries.py` | restructure | [query_markdown_adapter](../../tests-e2e/cases/search/test_query_markdown_adapter.py)<br>[query_markdown_context](../../tests-e2e/cases/search/test_query_markdown_context.py)<br>[query_source_paths](../../tests-e2e/cases/search/test_query_source_paths.py)<br>[query_source_store](../../tests-e2e/cases/search/test_query_source_store.py)<br>[query_code_span](../../tests-e2e/cases/search/test_query_code_span.py) | 32→40 |
| `search/test_publication_facts.py` | restructure | [publication_facts](../../tests-e2e/cases/search/test_publication_facts.py) | 5→5 |
| `search/test_search_then_read.py` | migrate | [search_then_read](../../tests-e2e/cases/search/test_search_then_read.py) | 3→3 |
| `search/test_stale_snapshot.py` | migrate | [stale_snapshot](../../tests-e2e/cases/search/test_stale_snapshot.py) | 5→5 |
| `self_use/test_argument_refresh.py` | migrate | [argument_refresh](../../tests-e2e/cases/self_use/test_argument_refresh.py) | 3→3 |
| `self_use/test_custom_output.py` | migrate | [custom_output](../../tests-e2e/cases/self_use/test_custom_output.py) | 3→3 |
| `self_use/test_deterministic_generation.py` | keep | [deterministic_generation](../../tests-e2e/cases/self_use/test_deterministic_generation.py) | 2→2 |
| `self_use/test_entity_selection_refresh.py` | restructure | [entity_selection_refresh](../../tests-e2e/cases/self_use/test_entity_selection_refresh.py) | 6→6 |
| `self_use/test_guide_navigation.py` | restructure | [guide_navigation](../../tests-e2e/cases/self_use/test_guide_navigation.py)<br>[guide_source_excerpts](../../tests-e2e/cases/self_use/test_guide_source_excerpts.py) | 2→4 |
| `self_use/test_material_refresh.py` | migrate | [material_refresh](../../tests-e2e/cases/self_use/test_material_refresh.py) | 3→3 |
| `self_use/test_project_composition.py` | keep | [project_composition](../../tests-e2e/cases/self_use/test_project_composition.py) | 1→1 |
| `self_use/test_six_languages.py` | migrate | [six_languages](../../tests-e2e/cases/self_use/test_six_languages.py) | 1→1 |
| `self_use/test_spec_delegation.py` | migrate | [spec_delegation](../../tests-e2e/cases/self_use/test_spec_delegation.py) | 1→1 |
| `watch/test_adoption.py` | restructure | [adoption](../../tests-e2e/cases/watch/test_adoption.py)<br>[adoption_reordered](../../tests-e2e/cases/watch/test_adoption_reordered.py)<br>[adoption_missing_page](../../tests-e2e/cases/watch/test_adoption_missing_page.py)<br>[adoption_edited_page](../../tests-e2e/cases/watch/test_adoption_edited_page.py)<br>[adoption_corrupt_index](../../tests-e2e/cases/watch/test_adoption_corrupt_index.py)<br>[adoption_different_scope](../../tests-e2e/cases/watch/test_adoption_different_scope.py) | 18→18 |
| `watch/test_adoption_links_unix.py` | migrate | [adoption_links_unix](../../tests-e2e/cases/watch/test_adoption_links_unix.py) | 6→6 |
| `watch/test_baseline_health_linux.py` | restructure | [baseline_health_linux](../../tests-e2e/cases/watch/test_baseline_health_linux.py)<br>[baseline_cancellation_linux](../../tests-e2e/cases/watch/test_baseline_cancellation_linux.py) | 5→5 |
| `watch/test_blocked_cleanup_linux.py` | migrate | [blocked_cleanup_linux](../../tests-e2e/cases/watch/test_blocked_cleanup_linux.py) | 3→3 |
| `watch/test_body_reads_linux.py` | restructure | [body_reads_linux](../../tests-e2e/cases/watch/test_body_reads_linux.py)<br>[body_reads_failure_linux](../../tests-e2e/cases/watch/test_body_reads_failure_linux.py) | 2→2 |
| `watch/test_cancellation_linux.py` | restructure | [cancellation_linux](../../tests-e2e/cases/watch/test_cancellation_linux.py)<br>[cancellation_repair_linux](../../tests-e2e/cases/watch/test_cancellation_repair_linux.py)<br>[cancellation_batch_linux](../../tests-e2e/cases/watch/test_cancellation_batch_linux.py) | 3→3 |
| `watch/test_check_repair.py` | migrate | [check_repair](../../tests-e2e/cases/watch/test_check_repair.py) | 2→2 |
| `watch/test_cleanup_window_linux.py` | migrate | [cleanup_window_linux](../../tests-e2e/cases/watch/test_cleanup_window_linux.py) | 3→3 |
| `watch/test_configuration.py` | restructure | [configuration](../../tests-e2e/cases/watch/test_configuration.py)<br>[configuration_explicit](../../tests-e2e/cases/watch/test_configuration_explicit.py) | 4→4 |
| `watch/test_content.py` | migrate | [content](../../tests-e2e/cases/watch/test_content.py) | 2→2 |
| `watch/test_dependency_scope.py` | restructure | [dependency_scope](../../tests-e2e/cases/watch/test_dependency_scope.py)<br>[dependency_removal](../../tests-e2e/cases/watch/test_dependency_removal.py) | 1→2 |
| `watch/test_dependency_window.py` | migrate | [dependency_window](../../tests-e2e/cases/watch/test_dependency_window.py) | 2→2 |
| `watch/test_directory_replacement.py` | migrate | [directory_replacement](../../tests-e2e/cases/watch/test_directory_replacement.py) | 2→2 |
| `watch/test_discovery.py` | migrate | [discovery](../../tests-e2e/cases/watch/test_discovery.py) | 2→2 |
| `watch/test_discovery_scope.py` | restructure | [discovery_scope](../../tests-e2e/cases/watch/test_discovery_scope.py)<br>[discovery_excluded](../../tests-e2e/cases/watch/test_discovery_excluded.py)<br>[discovery_empty_repair](../../tests-e2e/cases/watch/test_discovery_empty_repair.py) | 2→4 |
| `watch/test_execution_repair.py` | migrate | [execution_repair](../../tests-e2e/cases/watch/test_execution_repair.py) | 2→2 |
| `watch/test_fallback_linux.py` | restructure | [fallback_linux](../../tests-e2e/cases/watch/test_fallback_linux.py)<br>[fallback_explicit_linux](../../tests-e2e/cases/watch/test_fallback_explicit_linux.py)<br>[fallback_cancellation_linux](../../tests-e2e/cases/watch/test_fallback_cancellation_linux.py) | 4→6 |
| `watch/test_first_round.py` | migrate | [first_round](../../tests-e2e/cases/watch/test_first_round.py) | 1→1 |
| `watch/test_link_repair_unix.py` | migrate | [link_repair_unix](../../tests-e2e/cases/watch/test_link_repair_unix.py) | 2→2 |
| `watch/test_missing_parent.py` | migrate | [missing_parent](../../tests-e2e/cases/watch/test_missing_parent.py) | 2→2 |
| `watch/test_native.py` | migrate | [native](../../tests-e2e/cases/watch/test_native.py) | 1→1 |
| `watch/test_notification_permissions_linux.py` | migrate | [notification_permissions_linux](../../tests-e2e/cases/watch/test_notification_permissions_linux.py) | 2→2 |
| `watch/test_notification_publication_linux.py` | restructure | [notification_rescan_publication_linux](../../tests-e2e/cases/watch/test_notification_rescan_publication_linux.py)<br>[notification_error_publication_linux](../../tests-e2e/cases/watch/test_notification_error_publication_linux.py) | 5→6 |
| `watch/test_output_projection.py` | restructure | [output_projection](../../tests-e2e/cases/watch/test_output_projection.py) | 3→3 |
| `watch/test_partial_dependencies.py` | migrate | [partial_dependencies](../../tests-e2e/cases/watch/test_partial_dependencies.py) | 2→2 |
| `watch/test_poll.py` | migrate | [poll](../../tests-e2e/cases/watch/test_poll.py) | 2→2 |
| `watch/test_project_code.py` | migrate | [project_code](../../tests-e2e/cases/watch/test_project_code.py) | 2→2 |
| `watch/test_publication_faults_linux.py` | restructure | [page_publication_failure_linux](../../tests-e2e/cases/watch/test_page_publication_failure_linux.py)<br>[obsolete_page_deletion_failure_linux](../../tests-e2e/cases/watch/test_obsolete_page_deletion_failure_linux.py)<br>[index_publication_failure_linux](../../tests-e2e/cases/watch/test_index_publication_failure_linux.py)<br>[publication_cancellation_linux](../../tests-e2e/cases/watch/test_publication_cancellation_linux.py) | 12→15 |
| `watch/test_publication_repair.py` | migrate | [publication_repair](../../tests-e2e/cases/watch/test_publication_repair.py) | 2→2 |
| `watch/test_query_links_unix.py` | restructure | [query_links_unix](../../tests-e2e/cases/watch/test_query_links_unix.py) | 3→3 |
| `watch/test_script_cleanup_linux.py` | migrate | [script_cleanup_linux](../../tests-e2e/cases/watch/test_script_cleanup_linux.py) | 6→6 |
| `watch/test_six_languages.py` | migrate | [six_languages](../../tests-e2e/cases/watch/test_six_languages.py) | 7→13 |
| `watch/test_unknown_repairs.py` | restructure | [unknown_repairs](../../tests-e2e/cases/watch/test_unknown_repairs.py) | 4→4 |
| `watch/test_unreadable_unix.py` | migrate | [unreadable_unix](../../tests-e2e/cases/watch/test_unreadable_unix.py) | 1→1 |

## Preserved boundaries and cost

- Full JSON, full single-page body, body text alone, first hit, unique filtered hit,
  ordered dependencies, first occurrence and forward search remain distinct checks.
  The `code_span` acceptance keeps top_k=1 and the exact original function/source
  interval; kind and occurrence ownership are not newly constrained.
- Whole output, exactly two leaves, pages plus index, and all Markdown including
  reports retain their original scopes. MissingMaterial now checks its two baseline
  files before editing. Default/custom output comparisons remain independent.
- Exit-zero-only commands remain exit-zero-only; stdout empty is explicit. Captures
  remain at the original phase, including search-before-snapshot and shifted guide
  excerpts. All five in-flow guide checks remain in their owning refresh rounds.
- Separate waits remain separate, and immediate assertions are not converted to extra
  waiting. Configuration repair combines extra-page existence and its exact manifest
  in one predicate; input discovery waits for its final manifest. DependencyWindow
  checks both ready/unpublished phases before release. Missing files and malformed
  JSON keep their original errors. Static windows remain 1.1, 1.2 or 1.6 seconds.
- Native C fixtures are byte-identical to baseline. Tests preserve actual handshake
  release points, inotify masks/registrations, inode identities, held readers, ordinary
  uid permissions and `/proc` reaping before harness cleanup. Release remains visible
  in case `finally` blocks. No timed business retry or implicit repair was added.
- Fixed Python fixtures share only NDJSON transport. Payloads, dependencies, reports,
  diagnostics, options and handshake paths stay visible in one fixture/body. Existing
  command/protocol owners remain the sole executors; there is no scenario interpreter,
  second runner, cross-test import or generated fixture duplicate.

The four kept bodies are record-record collision, UTF-8 continuation, deterministic
self generation and project composition. Original matrices retain their failure
continuation scope, or map explicitly to independent IDs. C12 renders before each
output subTest. Old combined query/link/notification/publication files were deleted
only after every old check had an owner and target execution had passed. The two short
include fixtures were removed after reference checking; their exact bytes are inline.

Focused command counts are 267→305: core 101→111 (eight independent query baselines,
two guide baselines), link 46→59 (thirteen declared split preparations/readbacks),
watch-A 63→68 (two extra fallback compilations, one dependency and two discovery
watch starts), and watch-B 57→67. Four of watch-B's additions are independent C builds;
six are extra observed probes of the existing six-language search polling loop.
Polling counts depend on publication timing, so these are measured costs, not a fixed
future count. Every argv flag and ordering was checked in `core-command-map.json`,
`link-command-map.json` and `watch-command-map.json`; only disposable roots and handles
proven to come from actual search output were normalized.

## Runtime and sensitivity evidence

All 29 core targets passed focused Linux runs and reading verification; exact run IDs
are in `core-command-map.json`. The final link run is
`20260910T150311-331c8c3a7370` (17 passed, reading passed). The corrected complete watch
integration run is `20260910T171325-aa20e614c618` (53 passed, reading passed); its source
hashes match the transferred live cases. All 20 external helper tests passed in
`shared-helpers-green.log`.

| Mechanism | Actual bounded experiment and result | Evidence under E |
| --- | --- | --- |
| Full artifact protection and exact complete read/source | After real failure, corrupt a protected page; after real read, require an extra body byte; require a valid but one-byte-longer code_span source. All three fail their intended assertions. | `core-sensitivity-results.json` |
| Collision identity and failure continuation | Actual private Rust short-handle mutant: four wrong identity/kind/output variants fail the original operation checks. The six-case run retains expected pass/fail subTest sequences and two normal controls. | `core-sensitivity-results.json`, run `20260910T152307-840c0ae715b6` |
| Real Rust plugin result | Invoke the supplied Rust spec plugin and require incorrect delegated line bounds. The exact protocol result assertion fails. | `core-sensitivity-results.json`, run `20260910T152315-ace72796423f` |
| Link navigation, mappings, sources and publication | 27 original/new-owner controlled negatives run the actual coordinator/artifacts and fail ordinary assertions. Three permissive controls pass: empty mappings and additional sources where only source-item-0 was originally required. | `link-sensitivity-results.json`, `link-permissive-results.json` |
| Watch synchronization and native observation | Real file read produces IN_ACCESS/IN_OPEN; premature page written during actual read/response pause; incorrect old index during C baseline fault; wrong live PID for /proc reaping; existing file inode absent from actual inotify directory registration. Five intended assertion failures, followed by a healthy case passing in the same run. | `watch-a-sensitivity-results.json`, run `20260910T172351-837422530f34` |
| Native publication, quiet plugin and ordinary permission | Wrong link URL; wrong retained index during C publication EIO; wrong event count after real Rescan and 1.1-second window; wrong diagnostic under actual ordinary uid. Four intended assertion failures, each restored before GREEN. | `watch-b-report.md`, runs `151457-c793ffb2c923`, `151519-64dac831cb0f`, `151544-3a53c56f64b0`, `151628-e0314a17ca11` (20260910 prefix) |
| Shared API preconditions | Real render with missing declared baseline file fails before the next command; real watch checks new-log offsets, conjunction, exact manifest, missing-file errors and bound argv; real two-render excerpt capture rejects changed/wrong bodies. | `tests/e2e_helpers_test.py`, `shared-helpers-green.log` |

The plan's per-case negative checkpoints are owned by their exact old→new assertion
rows. The experiments above sample each required mechanism through real boundaries;
they are not claims of a distinct production mutation for every hypothetical defect.
The unchanged UTF-8 public continuation case and source/pagination helper external
tests retain exact budgets and offsets. The real link controls specifically prevent
accidental strengthening of first-source or empty-mapping contracts.

Missing helper methods/signatures were recorded as harness API errors, not product
RED. The watch argv external regression was RED before its shared construction fix
and GREEN afterward. Early ordinary-uid attempts failed at sandbox `setgroups`, and
two integration runs hit `/tmp` inode exhaustion; those are facility failures. The
ordinary-uid reruns and final watch run used real permissions and adequate inode
capacity. All bounded negative runs retained their expected reading output and
recorded command cleanup. No failure was converted to a skip to obtain GREEN.

## Final repository gates

Implementation files were frozen before these commands. `MISE_DISABLE_TOOLS=java`
and a task-specific mise cache avoid unrelated global tooling; `TMPDIR` is the
task-owned cache directory. Native permission tests run with the privileges needed
to enter ordinary credentials. Documentation result entries are filled after each
gate; executable/test sources remain frozen.

| Command | Result and actual scope | Evidence under E |
| --- | --- | --- |
| `mise run lint` | PASS: formatting, Clippy and documentation (56 documents, 76 normative clauses). | `final-lint.log` |
| `mise run test` | PASS: 207 Cargo test passes across 22 harness summaries, including the full 99-case E2E bridge; 61 Python tests. Coverage: core 8832/9339 (94.57%), Rust spec plugin 297/308 (96.43%), Python project plugin 113/120 (94.17%). | `final-test.log`; E2E `20260910T173229-731819ece098` |
| `mise run review` | PASS: 229 project/guide pages and spec coverage report published. | `final-review.log` |
| `mise run acceptance` | PASS: all 99 cases, all command cleanup, and reading verification; 100 reading pages including the index. | `final-acceptance.log`; run `20260910T173909-2d3e22505c62` |
| `mise run release` | PASS on x86_64-unknown-linux-gnu: extracted binary, native portability, relocated offline source rebuild, all 99 packaged E2E cases, and identical rendering by extracted/rebuilt binaries. | `final-release.log`; retained run `20260910T174215-25f2ef500301` |

The coverage bridge uses the instrumented CLI
`8bd345dd77c9a35a38ba79620af3797f074b5201903ecace0efb9faf002ecc2e` and instrumented
spec plugin `ee5c0a57357addd63f4b506a3f335acd971c3202f3b9f12e2ff2ce25c1a615e9`.
Its documentation status is `not_requested`. The separate final acceptance run uses
the release hashes listed above and has `documentation.status=passed`; its 167
recorded frozen source hashes match the live implementation. The reading entry is
`.source-down/e2e/runs/20260910T173909-2d3e22505c62/reading/pages/index.md.md`.

The relocated release result is retained under
`.source-down/e2e/runs/20260910T174215-25f2ef500301/results.json`; its documentation
status is `not_requested`. The release gate does not replace the separate reading
verification above. Local package SHA-256 values are:

- `source-down-0.1.0-source.tar.gz`: `6d9e967fd40763c0f7b02fafb2d9ac9a48b2c085cff34ad758ae0accff563c2a`.
- `source-down-0.1.0-x86_64-unknown-linux-gnu.tar.gz`: `7eb4f5789b47bcc6e3ca9052a9e3bd12d7240ae4c2e9aaf4efcc0f781c627a89`.

Final preservation checks confirm the 277 frozen implementation files, all four kept
case files, and all 80 saved production/specification/tool/example files still match
their reviewed baselines. The recorded implementation deviations are the explicitly
planned splits, additional independent preparation and narrow shared helper APIs.
There are no unresolved specification gaps or missing applicable Linux evidence for
this migration. No Git commit, index or remote was changed during Proposal 003.

Only the actual Linux host is covered by these local results. macOS, Windows and
other architecture runtime claims remain for their existing CI runners. A filtered
run, list result or successful Markdown generation is not full-suite or cross-platform
acceptance.
