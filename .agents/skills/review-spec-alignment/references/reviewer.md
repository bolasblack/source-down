# Packet reviewer

Judge one clause. Write nothing. Return one JSON object. The coordinator records
it.

When the prompt includes a prior finding, use Recheck.

## Material

Read the packet at the absolute path in the prompt. It already holds the clause
bytes, linked clauses, the code under each call site, every test named for the
clause, and the acceptance rows. Extra files are allowed only to confirm a
suspicion that packet already raised; every extra path belongs in `evidence` as
`path:start-end`. Extra files are project sources, specs, or tests the packet
named.

When the packet raises a suspicion that needs a public-CLI reproduction, use
[verify-source-down](../../verify-source-down/SKILL.md) and keep that run's
evidence paths in `evidence`.

## Return

```json
{"clause": "SPEC-CLI-004",
 "verdict": "aligned|implementation-defect|spec-gap|coverage-gap|stale-engineering-doc",
 "evidence": ["src/publication.rs:21-271", "docs/specs/cli.md:120-158"],
 "finding": "one line, empty when aligned"}
```

Each `evidence` entry is a path and the line range the claim rests on.

## Verdicts

The five names are the contract's verdicts:
[spec alignment contract](../../../../docs/engineering/spec-alignment.md),
matching [AGD-001](../../../decisions/AGD-001_adopt-rule-0-spec-first-development.md).

- `aligned` — the clause, the code under its markers, and the tests named for it
  still say the same thing.
- `implementation-defect` — the implementation disagrees with the clause.
- `spec-gap` — the clause is incomplete or contradictory for the behavior present.
- `coverage-gap` — the behavior the clause requires is unexercised. Reach this
  by reading the clause against the tests the packet carries, not from a missing
  same-name test.
- `stale-engineering-doc` — an engineering document no longer matches the clause
  or the implementation.

## Facts, not findings

Read these packet sentences as facts:

- `No test name references <CLAUSE>.` — no test carries this clause's number.
  A test named for a neighbouring clause may still cover the behavior; the
  packet cannot see that.
- `No acceptance row names <CLAUSE> in …` — absence of a table row.
- `UNRESOLVED` on a test heading — return that heading to the coordinator;
  Launch should have stopped.
- `no code under marker` — that call site has no code fragment in the window.
- `Also marked by:` — several clauses share one segment. Judge whether this
  clause's marker sits above behavior it owns.
- `(also owns …)` on a test — the same body is named for other clauses too.

## Recheck

Confirm the prior finding by quoting the bytes that make it true, or reject it.
The quoted bytes belong in `evidence`. Your verdict is the recorded one.

## Done when

The JSON names the prompted clause, one of the five verdicts, an evidence range
for every claim, and a one-line finding that is empty if and only if the verdict
is `aligned`.
