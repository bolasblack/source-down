"""Discover native and Python tests, then share one process budget with readable E2E."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import unittest
import uuid

from acceptance import AcceptanceRun, flatten
from test_jobs import Job, run_jobs

ROOT = Path(__file__).resolve().parents[1]


def command(argv, env):
    print("+ " + " ".join(map(str, argv)), flush=True)
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode:
        print(result.stdout, end="", flush=True)
        result.check_returncode()
    return result.stdout


def native_jobs(env):
    command(["cargo", "build", "--locked", "--bins", "--examples"], env)
    output = command(["cargo", "test", "--locked", "--no-run", "--message-format=json"], env)
    artifacts = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    artifacts = [item for item in artifacts if item.get("reason") == "compiler-artifact"
                 and item.get("executable") and item["profile"]["test"]]
    jobs, has_library = [], False
    for artifact in artifacts:
        target = artifact["target"]
        has_library |= "lib" in target["kind"] and target.get("doctest", True)
        if Path(target["src_path"]).resolve() == (ROOT / "tests-e2e/bridge.rs").resolve():
            continue  # Its coordinator contributes individual jobs to this same budget.
        executable = artifact["executable"]
        listed = command([executable, "--list", "--format", "terse"], env)
        for line in listed.splitlines():
            if line.endswith(": test"):
                name = line.removesuffix(": test")
                jobs.append(Job(f"Rust {target['name']}::{name}",
                    [executable, "--exact", name, "--test-threads", "1"], ROOT, env))
    if has_library:
        jobs.append(Job("Rust doctests", ["cargo", "test", "--locked", "--doc", "--jobs", "1",
                                         "--", "--test-threads", "1"], ROOT, env))
    return jobs


def python_jobs(env, prefix, *, pattern="*_test.py"):
    sys.path.insert(0, str(ROOT))
    loader = unittest.TestLoader()
    tests = list(flatten(loader.discover(str(ROOT / "tests"), pattern=pattern)))
    if loader.errors:
        raise RuntimeError("\n".join(loader.errors))
    ids = [test.id() for test in tests]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate Python test identity in discovery")
    groups = {}
    for test in tests:
        cls = type(test)
        module = sys.modules[cls.__module__]
        module_fixture = any(callable(getattr(module, name, None)) for name in ("setUpModule", "tearDownModule"))
        class_fixture = any(name in base.__dict__ for base in cls.__mro__ if base is not unittest.TestCase
                            for name in ("setUpClass", "tearDownClass"))
        owner = cls.__module__ if module_fixture else f"{cls.__module__}.{cls.__qualname__}" if class_fixture else test.id()
        groups.setdefault(owner, []).append(test.id())
    child_env = dict(env, SD_TEST_JOBS="1")
    child_env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "tests"), str(ROOT), env.get("PYTHONPATH", "")])
    return [Job(f"Python {selected[0].split('.')[0]}.py::{owner}", [*prefix, ROOT / "tools/python_test_worker.py", *selected],
                ROOT, child_env) for owner, selected in groups.items()], ids


def run_suite(env, limit, *, review=False, python_prefix=None, artifact=None, spec_plugin=None):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    directory = ROOT / ".source-down/test-runs" / run_id
    directory.mkdir(parents=True)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "jobs": [], "errors": [],
              "worker_limit": limit, "interrupted": False, "status": "error",
              "scope": "artifact" if artifact else "all"}
    acceptance, jobs, code = None, [], 1
    try:
        native = [] if artifact else native_jobs(env)
        if artifact:
            env = dict(env, SD_TEST_BINARY=str(artifact.resolve()))
        python, report["python_inventory"] = python_jobs(env, python_prefix or [sys.executable],
            pattern="portability_test.py" if artifact else "*_test.py")
        if not report["python_inventory"]:
            raise RuntimeError("no Python tests discovered")
        suffix = ".exe" if os.name == "nt" else ""
        target = Path(env.get("CARGO_TARGET_DIR", ROOT / "target"))
        if not target.is_absolute():
            target = ROOT / target
        acceptance = AcceptanceRun(artifact or target / "debug" / f"source-down{suffix}",
                                   spec_plugin=spec_plugin, review=review, env=env)
        e2e = acceptance.jobs(limit)
        report["e2e_results"] = str(acceptance.run / "results.json")
        # Start a long E2E module and Python tests early. All processes use this pool;
        # no wrapper reserves a slot while starting its own independent pool.
        jobs = [*e2e[:1], *python, *native, *e2e[1:]]
        completed = 0

        def complete(job):
            nonlocal completed
            completed += 1
            state = "passed" if job.record["exit_code"] == 0 else "failed"
            print(f"[test {completed}/{len(jobs)}] {job.name}: {state} ({job.record['seconds']:.2f}s)", flush=True)
            if state == "failed":
                for stream in ("stdout", "stderr"):
                    text = Path(job.record[stream]).read_text(encoding="utf-8", errors="replace")
                    print(text, end="", flush=True)
            return job.record["exit_code"] == 130

        for job in native + python:
            job.complete = complete
        print(f"Tests: {len(native)} native jobs, {len(report['python_inventory'])} Python tests, "
              f"{len(e2e)} E2E modules; {limit} workers", flush=True)
        report["interrupted"] = run_jobs(jobs, limit, directory / "logs")
        e2e_code = acceptance.finish(report["interrupted"])
        failed = any(job.record.get("exit_code") != 0 for job in native + python)
        code = 130 if report["interrupted"] or e2e_code == 130 else 1 if failed or e2e_code else 0
        report["status"] = "interrupted" if code == 130 else "failed" if code else "passed"
    except KeyboardInterrupt:
        report.update(interrupted=True, status="interrupted")
        code = 130
        if acceptance:
            acceptance.finish(True)
    except Exception:
        report["errors"].append(traceback.format_exc())
        print(report["errors"][-1], file=sys.stderr, flush=True)
        if acceptance:
            acceptance.report["errors"].extend(report["errors"])
            acceptance.finish()
    finally:
        report["jobs"] = [{"name": job.name, **job.record} for job in jobs]
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Test results: {directory / 'results.json'}", flush=True)
    return code
