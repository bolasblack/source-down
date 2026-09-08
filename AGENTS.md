# Source Down

Source Down is a literate programming tool. Read the [product model](docs/specs/model.md#spec-mod-001) when evaluating product scope or new capabilities. Preserve the original source code, source locations, and ownership boundaries of project extensions.

## Authority

- `docs/specs/` is the only normative source for product behavior, file formats, the CLI, and the plugin protocol. When code conflicts with a specification, fix the code; when a specification is incomplete or contradictory, revise the owning clause first.
- `.agents/decisions/` owns decisions about implementation language, architecture, tooling, and development acceptance criteria.
- `docs/engineering/` explains implementation practices. Generated reading material, types, and tests serve as projections and evidence.

For product behavior changes, update the owning specification; creating or updating an AGD is optional. Record an AGD when there is lasting design rationale, a trade-off, an attempted approach and its result, a lesson, or a condition for reconsideration to preserve. AGDs are self-contained historical decisions and must not reference SPEC clause IDs, including link anchors and code examples. Keep current behavior rules in specifications and implementation navigation in engineering documentation. Mark future ideas as not yet adopted.

## Work

1. Before changing product implementation, read the [specification index](docs/specs/README.md), the [model](docs/specs/model.md), and the owning specification. Write or update the owning clause first, then write the corresponding readable E2E test and observe a failure caused by the missing behavior through its public boundary. Only then implement the smallest passing change and refactor while green. Record red and green evidence. For behavior-preserving refactors, establish the existing specification and E2E coverage before editing, using a bounded mutation check where needed. Unit and component tests supplement this acceptance evidence. For E2E writing, migration, execution and reading material, follow the [engineering contract](docs/engineering/e2e.md).
2. When changing comment recognition, directive execution, or rendering, read the respective specifications linked from the index. For actual files, plugin processes, and output publication, use tests at those real boundaries as acceptance evidence.
3. Before changing module structure or the toolchain, read [AGD-002](.agents/decisions/AGD-002_choose-rust-and-source-range-parsing.md) and the [engineering handoff](docs/engineering/README.md). Use stable, complete clause IDs in code and documentation references.
4. When changing directive notation, read the [directive syntax](docs/specs/directives.md); when changing calls or return values, read the [plugin protocol](docs/specs/plugins.md). Each project defines its plugins' names, argument semantics, and material selection; the generic core obtains results through the protocol.
5. When completing a slice, check the relevant clauses, implementation, tests, and generated material. Record implementation deviations, specification gaps, and missing evidence separately. Successful batch generation proves only the corresponding results of the generation contract.

See [.agents/CLAUDE.md](.agents/CLAUDE.md) for decision record formats and index maintenance. Consult the engineering handoff and actual repository files for the current implementation state.
