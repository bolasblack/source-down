# Address alignment findings

Launch has already run. Follow this file instead of Review select. The coordinator
repairs; reviewers still return JSON only. Ledger rows are written only through
`--record`.

## Select

Read the ledger at `PATH/spec-alignment-ledger.md` from Launch stdout
(`spec_alignment: run PATH`). A current non-aligned row is eligible: the clause
still exists, and Launch did not list it under stale. Aligned rows are skipped.
Stale non-aligned rows are blocked until they are re-reviewed. Unreviewed
clauses have no finding.

Choose the work set:

1. User-named clause IDs — those that are eligible. Report aligned, stale, or
   unknown IDs as skipped or blocked.
2. Otherwise one eligible row: `implementation-defect` first, then `spec-gap`,
   then `coverage-gap`, then `stale-engineering-doc`, in ledger order within a
   verdict.

**Done when:** the work set is an explicit list of eligible clause IDs, or the
request is reported as having none.

## Repair

Handle one clause at a time through Re-record before opening the next. Read that
clause's packet and ledger note. Extra files are the sources, specs, or tests
the packet already named.

Follow Rule 0 in [AGENTS.md](../../../../AGENTS.md). The
[readable E2E contract](../../../../docs/engineering/e2e.md) owns how to write
and run those tests. When the missing behavior is a CLI workflow, use
[verify-source-down](../../verify-source-down/SKILL.md) for red and green
evidence.

By verdict:

- `implementation-defect` — keep the clause unless it is also wrong. Write or
  extend a test that fails because of this disagreement, then change the
  implementation.
- `spec-gap` — revise the owning clause in `docs/specs/` first. Then add the
  test the new text requires, then the code if the code does not already match.
- `coverage-gap` — add a test named for this clause that performs the missing
  action. If that test fails, fix the implementation while it is red. If it
  passes, the implementation already matched.
- `stale-engineering-doc` — update `docs/engineering/` to match the clause and
  the implementation.

A new Rust test uses `spec_<domain>_<nnn>` in its name. A new E2E case declares
this clause ID in the class `specs` tuple. Otherwise the next packet will not
carry the test. Shared segments named `Also marked by:` may move; keep the
repair on this clause's finding.

**Done when:** each selected clause has a product change that targets its
recorded verdict, or a reason written in PATH that the finding is not repaired;
every implementation edit has public red evidence.

## Re-record

After the change, before the next clause:

```sh
mise run alignment -- --run PATH
```

Dispatch a reviewer for that clause with [reviewer.md](reviewer.md) and the
rebuilt packet. Recheck if the verdict is not `aligned`. Record the resulting
JSON with `--record`. A still-open finding is recorded as itself.

**Done when:** each repaired clause has a ledger row for the fingerprint as of
this run.

## Close

Quote the run PATH from that alignment stdout. Report remaining stale,
unreviewed, and orphan counts, every still-open non-aligned row, the clauses
this run changed, and the public red and green evidence for each implementation
change. Notes and dispositions from this pass are in PATH. The user-facing
close-out is this reply.

**Done when:** the reply quotes the run PATH; remaining list counts are taken
from the alignment run after the last `--record`; every selected clause is
accounted for as recorded, blocked, or skipped.
