"""Run Rust and Python tests, generate reports, and enforce AGD-008 line coverage gates."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MINIMUM = 90


def line_counts(summary, total_key, covered_key):
    total, covered = summary[total_key], summary[covered_key]
    if type(total) is not int or type(covered) is not int or not 0 <= covered <= total:
        raise ValueError("invalid line counts")
    return total, covered


def declarations_only(path):
    # LLVM emits no regions for a module list. Adding executable code must
    # automatically make this file required in the measured report.
    code = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("//"))
    return re.fullmatch(r"(?:\s*(?:pub\s+)?mod\s+\w+;)*\s*", code) is not None


def check_reports(output):
    rust = json.loads((output / "rust.json").read_text())
    python = json.loads((output / "python.json").read_text())
    measured = {}
    for unit in rust["data"]:
        for file in unit["files"]:
            path = Path(file["filename"])
            path = (ROOT / path).resolve()
            if path in measured:
                raise ValueError(f"duplicate Rust coverage file: {path}")
            measured[path] = line_counts(file["summary"]["lines"], "count", "covered")

    groups = {}
    declarations = []
    for name, paths in (("Rust core", sorted((ROOT / "src").rglob("*.rs"))),
                        ("Rust spec plugin", [ROOT / "tools/spec_plugin.rs"])):
        files = {}
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            if path not in measured or measured[path][0] == 0:
                if declarations_only(path):
                    declarations.append(relative)
                    continue
                raise ValueError(f"missing measurable production coverage: {relative}")
            total, covered = measured[path]
            files[relative] = {"total": total, "covered": covered}
        groups[name] = files

    summary = python["files"]["tools/project_docs.py"]["summary"]
    if summary["excluded_lines"] != 0:
        raise ValueError("Python project plugin: executable lines must not be excluded")
    total, covered = line_counts(summary, "num_statements", "covered_lines")
    groups["Python project plugin"] = {"tools/project_docs.py": {"total": total, "covered": covered}}

    report = {"minimum_percent": MINIMUM, "declarations_only": declarations, "groups": {}}
    failures = []
    for name, files in groups.items():
        total = sum(file["total"] for file in files.values())
        covered = sum(file["covered"] for file in files.values())
        passed = total > 0 and covered * 100 >= total * MINIMUM
        percent = covered * 100 / total if total else 0
        report["groups"][name] = {"total": total, "covered": covered, "percent": percent,
                                   "passed": passed, "files": files}
        message = f"{name}: {covered}/{total} lines = {percent:.2f}% (minimum {MINIMUM}%)"
        print(message, flush=True)
        if not passed:
            failures.append(message)
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    if failures:
        raise ValueError("coverage gate failed:\n" + "\n".join(failures))


def run(command, env, capture=False):
    print("+ " + shlex.join(map(str, command)), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None)


def measure(output):
    env = dict(os.environ, CARGO_TARGET_DIR=str(ROOT / "target/coverage"))
    settings = run(["cargo", "llvm-cov", "show-env"], env, capture=True).stdout
    for line in settings.splitlines():
        assignment, = shlex.split(line)
        key, value = assignment.split("=", 1)
        env[key] = value

    # The profile directory and instrumented Cargo cache have one owner. Clean
    # the current workspace's profiles before building, retaining dependency caches.
    run(["cargo", "llvm-cov", "clean", "--workspace"], env)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    env.update(SD_COVERAGE_ROOT=str(ROOT), SD_COVERAGE_DATA=str(output / "python"))
    run(["cargo", "build", "--locked", "--bins", "--examples"], env)
    run(["cargo", "test", "--locked"], env)

    python = ROOT / ".source-down/coverage-env/bin/python"
    coverage = [str(python), "-m", "coverage"]
    config = f"--rcfile={ROOT / 'tools/coverage.toml'}"
    run(coverage + ["run", config, "-m", "unittest", "discover", "-s", "tests", "-p", "*_test.py"], env)
    run(coverage + ["combine", config], env)
    run(coverage + ["json", config, "-o", str(output / "python.json")], env)
    run(coverage + ["html", config, "-d", str(output / "python-html")], env)
    rust = ["cargo", "llvm-cov", "report", "--ignore-filename-regex", "/(tests|examples)/"]
    run(rust + ["--json", "--output-path", str(output / "rust.json")], env)
    run(rust + ["--html", "--output-dir", str(output / "rust")], env)
    check_reports(output)
    print(f"Coverage reports: {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", type=Path, metavar="REPORT_DIRECTORY",
                        help="check existing rust.json and python.json without collecting samples")
    arguments = parser.parse_args()
    try:
        if arguments.check_only is not None:
            check_reports(arguments.check_only)
        else:
            import fcntl

            state = ROOT / ".source-down"
            state.mkdir(exist_ok=True)
            with (state / "coverage.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                measure(state / "coverage")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"coverage: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
