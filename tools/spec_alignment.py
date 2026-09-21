#!/usr/bin/env python3
"""Assemble one review packet per spec clause through the public Source Down CLI."""
import argparse
from collections import namedtuple
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPAIR = "rebuild the snapshot with `mise run review`, then run this tool again"
UNRESOLVED = b"source-down: selection_not_found:"
CLAUSE = re.compile(r"^## (SPEC-[A-Z]+-[0-9]{3})\b.*$", re.M)
CLAUSE_ID = re.compile(r"SPEC-[A-Z]+-[0-9]{3}")
RUST_TEST = re.compile(r"\bfn (spec_[a-z0-9_]+)\s*\(")
E2E_CASE = re.compile(r"^class (\w+)\([^\n]*\n\s+specs = \(([^)]*)\)", re.M)
DELIMITER = re.compile(r"\|[\s:-]+\|")
ANCHOR = re.compile(r'^<a id="spec-([a-z]+)-([0-9]{3})">')
LEDGER = "spec-alignment-ledger.md"
PACKETS = "packets"
RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z(?:-[0-9]+)?$")
VERDICTS = ("aligned", "implementation-defect", "spec-gap", "coverage-gap", "stale-engineering-doc")
HEADER = ("# Spec alignment ledger\n\n"
          "Written by `tools/spec_alignment.py`. Do not edit by hand.\n"
          "A clause with no row has never been reviewed. See the spec alignment contract.\n\n"
          "| 条款 | verdict | reviewed | fingerprint | note |\n"
          "| --- | --- | --- | --- | --- |\n")

Record = namedtuple("Record", "clause spec span snapshot text sites tests header rows")
Site = namedtuple("Site", "call span text marked")
Test = namedtuple("Test", "kind path name line selector span text others")


class Cli:
    """Every fact in a packet comes from these commands; nothing under the output root is opened."""

    def __init__(self, binary, root):
        self.binary = binary
        self.root = root

    def execute(self, *arguments):
        command = [str(self.binary), *arguments, "--json", "--root", str(self.root)]
        return subprocess.run(command, capture_output=True)

    def decode(self, result):
        reply = json.loads(result.stdout)
        if reply.get("format_version") != 1:
            raise SystemExit(f"spec_alignment: unsupported format_version {reply.get('format_version')}")
        return reply

    def stop(self, result, arguments):
        sys.stderr.buffer.write(result.stderr)
        raise SystemExit(f"spec_alignment: {' '.join(arguments)} failed; {REPAIR}")

    def __call__(self, *arguments):
        result = self.execute(*arguments)
        if result.returncode != 0:
            self.stop(result, arguments)
        return self.decode(result)

    def attempt(self, *arguments):
        """Only the command's own not-found category is an answer about the file; anything else failed."""
        result = self.execute(*arguments)
        if result.returncode == 0:
            return self.decode(result)
        if not result.stderr.startswith(UNRESOLVED):
            self.stop(result, arguments)
        return None


def whole(cli, first, *arguments):
    """One body read completely, following the read command's own continuation offset."""
    text, offset = first["body"]["text"], first["body"]["next_offset"]
    while offset is not None:
        more = cli(*arguments, "--offset", str(offset))["body"]
        text, offset = text + more["text"], more["next_offset"]
    return text


def body(cli, handle):
    first = cli("read", handle)
    return first, whole(cli, first, "read", handle)


def clause_record(cli, clause, heading, spec):
    anchor = f'<a id="{clause.lower()}">'
    for hit in cli("search", heading, "--path", spec, "--limit", "20")["hits"]:
        if hit["kind"] == "expansion" and hit["snippet"].startswith(anchor):
            return hit["handle"]
    raise SystemExit(f"spec_alignment: {clause} has no expansion record in the snapshot; {REPAIR}")


def occurrences(cli, handle, reply):
    """Every call site of this clause, following the list's own cursor."""
    items = list(reply["occurrences"]["items"])
    cursor = reply["occurrences"]["next_cursor"]
    while cursor is not None:
        page = cli("read", handle, "--cursor", cursor)["continuation"]["page"]
        items += page["items"]
        cursor = page["next_cursor"]
    return [item for item in items if item["plugin"] == "spec" and item["call_site"]]


def fragment(cli, fragments, handle):
    """One neighbouring fragment read in full; a context item only names it, its own read describes it."""
    if handle not in fragments:
        fragments[handle] = body(cli, handle)
    return fragments[handle]


def marking(text):
    """The clause a fragment expands, recognised by the anchor a clause body opens with."""
    match = ANCHOR.match(text)
    return f"SPEC-{match[1].upper()}-{match[2]}" if match else None


def segment(cli, fragments, handle, occurrence):
    """The first following fragment the read command reports as code, and the clauses sharing it."""
    position = int(occurrence["id"].lstrip("o"))
    reply = cli("read", handle, "--occurrence", occurrence["id"], "--context", "5")
    neighbours = {int(item["occurrence"].lstrip("o")): item["handle"] for item in reply["context"]}
    others, step = [], 1
    while (near := neighbours.get(position - step)) and (clause := marking(fragment(cli, fragments, near)[1])):
        others.insert(0, clause)
        step += 1
    step = 1
    while near := neighbours.get(position + step):
        read, text = fragment(cli, fragments, near)
        if read["kind"] == "code":
            return read["sources"]["items"][0]["span"], text, others
        if clause := marking(text):
            others.append(clause)
        step += 1
    return None, None, others


def leading_clauses(name):
    """The clause numbers a Rust test name carries, e.g. spec_ren_002_cli_004_… owns two."""
    parts, found, index = name.split("_"), [], 1
    while index + 1 < len(parts) and parts[index].isalpha() and re.fullmatch("[0-9]{3}", parts[index + 1]):
        found.append(f"SPEC-{parts[index].upper()}-{parts[index + 1]}")
        index += 2
    return found


def sources(root, suffix, directory=None):
    """The project's own files of one kind; the output root and build artefacts are never entered."""
    for parent, folders, names in os.walk(root / directory if directory else root):
        folders[:] = sorted(name for name in folders if not name.startswith(".") and name != "target")
        for name in sorted(names):
            if name.endswith(suffix):
                path = Path(parent) / name
                yield path, path.read_text(encoding="utf-8")


def discover_tests(root, inventory):
    """Clause → the tests whose names the project's two conventions associate with it."""
    found = {}

    def associate(kind, path, name, start, text, owned):
        for clause in owned:
            others = [other for other in owned if other != clause]
            found.setdefault(clause, []).append(
                (kind, path.relative_to(root).as_posix(), name, text.count("\n", 0, start) + 1, others))

    for path, text in sources(root, ".rs"):
        for match in RUST_TEST.finditer(text):
            owned = [clause for clause in leading_clauses(match[1]) if clause in inventory]
            associate("Rust", path, match[1], match.start(), text, owned)
    for path, text in sources(root, ".py", "tests-e2e/cases"):
        for match in E2E_CASE.finditer(text):
            associate("E2E", path, match[1], match.start(), text, CLAUSE_ID.findall(match[2]))
    return found


def entity(cli, cache, path, selector):
    key = (path, selector)
    if key not in cache:
        first = cli.attempt("read", path, "--id", selector)
        cache[key] = None if first is None else (first["source"], whole(cli, first, "read", path, "--id", selector))
    return cache[key]


def resolve(cli, cache, entry):
    """The named test's own bytes, through the bare name first and the tests module second."""
    kind, path, name, line, others = entry
    for selector in (name, json.dumps(["tests", name])):
        read = entity(cli, cache, path, selector)
        if read is not None:
            return Test(kind, path, name, line, selector, *read, others)
    return Test(kind, path, name, line, None, None, None, others)


def tests_section(clause, tests):
    rust = sum(1 for test in tests if test.kind == "Rust")
    lines = [f"## Tests ({rust} Rust, {len(tests) - rust} E2E)", ""]
    if not tests:
        return "\n".join(lines + [f"No test name references {clause}.", ""])
    for test in tests:
        also = f" (also owns {', '.join(test.others)})" if test.others else ""
        if test.span is None:
            lines += [f"### `{test.path}:{test.line}` → `{test.name}` UNRESOLVED{also}", ""]
            continue
        lines.append(f"### `{test.path}` → `{test.name}`"
                     f" L{test.span['start_line']}-{test.span['end_line']}{also}")
        marker = fence(test.text)
        lines += ["", marker, test.text.rstrip("\n"), marker, ""]
    return "\n".join(lines)


def acceptance(spec, clause):
    """The clause's own acceptance rows, under the header of the table that holds the first one."""
    lines = spec.read_text(encoding="utf-8").splitlines()
    rows = [index for index, line in enumerate(lines) if first_cell(line) == clause]
    header = next((lines[index - 1:index + 1] for index in range(rows[0], 0, -1)
                   if DELIMITER.match(lines[index])), []) if rows else []
    return header, [lines[index] for index in rows]


def first_cell(line):
    cells = line.split("|")
    return cells[1].strip() if line.startswith("|") and len(cells) > 2 else None


def acceptance_section(clause, spec, header, rows):
    quoted = "\n".join(header + rows) if rows else f"No acceptance row names {clause} in `{spec}`."
    return (f"## Acceptance scenarios ({len(rows)} row{'' if len(rows) == 1 else 's'} in `{spec}`)"
            f"\n\n{quoted}\n")


def links(clause, text):
    """Clauses the body points at: anchor targets first, then plain-text mentions."""
    anchored = {f"SPEC-{domain.upper()}-{number}"
                for domain, number in re.findall(r"\]\([^)]*#spec-([a-z]+)-([0-9]{3})\)", text)}
    mentioned = set(re.findall(r"SPEC-[A-Z]+-[0-9]{3}", text)) - anchored - {clause}
    return ("## Linked clauses\n\n"
            f"Anchored: {', '.join(sorted(anchored)) or 'none'}\n"
            f"Mentioned: {', '.join(sorted(mentioned)) or 'none'}\n")


def fence(text):
    longest = max((len(run) for run in re.findall(r"^`+", text, re.M)), default=0)
    return "`" * max(3, longest + 1)


def code_section(sites, clause):
    lines = [f"## Code under the clause ({len(sites)} call site{'' if len(sites) == 1 else 's'})", ""]
    for site in sites:
        if site.span is None:
            lines += [f"### `{site.call}` → no code under marker", ""]
            continue
        size = site.span["end_byte"] - site.span["start_byte"]
        lines.append(f"### `{site.call}` → L{site.span['start_line']}-{site.span['end_line']} ({size} B)")
        others = [other for other in site.marked if other != clause]
        if others:
            lines.append(f"\nAlso marked by: {', '.join(others)}")
        marker = fence(site.text)
        lines += ["", marker, site.text.rstrip("\n"), marker, ""]
    return "\n".join(lines)


def fingerprint(record):
    """SHA-256 over the reviewed content bytes alone: no line or byte offsets, no packet framing."""
    digest = hashlib.sha256()

    def item(*fields, content=b""):
        digest.update("\n".join(fields).encode("utf-8") + f"\n{len(content)}\n".encode("ascii") + content)

    item("clause", record.clause, content=record.text.encode("utf-8"))
    coded = [site for site in record.sites if site.span is not None]
    for site in sorted(coded, key=lambda site: (site.span["path"], site.span["start_byte"])):
        item("site", site.span["path"], content=site.text.encode("utf-8"))
    for test in sorted((test for test in record.tests if test.span), key=lambda test: (test.path, test.selector)):
        item("test", test.path, test.selector, content=test.text.encode("utf-8"))
    for test in sorted((test for test in record.tests if not test.span), key=lambda test: (test.path, test.name)):
        item("unresolved", test.path, test.name)
    for row in record.rows:
        item("row", content=row.encode("utf-8"))
    return digest.hexdigest()


def packet(record, digest):
    span = record.span
    return (f"# {record.clause} review packet\n\n"
            f"- Fingerprint: `{digest}`\n"
            f"- Clause source: `{span['path']}` L{span['start_line']}-{span['end_line']}"
            f" (bytes {span['start_byte']}-{span['end_byte']})\n"
            f"- Snapshot: `{record.snapshot}`  ·  Rebuild: `mise run alignment`\n\n"
            f"## Clause\n\n{record.text.rstrip(chr(10))}\n\n"
            f"{links(record.clause, record.text)}\n"
            f"{code_section(record.sites, record.clause)}\n"
            f"{tests_section(record.clause, record.tests)}\n"
            f"{acceptance_section(record.clause, record.spec, record.header, record.rows)}")


def clauses(root):
    """Every clause heading the project defines, in specification file order."""
    for path in sorted((root / "docs/specs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in CLAUSE.finditer(text):
            yield path, match[1], match[0][3:]


def collect(cli, root, only=None):
    headings = list(clauses(root))
    found = discover_tests(root, {clause for _, clause, _ in headings})
    fragments, entities = {}, {}
    for path, clause, heading in headings:
        if only is not None and clause != only:
            continue
        spec = path.relative_to(root).as_posix()
        handle = clause_record(cli, clause, heading, spec)
        reply, text = body(cli, handle)
        sites = []
        for occurrence in occurrences(cli, handle, reply):
            site = occurrence["call_site"]
            sites.append(Site(f"{site['path']}:{site['start_line']}",
                              *segment(cli, fragments, handle, occurrence)))
        tests = [resolve(cli, entities, entry) for entry in sorted(found.get(clause, []), key=lambda entry: entry[1:3])]
        yield Record(clause, spec, reply["sources"]["items"][0]["span"], reply["snapshot"],
                     text, sites, tests, *acceptance(path, clause))


def build(cli, root, output, only=None):
    """Each covered clause's packet and fingerprint, plus the test names no selector reached."""
    digests, unresolved = {}, []
    output.mkdir(parents=True, exist_ok=True)
    for record in collect(cli, root, only):
        digests[record.clause] = fingerprint(record)
        (output / f"{record.clause}.md").write_text(packet(record, digests[record.clause]),
                                                    encoding="utf-8", newline="")
        unresolved += [f"{test.path}:{test.line} {test.name}" for test in record.tests if test.span is None]
    return digests, sorted(set(unresolved))


def ledger_rows(ledger):
    """The recorded verdicts, read back from the one table this tool writes."""
    found = {}
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if len(cells) == 5 and CLAUSE_ID.fullmatch(cells[0]):
                found[cells[0]] = cells[1:]
    return found


def write_ledger(ledger, recorded):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(HEADER + "".join(f"| {clause} | {' | '.join(recorded[clause])} |\n"
                                       for clause in sorted(recorded)), encoding="utf-8", newline="\n")


def project_key(root):
    digest = hashlib.sha256(os.fsencode(str(root))).hexdigest()[:8]
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", root.name).strip("-.") or "project"
    return f"{name}-{digest}"


def cache_parent(root):
    home = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    return (home / "source-down" / "alignment" / project_key(root)).resolve()


def is_run(path):
    return path.is_dir() and RUN_ID.fullmatch(path.name)


def previous_run(parent, current=None):
    if not parent.is_dir():
        return None
    runs = sorted(path for path in parent.iterdir() if is_run(path) and path != current)
    return runs[-1] if runs else None


def new_run(parent):
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path, extra = parent / stamp, 2
    while path.exists():
        path = parent / f"{stamp}-{extra}"
        extra += 1
    path.mkdir()
    return path


def announce(run):
    print(f"spec_alignment: run {run}")


def select_run(args, root, *, open_new, mkdir_pinned, require_existing):
    if args.run is not None:
        run = args.run.resolve()
        if mkdir_pinned:
            run.mkdir(parents=True, exist_ok=True)
            return run
        if not run.is_dir():
            raise SystemExit(f"spec_alignment: run {run} does not exist")
        return run
    parent = cache_parent(root)
    if open_new:
        return new_run(parent)
    prior = previous_run(parent)
    if prior is not None:
        return prior
    if require_existing:
        raise SystemExit("spec_alignment: no alignment run")
    return new_run(parent)


def archive_run(run, destination):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / run.name
    if target.exists():
        raise SystemExit(f"spec_alignment: archive {target} already exists")
    shutil.copytree(run, target)
    print(f"spec_alignment: archived {target}")


def report(digests, recorded):
    """The three lists a reviewer acts on; any of them non-empty means review work is outstanding."""
    return {"Stale (reviewed at another fingerprint)":
            [f"{clause} {recorded[clause][2]} -> {digest}" for clause, digest in digests.items()
             if clause in recorded and recorded[clause][2] != digest],
            "Unreviewed (no ledger row)": [clause for clause in digests if clause not in recorded],
            "Orphan (ledger row without a clause)": [clause for clause in recorded if clause not in digests]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    executable = "source-down.exe" if os.name == "nt" else "source-down"
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release" / executable)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--new-run", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--record", metavar="CLAUSE")
    parser.add_argument("--verdict", choices=VERDICTS)
    parser.add_argument("--note", default="")
    parser.add_argument("--forget", metavar="CLAUSE")
    args = parser.parse_args()
    if args.forget and (args.record or args.verdict or args.note or args.archive or args.new_run):
        parser.error("--forget only drops a row; it takes no --record, --verdict, --note, --archive or --new-run")
    if args.archive and (args.record or args.verdict or args.note or args.new_run):
        parser.error("--archive copies a run; it takes no --record, --verdict, --note or --new-run")
    if args.new_run and (args.record or args.verdict or args.note or args.run):
        parser.error("--new-run starts a round; it takes no --record, --verdict, --note or --run")
    if bool(args.record) != bool(args.verdict):
        parser.error("--record and --verdict go together")
    if "|" in args.note or "\n" in args.note:
        parser.error("--note takes one line without '|'")
    root = args.root.resolve()
    if args.archive:
        run = select_run(args, root, open_new=False, mkdir_pinned=False, require_existing=True)
        announce(run)
        return archive_run(run, args.archive.resolve())
    if args.forget:
        run = select_run(args, root, open_new=False, mkdir_pinned=False, require_existing=True)
        announce(run)
        ledger = run / LEDGER
        recorded = ledger_rows(ledger)
        if args.forget not in recorded:
            raise SystemExit(f"spec_alignment: {args.forget} has no ledger row")
        del recorded[args.forget]
        return write_ledger(ledger, recorded)
    run = select_run(args, root, open_new=args.new_run, mkdir_pinned=True,
                     require_existing=bool(args.record))
    announce(run)
    cli = Cli(args.binary, root)
    digests, unresolved = build(cli, root, run / PACKETS, args.record)
    for item in unresolved:
        print(f"spec_alignment: unresolved test selector {item}", file=sys.stderr)
    ledger = run / LEDGER
    if args.record:
        if args.record not in digests:
            raise SystemExit(f"spec_alignment: {args.record} is not defined under docs/specs")
        recorded = ledger_rows(ledger)
        recorded[args.record] = [args.verdict, datetime.date.today().isoformat(),
                                 digests[args.record], args.note]
        return write_ledger(ledger, recorded)
    outstanding = [line for title, listed in report(digests, ledger_rows(ledger)).items() if listed
                   for line in [f"{title}:", *(f"  {entry}" for entry in listed)]]
    print("\n".join(outstanding) if outstanding
          else f"spec_alignment: {len(digests)} clauses reviewed and current")
    if outstanding or unresolved:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
