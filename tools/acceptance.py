#!/usr/bin/env python3
"""Discover and run readable E2E scenarios against explicitly identified artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
import unittest
import uuid
from test_jobs import Job, add_jobs_argument, print_failure, run_jobs

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


class AcceptanceRun:
    """Own one inventory and report, with jobs usable by either shared entry point."""

    def __init__(self, binary, *, spec_plugin=None, selector=None, review=False, listing=False, env=None):
        self.review, self.listing = review, listing
        self.env = dict(os.environ if env is None else env)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
        self.run = run = ROOT / ".source-down/e2e/runs" / run_id
        run.mkdir(parents=True)
        for name in ("tests-e2e", "docs/specs"):
            shutil.copytree(ROOT / name, run / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        queries = ROOT / "docs/engineering/search-queries.json"
        if queries.exists():
            (run / "docs/engineering").mkdir()
            shutil.copy2(queries, run / "docs/engineering/search-queries.json")
        (run / "source-down.toml").write_text("config_version = 1\n", encoding="utf-8")
        sys.path.insert(0, str(run / "tests-e2e"))
        from support.case import RunContext, identity
        plugin_name = "spec-plugin.exe" if binary.suffix.lower() == ".exe" else "spec-plugin"
        self.context = context = RunContext(ROOT, run, binary, spec_plugin or binary.parent / "examples" / plugin_name,
                                            env=self.env)
        self.report = report = {"run_id": run_id,
            "scope": "listing" if listing else "partial" if selector is not None else "complete",
            "selection": selector, "full_pass": False, "cases": [], "source_sha256": source_hashes(run),
            "errors": [], "interrupted": False, "workspace": str(ROOT), "platform": sys.platform,
            "started_at": context.started_at, "commands": context.commands, "mutations": context.mutations,
            "suite_events": [], "workers": [], "coverage_environment": {name: self.env[name] for name in
                ("LLVM_PROFILE_FILE", "SD_COVERAGE_ROOT", "SD_COVERAGE_DATA") if name in self.env}}
        self.completed = 0
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
                    if not listing:
                        report["errors"].append(str(error))
            _, report["cases"], errors = discover(run, selector)
            report["errors"].extend(errors)
        except KeyboardInterrupt:
            report["interrupted"] = True
            report["errors"].append("discovery interrupted")
        except Exception:
            report["errors"].append(traceback.format_exc())

    def jobs(self, limit):
        report = self.report
        if self.listing or report["errors"] or report["interrupted"]:
            return []
        groups = {}
        for case in report["cases"]:
            if case["selected"]:
                groups.setdefault(case["source"], []).append(case)
        directory = self.run / "workers"
        directory.mkdir()
        jobs = []
        for number, (source, cases) in enumerate(groups.items()):
            manifest = directory / f"worker-{number:04d}.json"
            manifest.write_text(json.dumps({"repository": str(ROOT), "run": str(self.run),
                "binary": str(self.context.binary), "spec_plugin": str(self.context.spec_plugin),
                "cases": cases, "logs": f"logs/worker-{number:04d}"}), encoding="utf-8")
            job = Job(source, [sys.executable, ROOT / "tools/acceptance_worker.py", manifest], ROOT, self.env)
            job.logs = self.run / "logs/workers"
            job.complete = lambda completed, path=manifest, assigned=cases: self.collect(completed, path, assigned)
            jobs.append(job)
        if limit > 1:
            durations = self.previous_durations()
            jobs.sort(key=lambda job: -durations.get(job.name, 0))
        report["jobs"] = min(limit, len(jobs))
        print(f"E2E: {sum(case['selected'] for case in report['cases'])} cases, {report['jobs']} workers", flush=True)
        return jobs

    def previous_durations(self):
        for path in sorted(self.run.parent.glob("*/results.json"), reverse=True):
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
                if previous.get("scope") != "complete" or previous.get("tests_status") != "passed":
                    continue
                durations = {}
                for case in previous["cases"]:
                    if case.get("started_at") and case.get("ended_at"):
                        duration = (datetime.fromisoformat(case["ended_at"]) - datetime.fromisoformat(case["started_at"])).total_seconds()
                        durations[case["source"]] = durations.get(case["source"], 0) + duration
                return durations
            except (OSError, ValueError, KeyError, TypeError):
                continue  # Scheduling hints never determine discovery or acceptance.
        return {}

    def collect(self, job, manifest, assigned):
        report = self.report
        worker = dict(job.record)
        for stream in ("stdout", "stderr"):
            worker[stream] = Path(worker[stream]).relative_to(self.run).as_posix()
        report["workers"].append(worker)
        try:
            result = json.loads(manifest.with_suffix(".result.json").read_text(encoding="utf-8"))
            if [case["id"] for case in result["cases"]] != [case["id"] for case in assigned]:
                raise ValueError("worker returned a different case inventory")
            for original, actual in zip(assigned, result["cases"]):
                original.update(actual)
            report["commands"].extend(result["commands"])
            report["mutations"].extend(result["mutations"])
            report["suite_events"].extend(result["suite_events"])
            report["errors"].extend(result["errors"])
            report["interrupted"] |= result["interrupted"]
            if job.record["exit_code"] not in (0, 130) or not result.get("finished"):
                raise ValueError(f"worker exited {job.record['exit_code']} without a completed result")
        except (OSError, ValueError, KeyError, TypeError) as error:
            report["errors"].append(f"{job.name}: {error}; stderr: {worker['stderr']}")
            for case in assigned:
                if case["started_at"] and case["status"] == "not_run":
                    case.update(status="error", ended_at=job.record["ended_at"], reason=str(error))
        if job.record.get("error"):
            report["errors"].append(job.record["error"])
        for case in assigned:
            self.completed += 1
            print(f"[E2E {self.completed}] {case['id']}: {case['status']} ({job.record['seconds']:.2f}s module)", flush=True)
            if case["status"] in ("failed", "error") and case.get("log"):
                print_failure(f"{case['id']}\n" + (self.run / case["log"]).read_text(encoding="utf-8"))
        return report["interrupted"]

    def finish(self, interrupted=False):
        from support.result import now
        from support.reading import publish, save
        report, context, run = self.report, self.context, self.run
        context.resources.close()
        report["interrupted"] |= interrupted
        if report["interrupted"] and "execution interrupted" not in report["errors"]:
            report["errors"].append("execution interrupted")
        for event in report["suite_events"]:
            if event["status"] == "error":
                report["errors"].append((run / event["log"]).read_text(encoding="utf-8"))
        unchanged = source_hashes(run) == report["source_sha256"]
        if not unchanged:
            report["errors"].append("preserved inputs changed during execution")
        selected = [case for case in report["cases"] if case["selected"]]
        applicable = [case for case in selected if case["applicable"]]
        passed = (not report["errors"] and not self.listing and bool(applicable)
                  and all(case["status"] == "passed" for case in applicable)
                  and all(case["status"] == "skipped" for case in selected if not case["applicable"]))
        report["tests_status"] = ("error" if report["errors"] or any(case["status"] == "error" for case in selected)
                                  else "not_run" if self.listing else "passed" if passed
                                  else "failed" if any(case["status"] == "failed" for case in selected) else "incomplete")
        report["full_pass"] = report["scope"] == "complete" and passed and not self.review
        report["tests_ended_at"] = report["ended_at"] = now()
        report["documentation"] = {"status": "pending" if self.review else "not_requested"}
        for error in report["errors"]:
            print_failure(f"E2E error: {error}")
        save(report, run)
        if self.review:
            try:
                if not unchanged or report["interrupted"]:
                    raise RuntimeError("reading requires unchanged executed inputs and an uninterrupted coordinator")
                print("E2E: publishing reading material", flush=True)
                report["documentation"] = publish(context, report)
                if source_hashes(run) != report["source_sha256"]:
                    raise RuntimeError("preserved inputs changed during reading")
                report["full_pass"] = report["scope"] == "complete" and passed
            except (Exception, KeyboardInterrupt) as error:
                if isinstance(error, KeyboardInterrupt):
                    report["interrupted"] = True
                report["documentation"] = {"status": "failed", "error": str(error) or "reading interrupted"}
                report["full_pass"] = False
            report["ended_at"] = now()
            save(report, run)
        if self.listing:
            for case in report["cases"]:
                print(f"{case['source'].removeprefix('tests-e2e/cases/')} :: {case['title']} [{case['status']}]")
        print(f"E2E results: {run / 'results.json'}", flush=True)
        entry = run / ("reading/pages/index.md.md" if report["documentation"]["status"] == "passed" else "results.md")
        print(f"E2E reading: {entry}", flush=True)
        if report["interrupted"]:
            return 130
        return 0 if ((self.listing and selected and not report["errors"]) or passed) and report["documentation"]["status"] != "failed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    executable = "source-down.exe" if os.name == "nt" else "source-down"
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release" / executable)
    parser.add_argument("--spec-plugin", type=Path)
    parser.add_argument("--case", help="exact scenario file or workflow directory under cases")
    parser.add_argument("--review", action="store_true", help="render this run's scenarios and results")
    parser.add_argument("--list", action="store_true", help="discover without executing scenarios")
    add_jobs_argument(parser)
    args = parser.parse_args()
    acceptance = AcceptanceRun(args.binary, spec_plugin=args.spec_plugin, selector=args.case,
                               review=args.review, listing=args.list)
    interrupted = False
    try:
        interrupted = run_jobs(acceptance.jobs(args.jobs), args.jobs, acceptance.run / "logs/workers")
    except KeyboardInterrupt:
        interrupted = True
    except Exception:
        acceptance.report["errors"].append(traceback.format_exc())
    return acceptance.finish(interrupted)


if __name__ == "__main__":
    sys.exit(main())
