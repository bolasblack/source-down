#!/usr/bin/env python3
"""Discover and run readable E2E scenarios against explicitly identified artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import os
from pathlib import Path
import shutil
import sys
import traceback
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def source_hashes(run):
    return {path.relative_to(run).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in (run / "tests-e2e", run / "docs")
            for path in sorted(folder.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}


def discover(run, selector):
    loader = unittest.TestLoader()
    tests = list(flatten(loader.discover(str(run / "tests-e2e/cases"), pattern="test_*.py",
                                        top_level_dir=str(run / "tests-e2e"))))
    cases, errors = [], list(loader.errors)
    for test in tests:
        file = Path(inspect.getfile(type(test)))
        if file.is_relative_to(run):
            source = file.relative_to(run).as_posix()
        else:
            # Unittest represents an import failure as a synthetic error case.
            source = "tests-e2e/" + test.id().removeprefix("unittest.loader._FailedTest.").replace(".", "/") + ".py"
            if not (run / source).is_file():
                errors.append(f"test source is outside the preserved cases: {test.id()}")
        name = source.removeprefix("tests-e2e/cases/")
        selected = selector is None or name == selector or name.startswith(selector.rstrip("/") + "/")
        platforms = getattr(test, "platforms", (sys.platform,))
        applicable = sys.platform in platforms
        if not applicable:
            unittest.skip(f"not applicable on {sys.platform}; requires {', '.join(platforms)}")(type(test))
        cases.append({"id": test.id(), "title": test.shortDescription() or test.id(),
                      "source": source, "specs": list(getattr(test, "specs", ())),
                      "applicable": applicable, "platforms": list(platforms),
                      "selected": selected, "status": "not_run", "started_at": None, "ended_at": None})
    if not tests:
        errors.append("no scenarios discovered")
    expected = {path.relative_to(run).as_posix() for path in (run / "tests-e2e/cases").rglob("test_*.py")}
    errors.extend(f"scenario file not discovered: {name}" for name in sorted(expected - {case["source"] for case in cases}))
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scenario identity in discovery")
    if selector is not None and not any(case["selected"] for case in cases):
        errors.append(f"case selection matched no scenarios: {selector}")
    return tests, cases, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    executable = "source-down.exe" if os.name == "nt" else "source-down"
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release" / executable)
    parser.add_argument("--spec-plugin", type=Path)
    parser.add_argument("--case", help="exact scenario file or workflow directory under cases")
    parser.add_argument("--review", action="store_true", help="render this run's scenarios and results")
    parser.add_argument("--list", action="store_true", help="discover without executing scenarios")
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    run = ROOT / ".source-down/e2e/runs" / run_id
    run.mkdir(parents=True)
    for name in ("tests-e2e", "docs/specs"):
        shutil.copytree(ROOT / name, run / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    queries = ROOT / "docs/engineering/search-queries.json"
    if queries.exists():
        (run / "docs/engineering").mkdir()
        shutil.copy2(queries, run / "docs/engineering/search-queries.json")
    (run / "source-down.toml").write_text("config_version = 1\n", encoding="utf-8")
    preserved = source_hashes(run)
    sys.path.insert(0, str(run / "tests-e2e"))
    from support.case import E2ECase, RunContext, identity
    from support.result import Result, now
    from support.reading import publish, save
    plugin_name = "spec-plugin.exe" if args.binary.suffix.lower() == ".exe" else "spec-plugin"
    context = E2ECase.context = RunContext(ROOT, run, args.binary, args.spec_plugin or args.binary.parent / "examples" / plugin_name)
    scope = "listing" if args.list else "partial" if args.case is not None else "complete"
    report = {"run_id": run_id, "scope": scope, "selection": args.case, "full_pass": False,
              "cases": [], "source_sha256": preserved, "errors": [], "interrupted": False,
              "workspace": str(ROOT), "platform": sys.platform, "started_at": context.started_at,
              "commands": context.commands, "mutations": context.mutations,
              "coverage_environment": {name: os.environ[name] for name in
                                        ("LLVM_PROFILE_FILE", "SD_COVERAGE_ROOT", "SD_COVERAGE_DATA") if name in os.environ}}
    result = None
    try:
        report["git"] = {"available": False, "head": None, "dirty": None}
        try:
            head = context.command(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10)
            status = context.command(["git", "status", "--porcelain=v1", "-z"], cwd=ROOT, timeout=10)
            if head.returncode == status.returncode == 0:
                report["git"].update(available=True, head=head.stdout.decode("ascii").strip(), dirty=bool(status.stdout))
        except OSError as error:
            report["git"]["error"] = str(error)
        for label, path in (("binary", context.binary), ("spec_plugin", context.spec_plugin)):
            try:
                report[label] = identity(path)
            except OSError as error:
                report[label] = {"path": str(path), "sha256": None, "error": str(error)}
                if not args.list:
                    report["errors"].append(str(error))
        tests, report["cases"], errors = discover(run, args.case)
        report["errors"].extend(errors)
        # An unambiguous discovered collection owns execution; errors retain its inventory.
        if not args.list and not report["errors"]:
            result = Result(report["cases"], run, context)
            unittest.TestSuite(test for test, case in zip(tests, report["cases"]) if case["selected"]).run(result)
    except KeyboardInterrupt:
        report["interrupted"] = True
        report["errors"].append("execution interrupted")
        if result and result.current_test:
            result.problem(result.current_test, sys.exc_info(), "error")
    except Exception:
        report["errors"].append(traceback.format_exc())
    finally:
        context.resources.close()
    if result:
        report["suite_events"] = result.events
        for event in result.events:
            if event["status"] == "error":
                report["errors"].append((run / event["log"]).read_text(encoding="utf-8"))
    unchanged = source_hashes(run) == report["source_sha256"]
    if not unchanged:
        report["errors"].append("preserved inputs changed during execution")
    selected = [case for case in report["cases"] if case["selected"]]
    applicable = [case for case in selected if case["applicable"]]
    passed = (not report["errors"] and not args.list and bool(applicable)
              and all(case["status"] == "passed" for case in applicable)
              and all(case["status"] == "skipped" for case in selected if not case["applicable"]))
    report["tests_status"] = ("error" if report["errors"] or any(case["status"] == "error" for case in selected)
                              else "not_run" if args.list else "passed" if passed
                              else "failed" if any(case["status"] == "failed" for case in selected) else "incomplete")
    report["full_pass"] = scope == "complete" and passed and not args.review
    report["ended_at"] = now()
    report["documentation"] = {"status": "pending" if args.review else "not_requested"}
    save(report, run)
    if args.review:
        try:
            if not unchanged or report["interrupted"]:
                raise RuntimeError("reading requires unchanged executed inputs and an uninterrupted coordinator")
            report["documentation"] = publish(context, report)
            if source_hashes(run) != report["source_sha256"]:
                raise RuntimeError("preserved inputs changed during reading")
            report["full_pass"] = scope == "complete" and passed
        except (Exception, KeyboardInterrupt) as error:
            if isinstance(error, KeyboardInterrupt):
                report["interrupted"] = True
            report["documentation"] = {"status": "failed", "error": str(error) or "reading interrupted"}
            report["full_pass"] = False
        report["ended_at"] = now()
        save(report, run)
    for case in report["cases"]:
        print(f"{case['source'].removeprefix('tests-e2e/cases/')} :: {case['title']} [{case['status']}]")
    print(f"E2E results: {run / 'results.json'}", flush=True)
    entry = run / ("reading/pages/index.md.md" if report["documentation"]["status"] == "passed" else "results.md")
    print(f"E2E reading: {entry}", flush=True)
    if report["interrupted"]:
        return 130
    return 0 if ((args.list and selected and not report["errors"]) or passed) and report["documentation"]["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
