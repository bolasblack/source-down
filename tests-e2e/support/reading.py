"""Project observed results and the executed source copy into one reading set."""
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit
from check_docs import outside_fences


def link(base, target, anchor=""):
    return quote(Path(os.path.relpath(target, base)).as_posix(), safe="/.-_") + anchor


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def fenced(text):
    size = max([2, *(len(match[0]) for match in re.finditer(r"`+", text))]) + 1
    fence = "`" * size
    return f"{fence}text\n{text}\n{fence}\n"


def markdown(report, run, *, reading):
    base = run / "reading/pages" if reading else run
    lines = ["# E2E acceptance\n", f"Run: `{report['run_id']}`.\n",
             f"Execution scope: **{report['scope']}**. Tests: **{report['tests_status']}**.\n"]
    if reading:
        lines.append(f"Documentation status, program identities and logs: [results]({link(base, run / 'results.md')}) · [JSON]({link(base, run / 'results.json')}).\n")
    else:
        lines.append(f"Documentation: {report['documentation']['status']}\n")
        if report["documentation"].get("error"):
            lines.append(fenced(report["documentation"]["error"]))
        for label in ("binary", "spec_plugin"):
            if label in report:
                lines.append(f"{label}: `{report[label]['path']}`; SHA-256 `{report[label]['sha256']}`.\n")
    for error in report["errors"]:
        lines.append(fenced(error))
    clauses = {match[1]: path for path in (run / "docs/specs").glob("*.md")
               for match in re.finditer(r"^## (SPEC-[A-Z]+-[0-9]{3})\b", path.read_text(encoding="utf-8"), re.M)}
    groups = sorted({case["source"].removeprefix("tests-e2e/cases/").split("/")[0] for case in report["cases"]})
    for group in groups:
        lines.extend([f"## {cell(group)}\n", "| Scenario | Status | Reading / source | Owning clauses |",
                      "| --- | --- | --- | --- |"])
        for case in report["cases"]:
            if case["source"].removeprefix("tests-e2e/cases/").split("/")[0] != group:
                continue
            target = run / case["source"]
            links = f"[saved source]({link(base, target)})" if target.is_file() else "unavailable source"
            if reading and target.is_file():
                links = f"[scenario]({link(base, run / 'reading/pages' / (case['source'] + '.md'))}) · " + links
            owners = " · ".join(f"[{owner}]({link(base, clauses[owner], '#' + owner.lower())})"
                                if owner in clauses else cell(owner) for owner in case["specs"])
            reason = f" ({cell(case['reason'])})" if case.get("reason") else ""
            lines.append(f"| {cell(case['title'])} | {case['status']}{reason} | {links} | {owners} |")
        lines.append("")
    for case in report["cases"]:
        lines.extend([f"## {cell(case['title'])}\n", f"`{case['id']}` — **{case['status']}**.\n"])
        for part in case.get("subtests", []):
            lines.append(f"- `{cell(part['id'])}`: **{part['status']}**" + (f" ({cell(part['reason'])})" if part.get("reason") else ""))
        lines.append("")
        if case.get("log"):
            lines.append(f"[Failure log]({link(base, run / case['log'])})\n")
            lines.append(fenced((run / case["log"]).read_text(encoding="utf-8")))
        for command in report.get("commands", []):
            if command["case_id"] == case["id"]:
                lines.append(fenced(json.dumps(command["argv"], ensure_ascii=False)))
                lines.append(f"Exit: `{command['exit_code']}`; [stdout bytes]({link(base, run / command['stdout'])}), [stderr bytes]({link(base, run / command['stderr'])}).\n")
    return "\n".join(lines)


def save(report, run):
    (run / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run / "results.md").write_text(markdown(report, run, reading=False), encoding="utf-8")
    (run / "index.md").write_text(markdown(report, run, reading=True), encoding="utf-8")


def publish(context, report):
    run = context.run
    sources = sorted({case["source"] for case in report["cases"] if (run / case["source"]).is_file()})
    selected = ["index.md", *sources]
    result = context.command([context.binary, "render", *selected, "--root", run, "--output-dir", "reading"], cwd=run)
    if result.returncode != 0 or result.stdout:
        raise RuntimeError(f"reading render exited {result.returncode}: {result.stderr.decode('utf-8', errors='replace')}")
    expected = {run / "reading/pages" / (source + ".md") for source in selected}
    actual = set((run / "reading/pages").rglob("*.md"))
    if actual != expected:
        raise ValueError(f"reading page set differs: missing={expected - actual}, extra={actual - expected}")
    for page in sorted(expected):
        for line in outside_fences(page.read_text(encoding="utf-8")):
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                linked = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
                if not linked.is_relative_to(run) or not linked.is_file():
                    raise ValueError(f"reading link does not reach this run: {page}: {target}")
                if linked.is_relative_to(run / "reading/pages") and linked not in expected:
                    raise ValueError(f"reading link is outside the current output set: {target}")
                if parsed.fragment.startswith("spec-") and f'id="{parsed.fragment}"' not in linked.read_text(encoding="utf-8"):
                    raise ValueError(f"missing clause anchor: {target}")
    return {"status": "passed", "entry": "reading/pages/index.md.md",
            "pages": [path.relative_to(run).as_posix() for path in sorted(expected)]}
