# Per-clause spec alignment review

This engineering contract governs `tools/spec_alignment.py`, the review packets it
writes and the alignment ledger it maintains. Product behavior remains owned by
[the specifications](../specs/README.md); reference coverage is already mechanical and
checked by the project spec plugin, while semantic alignment between a clause and its
implementation is judged by review. This contract adds no product command and no
product-format requirement.

The tool's agreed public boundary is its command line, its exit status, and the
run directory it writes (ledger and packets together). Its own tests live in
`tests/spec_alignment_test.py`, next to the other development-tool tests described by
the [readable E2E contract](e2e.md).

## Portable test observations

The tests follow the [cross-platform work rules](../../AGENTS.md#work). Regression
cases launch the real tool with CRLF stdout and stderr, and with a cache parent
reached through a directory symlink. Source fixtures, packets and ledger
preservation checks retain their original byte assertions.

## Public API only

The tool reaches Source Down exclusively through the published command line:
`source-down search ... --json`, `source-down read <handle> --json` with its
`--occurrence`, `--context` and `--cursor` options, and `source-down read <file>
--id <selector> --json`. It opens no file under the product output root
`.source-down/`, neither the search index nor pages nor reports. Files under that
output root are implementation detail even where their format is specified; every
user of Source Down is encouraged to treat them the same way. Alignment writes go
to a run directory the tool owns, not into the product output root.

The tool never passes `--snapshot`, and queries the snapshot the CLI keeps under the
default output root, as `mise run review` publishes it; a project rendered elsewhere
with the product's `--output-dir` option is outside this contract, and so is the repair
command the tool prints. Each `search` and handle `read` performs the CLI's own
current-fact check, so snapshot currency has exactly one owner. On the first non-zero
exit the tool stops, prints the CLI's own message and the repair command, and exits 1 —
the one exception is the selector category named under *Test association* below. A
reply whose `format_version` is not 1 also stops the run with exit 1, naming the
version it saw and no repair command: rebuilding the snapshot does not change the
format the CLI speaks, and the tool has to be taught the new one.

The tool also re-implements nothing the product already owns. Source segmentation,
entity boundaries and call-site recognition are read back from the CLI, never
recomputed by brace matching or regular expressions over source text. Scanning the
project's own specification and test files for *names* is allowed, because those files
are not internal to the product.

## What "code under a clause" means

A call site is one `{% spec %}` marker comment. The code under it is the first
following fragment on the same generated page whose own read reports `kind: "code"`.
The tool asks for the neighbouring fragments with `--context 5`, because consecutive
markers put another expansion between a marker and its code, and reads the following
ones in page order until one is code. Page order is occurrence-ID order: per
[SPEC-SRH-002](../specs/search.md#spec-srh-002) the snapshot assigns occurrence IDs
after sorting occurrences by output path and in-page position, so the tool compares the
numbers the CLI returns instead of ordering the neighbours itself. A call site with no
code fragment within that window is recorded in the packet as having no code under the
marker.

Adjacent markers share one segment. The packet names every clause that marks a shared
segment, so a marker placed above code it does not own is visible to the reviewer. A
context item only names a neighbouring fragment; what that fragment is — code, or the
expansion of another clause — comes from reading the fragment itself, because one read
spends its fixed budget on the main body first and hands a large clause's context items
no text at all.
The convention that a marker sits immediately above the behavior it references is
recorded in
[AGD-007](../../.agents/decisions/AGD-007_check-spec-references-through-a-project-plugin.md).

## Test association

Tests are discovered by the two naming conventions the project already uses: Rust
functions named `spec_<domain>_<nnn>...`, where one name may carry two clause numbers,
and the `specs` tuple declared by the single case class of an E2E scenario file
(see the [readable E2E contract](e2e.md)). The tool scans the project's own `.rs` files
for the first convention and `tests-e2e/cases` for the second, reading names only; it
enters neither the output root nor `target/`. A packet names the other clause a
two-clause name also owns. Bodies come from
`source-down read <file> --id <name> --json`, continuing on `next_offset`, and each
`(file, selector)` pair is read once per run.

Selectors resolve in order: the bare name, then the JSON structural path
`["tests", <name>]` for a Rust unit test inside a `#[cfg(test)] mod tests`. Only the
CLI's own `selection_not_found` category means "this file does not define that name":
the tool then tries the next selector, and a read failing with any other category stops
the run like every other failed call, so a crash or an I/O error never becomes a fact
about the file. A name that resolves neither way is listed in the packet as unresolved
with its file and line, named on standard error, and a default run reporting one
exits 1. The
fingerprint covers the unresolved name, so a verdict recorded over it is still exact.
Discovery is never a verdict: a clause with no
name-matched test is stated as an absence, not labelled a coverage gap.

## Acceptance rows

A clause's acceptance scenarios are the table rows in the clause's own specification
file whose first cell, trimmed, equals the clause ID exactly, quoted under the header
of the table that holds the first of them. A clause with no such row is stated as an
absence.

## Fingerprint

The fingerprint is SHA-256 over a length-prefixed byte stream of content bytes only:
the clause bytes, each code segment sorted by path and start byte, each test entity
sorted by path and selector, each unresolved test name, and each acceptance row in
file order. Paths take part, because moving a call site is a real change. Line and
byte offsets and the packet's own framing do not, so unrelated code shifting above a
segment does not invalidate a review. It is computed only by `tools/spec_alignment.py`
and published in both the packet header and the ledger.

## Run directory

A run is one complete review round: one folder holding that round's ledger and
packets. The first stdout line is always `spec_alignment: run PATH`. Packets are
`PATH/packets/<CLAUSE>.md`; the ledger is `PATH/spec-alignment-ledger.md`.

The default parent is `$XDG_CACHE_HOME/source-down/alignment/<project>/`, or
`~/.cache/source-down/alignment/<project>/` when `XDG_CACHE_HOME` is unset. The
project segment is the root directory name plus a short hash of its resolved
path, so two checkouts do not share runs. That location is outside the project
by default: alignment artefacts are scratch, not repository files.

`--new-run` starts a round: a new folder and an empty ledger. A default
invocation with no `--new-run` continues the latest round for that project,
rebuilding packets in that folder against its ledger; if there is no round yet,
it starts one. `--run DIR` pins a folder. `--record` and `--forget` edit the
latest round, or the folder given by `--run`. Combining `--new-run` with
`--record`, `--verdict`, `--note` or `--run` is refused with the usage message
and exit 2. `--archive DIR` copies a finished round to `DIR/<run-id>/` and is
the only keep step; combining it with `--record`, `--verdict`, `--note`,
`--forget` or `--new-run` is refused the same way. A destination that already
exists is refused. Naming `--record` or `--forget` with no round yet exits 1.

## Ledger

The ledger in a run holds one row per reviewed clause, sorted by clause ID,
rewritten whole by the tool. Columns are the clause ID, the verdict, the review
date, the fingerprint and a one-line note. The verdicts are `aligned`,
`implementation-defect`, `spec-gap`, `coverage-gap` and `stale-engineering-doc`,
matching the finding kinds of
[AGD-001](../../.agents/decisions/AGD-001_adopt-rule-0-spec-first-development.md); any
other value is refused with the usage message and exit 2. A clause with no row has
never been reviewed; there is no value for that. A row whose clause is no longer
defined is reported as an orphan and retired with `--forget`, once the reviewer has
established from `docs/specs/` whether the clause was deleted or renumbered.

A note is one table cell: a note containing `|` or a line break is refused the same
way rather than escaped, so what the reviewer typed is what the table shows. The
review date is the local date of the recording run, so recording the same verdict and
note again on the same day leaves the file byte-identical.

The ledger has one writer, this tool: `--record` adds or replaces a row, `--forget`
removes one, and both rewrite the whole file through the same parser. Its banner says
so, and no row is ever edited by hand. Reviewing agents return verdicts; the
coordinating agent records them serially.

## Commands

```sh
python tools/spec_alignment.py [--binary PATH] [--root DIR] [--run DIR]
python tools/spec_alignment.py --new-run
python tools/spec_alignment.py --record SPEC-CLI-004 --verdict aligned --note "one line"
python tools/spec_alignment.py --forget SPEC-CLI-004
python tools/spec_alignment.py --archive DIR
mise run alignment
mise run alignment -- --new-run
```

The default run discovers every clause heading under `docs/specs/`, rebuilds
every packet in the current round and prints three lists: clauses whose
fingerprint differs from the one recorded (stale, with both fingerprints),
clauses with no row (unreviewed) and rows with no clause (orphan). It exits 1
when any list has an entry or a test selector went unresolved, and 0 otherwise.
`--new-run` does the same in a new folder with an empty ledger.
`--record` rebuilds that one clause's packet in the selected run, takes its
fingerprint as of now, rewrites that run's ledger and exits 0. `--forget` drops
that clause's row and does nothing else: it calls no command, builds no packet
and needs no snapshot. Combining it with `--record`, `--verdict`, `--note` or
`--archive` is refused with the usage message and exit 2; naming a clause the
ledger holds no row for exits 1 and leaves the file byte-identical. `--binary`
defaults to the release CLI and `--root` to the working directory. `mise run
alignment` renders the project first, so the snapshot is current by construction;
`mise run check` does not run it, because a clause written today is legitimately
unreviewed.

## Not in the coverage denominator

`tools/spec_alignment.py` is a development helper, outside the three production scopes
enumerated by the [coverage guide](coverage.md) and
[AGD-008](../../.agents/decisions/AGD-008_enforce-ninety-percent-test-coverage.md).
Its own boundary tests still run with the rest of the Python suite.
