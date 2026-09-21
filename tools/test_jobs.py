"""Bound independent test processes and collect every outcome, including cancellation."""
import argparse
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import time

from process_scope import ProcessScope


def positive_jobs(value):
    try:
        number = int(value)
        if number > 0:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("jobs must be a positive integer")


def add_jobs_argument(parser):
    parser.add_argument("--jobs", type=positive_jobs,
                        default=os.environ.get("SD_TEST_JOBS", str(os.process_cpu_count() or 1)),
                        help="maximum concurrent test processes (default: SD_TEST_JOBS or available CPUs)")


@dataclass
class Job:
    name: str
    argv: list
    cwd: Path
    env: dict | None = None
    complete: object = None
    record: dict = field(default_factory=dict)
    logs: Path | None = None


def run_jobs(jobs, limit, logs):
    """Callbacks consume reaped jobs. Return whether execution was interrupted."""
    logs.mkdir(parents=True, exist_ok=True)
    pending, active = deque(enumerate(jobs)), []
    interrupted, deadline = False, None

    def cancel():
        nonlocal interrupted, deadline
        interrupted = True
        if deadline is None:
            deadline = time.monotonic() + 10
            for _, scope, _, _ in active:
                if scope.process.poll() is None:
                    try:
                        scope.interrupt()
                    except ProcessLookupError:
                        pass

    try:
        while active or (pending and not interrupted):
            try:
                while pending and len(active) < limit and not interrupted:
                    number, job = pending.popleft()
                    stack = ExitStack()
                    row = job.record
                    destination = job.logs or logs
                    destination.mkdir(parents=True, exist_ok=True)
                    row.update(name=job.name, argv=[str(arg) for arg in job.argv], cwd=str(job.cwd),
                               started_at=datetime.now(timezone.utc).isoformat(), ended_at=None,
                               stdout=str(destination / f"job-{number:04d}.stdout.bin"),
                               stderr=str(destination / f"job-{number:04d}.stderr.bin"))
                    try:
                        scope = stack.enter_context(ProcessScope(row["argv"], cwd=job.cwd, env=job.env,
                            input=None, stdout=stack.enter_context(open(row["stdout"], "wb")),
                            stderr=stack.enter_context(open(row["stderr"], "wb")), record=row))
                        if scope.input is not None:
                            scope.process.stdin.write(scope.input)
                            scope.process.stdin.flush()
                        scope.process.stdin.close()
                    except BaseException:
                        stack.close()
                        raise
                    active.append((job, scope, stack, time.monotonic()))
                for entry in list(active):
                    job, scope, stack, started = entry
                    if scope.process.poll() is None:
                        if deadline is None or time.monotonic() < deadline:
                            continue
                        job.record["error"] = "worker did not finish cleanup after interruption"
                    stack.close()
                    active.remove(entry)
                    job.record.update(ended_at=datetime.now(timezone.utc).isoformat(),
                                      seconds=time.monotonic() - started)
                    if job.complete and job.complete(job):
                        cancel()
                if active:
                    time.sleep(0.01)
            except KeyboardInterrupt:
                cancel()
    finally:
        for _, _, stack, _ in active:
            stack.close()
    return interrupted
