#!/usr/bin/env python3
"""Validate documentation links, normative IDs, anchors, and AGD independence."""
from pathlib import Path
import os
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def outside_fences(text):
    marker = None
    for line in text.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if match:
            run = match[1]
            if marker is None:
                marker = run
            elif run[0] == marker[0] and len(run) >= len(marker) and not line[match.end():].strip():
                marker = None
            yield ""
        elif marker is None:
            yield line


def check():
    errors = []
    definitions = {}
    files = [ROOT / name for name in ("README.md", "AGENTS.md", "CLAUDE.md")]
    files += list((ROOT / "docs").rglob("*.md"))
    files += list((ROOT / ".agents").rglob("*.md"))
    files += list((ROOT / "tools").glob("*.md"))
    for path in files:
        text = path.read_text()
        if path.is_relative_to(ROOT / ".agents/decisions"):
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"\bSPEC-[A-Z]+-[0-9]+\b", line, re.I):
                    errors.append(
                        f"{path.relative_to(ROOT).as_posix()}:{number}: AGD must not reference SPEC clause IDs")
        for clause in re.findall(r"^## (SPEC-[A-Z]+-[0-9]{3})\b", text, re.M):
            if clause in definitions:
                errors.append(f"duplicate definition {clause}: {path}")
            definitions[clause] = path
            if text.count(f'<a id="{clause.lower()}"></a>') != 1:
                errors.append(f"{path}: {clause} needs exactly one explicit anchor")
        for line in outside_fences(text):
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
                target = target.strip().strip("<>")
                if "{%" in target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                filename, _, anchor = target.partition("#")
                linked = (path.parent / unquote(filename)).resolve() if filename else path
                if not linked.exists():
                    errors.append(f"{path.relative_to(ROOT).as_posix()}: broken local link {target}")
                elif anchor.startswith("spec-") and f'id="{anchor}"' not in linked.read_text():
                    errors.append(f"{path.relative_to(ROOT).as_posix()}: missing anchor {target}")

    for path in files:
        if path.is_relative_to(ROOT / "docs/specs"):
            for clause in set(re.findall(r"SPEC-[A-Z]+-[0-9]{3}", path.read_text())):
                if clause not in definitions:
                    errors.append(f"{path.relative_to(ROOT).as_posix()}: undefined {clause}")
    if errors:
        raise SystemExit("\n".join(errors))
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT))
    subprocess.run([sys.executable, str(ROOT / ".agents/scripts/validate-agds.py")], cwd=ROOT, env=environment, check=True)
    print(f"documentation: PASS ({len(files)} documents, {len(definitions)} unique normative clauses)")


if __name__ == "__main__":
    check()
