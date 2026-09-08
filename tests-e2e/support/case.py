"""Isolated files and public commands; scenarios own their expected behavior."""
from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from .result import now
from .process import execute
from .filesystem import read_bytes


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class RunContext:
    def __init__(self, repository, run, binary, spec_plugin):
        self.repository, self.run = repository, run
        self.binary = binary.resolve()
        self.spec_plugin = spec_plugin.resolve()
        self.commands = []
        self.active_case = None
        self.started_at = now()
        self.resources = ExitStack()
        self.mutants = {}
        self.mutations = []

    def command(self, arguments, *, cwd, input=None, timeout=30, env=None):
        arguments = [str(argument) for argument in arguments]
        row = {"case_id": self.active_case, "argv": arguments, "cwd": str(cwd),
               "executable": None,
               "started_at": now(), "ended_at": None, "exit_code": None,
               "stdout": f"logs/command-{len(self.commands) + 1:04d}.stdout.bin",
               "stderr": f"logs/command-{len(self.commands) + 1:04d}.stderr.bin"}
        self.commands.append(row)
        (self.run / "logs").mkdir(exist_ok=True)
        if input is not None:
            row["stdin"] = f"logs/command-{len(self.commands):04d}.stdin.bin"
            (self.run / row["stdin"]).write_bytes(input)
        stdout_path, stderr_path = self.run / row["stdout"], self.run / row["stderr"]
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                executable = shutil.which(arguments[0], path=(os.environ if env is None else env).get("PATH"))
                row["executable"] = identity(executable or Path(cwd) / arguments[0])
                code = execute(arguments, cwd=cwd, input=input, timeout=timeout, env=env,
                               stdout=stdout, stderr=stderr, record=row)
            return subprocess.CompletedProcess(arguments, code, stdout_path.read_bytes(), stderr_path.read_bytes())
        except BaseException as error:
            row["error"] = str(error)
            raise
        finally:
            row["ended_at"] = now()


class Project:
    def __init__(self, context, root):
        self.context, self.root = context, Path(root)

    def write_bytes(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def write_text(self, name, value):
        self.write_bytes(name, value.encode("utf-8"))

    def read_bytes(self, name):
        return read_bytes(self.root / name)

    def run(self, arguments, *, binary=None, timeout=30):
        return self.context.command([binary or self.context.binary, *arguments, "--root", self.root],
                                    cwd=self.root, timeout=timeout)

    def snapshot(self, output=".source-down"):
        base = self.root / output
        return {path.relative_to(base).as_posix(): read_bytes(path)
                for path in sorted(base.rglob("*")) if path.is_file()}


class E2ECase(unittest.TestCase):
    context = None

    def fixture(self, name):
        return (self.context.run / "tests-e2e/fixtures" / name).read_bytes()

    @contextmanager
    def project(self, files=None):
        with tempfile.TemporaryDirectory(prefix="source-down-e2e-project-") as temporary:
            project = Project(self.context, temporary)
            for name, value in (files or {}).items():
                project.write_bytes(name, value.encode("utf-8") if isinstance(value, str) else value)
            yield project

    def verify(self, *, files, command, expect_exit_code=0, expect_stdout=b"",
               expect_file_contains_in_order=None):
        with self.project(files) as project:
            result = project.run(command)
            self.assertEqual(result.returncode, expect_exit_code, result.stderr)
            self.assertEqual(result.stdout, expect_stdout)
            for name, pieces in (expect_file_contains_in_order or {}).items():
                actual = project.read_bytes(name)
                offset = 0
                for piece in pieces:
                    piece = piece.encode("utf-8") if isinstance(piece, str) else piece
                    found = actual.find(piece, offset)
                    self.assertGreaterEqual(found, 0, f"{name}: missing ordered bytes {piece!r}\n{actual!r}")
                    offset = found + len(piece)
