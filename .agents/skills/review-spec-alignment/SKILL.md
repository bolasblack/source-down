---
name: review-spec-alignment
description: "Review spec alignment: judge whether a clause, the code under its markers, and the tests named for it still say the same thing. Use when asked to review spec alignment, re-review stale clauses, record alignment verdicts in the ledger, or address alignment findings from the ledger."
---

# Review spec alignment

Work from the Source Down repository root. [Specifications](../../../docs/specs/README.md)
own product behavior. The [spec alignment contract](../../../docs/engineering/spec-alignment.md)
owns packets, fingerprints, the ledger, and the five verdicts (`aligned` plus the
finding kinds of
[AGD-001](../../decisions/AGD-001_adopt-rule-0-spec-first-development.md)). This
file is navigation, not another behavior specification.

The coordinator is this session. Reviewers return JSON. Only the coordinator runs
`tools/spec_alignment.py`. Ledger rows are written only through `--record` and
`--forget`.

## Step 1: Launch

A fresh checkout needs `mise trust` and `mise install` first.

A **round** is one complete review. Start a round only when the user asks for a
full review (including a new complete pass) or there is no round yet:

```sh
mise run alignment -- --new-run
```

Continue a named round when the user gives a PATH:

```sh
mise run alignment -- --run PATH
```

Continue the latest round when the user asks to look again after edits, take
status, close, or address findings, and does not name a PATH:

```sh
mise run alignment
```

Keep the full stdout and stderr. Exit 1 with a non-empty list is outstanding
review work, not a failed launch.

- The first stdout line is `spec_alignment: run PATH`. Packets are
  `PATH/packets/<CLAUSE>.md`. The ledger is `PATH/spec-alignment-ledger.md`.
  `--record` and `--forget` edit that PATH. Notes, dispositions, and other
  files this review produces are written in PATH. Product edits stay in the
  repository. PATH is the handle the user needs to name this round later.
  Quote it in every user-facing close-out. Archive only when the user asks.
- A stale-snapshot or other CLI failure is a precondition: apply the repair line
  the tool printed, then run this step again.
- `spec_alignment: unresolved test selector …` on stderr is a repository fix,
  not a verdict. Stop until that name resolves.
- `spec_alignment: N clauses reviewed and current` means every defined clause
  already has a matching row.

**Done when:** stdout starts with the run line, then either the current-line or
one or more of the three titled lists (a missing heading is an empty list);
stderr has no unresolved selector; every CLI refusal has been repaired.

## Route

- Status only — quote the run PATH, report Launch stdout, and stop.
- Address alignment findings from the ledger — read
  [references/process.md](references/process.md) and follow it.
- Otherwise continue at Review select.

## Step 2: Review select

Parse only the headings the tool prints. A heading is absent when its list is
empty:

- `Stale (reviewed at another fingerprint):` — content bytes changed; review again.
  Each entry is `CLAUSE <recorded> -> <current>`.
- `Unreviewed (no ledger row):` — no row means never reviewed. Treat the list as
  complete.
- `Orphan (ledger row without a clause):` — the ID is gone.

Resolve every orphan before reviewing anything else. Read `docs/specs/` to
establish deletion versus renumber. A renumbered clause appears under unreviewed
at the new ID and is reviewed there. Retire the dead row in the same change:

```sh
python tools/spec_alignment.py --run PATH --forget SPEC-XXX-001
```

`--forget` naming a clause with no row exits 1 and leaves the file unchanged.

Choose the review set:

1. User-supplied `clause + verdict` pairs — those clauses, even if current.
2. User-named clause IDs — those that appear under stale or unreviewed. Report
   current named IDs as skipped.
3. Otherwise at most three IDs, stale first, then unreviewed.

**Done when:** every orphan is forgotten or explained from `docs/specs/`; the
review set is an explicit list of clause IDs, and every ID in a review-only set
appears under stale or unreviewed.

## Step 3: Review

Skip this step and Recheck when the user already supplied a verdict for every
selected clause.

Before dispatching, read [references/reviewer.md](references/reviewer.md). Give
each reviewer that file and the absolute packet path. Prefer one isolated
reviewer per packet in parallel. If the host cannot dispatch isolated reviewers,
apply that file to one packet at a time in this session. Reviewers write nothing
and do not run the tool.

**Done when:** every selected clause has one JSON object matching the reviewer
schema.

## Step 4: Recheck

`aligned` is final. Every other verdict goes to a second reviewer with the same
packet, [references/reviewer.md](references/reviewer.md), and the first JSON.
The second JSON is the recorded one.

**Done when:** every non-aligned first verdict has a second JSON that either
quotes supporting bytes or rejects the finding; the recorded verdict is that
second object.

## Step 5: Record

Record serially, one invocation per clause, before any product edit:

```sh
python tools/spec_alignment.py --run PATH --record SPEC-CLI-004 --verdict aligned
python tools/spec_alignment.py --run PATH --record SPEC-SRH-002 --verdict coverage-gap \
  --note "one line of what was found"
```

PATH is the Launch run line. Use it on every `--record` and `--forget` in this session.

`--note` is the finding line; omit it when the verdict is `aligned`. The tool
refuses a note containing `|` or a line break, a verdict outside the five names
it accepts, and a clause `docs/specs/` does not define. Each call rebuilds that
packet in the selected run and rewrites that run's ledger whole from the
fingerprint as of now.

**Done when:** every selected clause has a ledger row written by this step; no
fingerprint was typed by hand; no spec, source, or test file changed.

## Step 6: Close

```sh
mise run alignment -- --run PATH
```

Quote the run PATH from this Close stdout. Report the remaining stale,
unreviewed, and orphan counts, every non-aligned verdict with its evidence and
the absolute packet path, and the Rule 0 owner of each finding:
implementation-defect or coverage-gap in code or tests, spec-gap in the owning
clause, stale-engineering-doc in `docs/engineering/`. Addressing those findings
is the other branch of this skill, from Route. Close continues the same PATH.
The round folder is the record of this review; the user-facing close-out is
this reply. This review run does not change the product tree.

`--archive DIR` is a manual keep step, not part of Close.

**Done when:** the reply quotes the run PATH; remaining list counts are taken
from this Close run; every recorded non-aligned verdict is listed with
evidence, owner, and packet path; no spec, source, or test file changed.
