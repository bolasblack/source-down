"""Bounded observation of a command while the scenario edits its real project."""
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import subprocess
import time
from .case import identity
from .process import ProcessScope
from .result import now


class RunningCommand:
    def __init__(self, context, arguments, *, cwd, env=None):
        self.context = context
        self.arguments = [str(argument) for argument in arguments]
        self.cwd, self.env = cwd, env
        self.resources = ExitStack()

    def __enter__(self):
        self.record = self.context.command_record(self.arguments, cwd=self.cwd)
        self.stdout_path = self.context.run / self.record["stdout"]
        self.stderr_path = self.context.run / self.record["stderr"]
        try:
            executable = shutil.which(self.arguments[0], path=(os.environ if self.env is None else self.env).get("PATH"))
            self.record["executable"] = identity(executable or Path(self.cwd) / self.arguments[0])
            stdout = self.resources.enter_context(self.stdout_path.open("wb"))
            stderr = self.resources.enter_context(self.stderr_path.open("wb"))
            self.scope = self.resources.enter_context(ProcessScope(self.arguments, cwd=self.cwd, input=None,
                                                      env=self.env, stdout=stdout, stderr=stderr, record=self.record))
            # Only the small Windows bootstrap handshake uses this pipe. The command sees EOF.
            if self.scope.input is not None:
                self.scope.process.stdin.write(self.scope.input)
                self.scope.process.stdin.flush()
            self.scope.process.stdin.close()
            return self
        except BaseException as error:
            self.record["error"] = str(error)
            self.resources.close()
            self.record["ended_at"] = now()
            raise

    def __exit__(self, kind, error, traceback):
        try:
            if error is not None:
                self.record["error"] = str(error)
            if self.scope.process.poll() is None:
                self.interrupt()
                try:
                    self.scope.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass  # The shared process scope performs final forced cleanup.
        finally:
            self.resources.close()
            self.record["ended_at"] = now()

    @property
    def stdout(self):
        return self.stdout_path.read_bytes()

    @property
    def stderr(self):
        return self.stderr_path.read_bytes()

    def wait_for(self, predicate, *, timeout=15):
        deadline = time.monotonic() + timeout
        while True:
            value = predicate()
            if value:
                return value
            code = self.scope.process.poll()
            if code is not None:
                raise AssertionError(f"command exited {code} before the expected observation: {self.stderr!r}")
            if time.monotonic() >= deadline:
                raise AssertionError(f"command observation timed out: {self.stderr!r}")
            time.sleep(0.01)

    def interrupt(self):
        self.scope.interrupt()

    def wait(self, *, timeout=10):
        code = self.scope.process.wait(timeout=timeout)
        return subprocess.CompletedProcess(self.arguments, code, self.stdout, self.stderr)
