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
from types import MappingProxyType
from .artifacts import ArtifactAssertions, OutputSnapshot, UNSET, utf8
from .source_down import RunAssertions, SourceDown
from .reading_assertions import ReadingAssertions
from .read_assertions import ReadAssertions
from .index_assertions import IndexAssertions
from .watch import WatchAssertions
from .native_fixtures import NativeAssertions


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

    def command_record(self, arguments, *, cwd, input=None):
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
        return row

    def command(self, arguments, *, cwd, input=None, timeout=30, env=None):
        arguments = [str(argument) for argument in arguments]
        row = self.command_record(arguments, cwd=cwd, input=input)
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

    def running(self, arguments, *, cwd, env=None):
        from .continuous import RunningCommand
        return RunningCommand(self, arguments, cwd=cwd, env=env)


class Project:
    def __init__(self, context, root):
        self.context, self.root = context, Path(root)

    @property
    def sourceDown(self):
        return SourceDown(self)

    def captureOutput(self, *, outputDir=UNSET):
        return OutputSnapshot.capture(self, outputDir)

    def writeFiles(self, files):
        for name, value in files.items():
            self.writeBytes(name, utf8(value))

    def writeBytes(self, name, value):
        self.write_bytes(name, value)

    def writeInPlace(self, path, content):
        (self.root / path).write_bytes(utf8(content))

    def atomicReplace(self, path, content, *, temporaryPath):
        target, temporary = self.root / path, self.root / temporaryPath
        if target.parent.resolve() / target.name == temporary.parent.resolve() / temporary.name:
            raise ValueError("temporary path must differ from the target")
        created = False
        try:
            with temporary.open("xb") as output:
                created = True
                output.write(utf8(content))
            os.replace(temporary, target)
        except BaseException:
            if created:
                try:
                    temporary.unlink()
                except OSError:
                    pass  # Preserve the write, close or replace failure.
            raise

    def readBytes(self, name):
        return self.read_bytes(name)

    def prependBytes(self, name, prefix):
        self.writeBytes(name, prefix + self.readBytes(name))

    def replaceBytes(self, name, old, new, count=-1):
        self.writeBytes(name, self.readBytes(name).replace(old, new, count))

    def replaceInFiles(self, paths, *, replacements):
        for path in paths:
            for old, new in replacements:
                self.replaceBytes(path, old, new)

    def replaceFile(self, path, *, fromPath):
        os.replace(self.root / fromPath, self.root / path)

    def symlink(self, path, *, target, directory=False):
        os.symlink(target, self.root / path, target_is_directory=directory)

    def removeFile(self, path):
        (self.root / path).unlink()

    def makeDirectory(self, path):
        (self.root / path).mkdir()

    def removeDirectory(self, path):
        (self.root / path).rmdir()

    def hardlink(self, path, *, target):
        os.link(self.root / target, self.root / path)

    def replaceSymlink(self, path, *, target, temporaryPath):
        self.symlink(temporaryPath, target=target)
        self.replaceFile(path, fromPath=temporaryPath)

    def writePreservingTimes(self, path, content):
        before = (self.root / path).stat()
        self.writeBytes(path, utf8(content))
        os.utime(self.root / path, ns=(before.st_atime_ns, before.st_mtime_ns))

    @contextmanager
    def editing(self, *paths):
        original = {path: self.readBytes(path) for path in paths}
        try:
            yield MappingProxyType(original)
        finally:
            self.writeFiles(original)

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


class E2ECase(RunAssertions, ArtifactAssertions, ReadingAssertions, ReadAssertions, IndexAssertions, WatchAssertions, NativeAssertions, unittest.TestCase):
    context = None

    def fixture(self, name):
        return (self.context.run / "tests-e2e/fixtures" / name).read_bytes()

    def declaredSearchQueries(self):
        import json
        return json.loads((self.context.run / "docs/engineering/search-queries.json").read_bytes())["queries"]

    def buildMutant(self, *, forceShortHandle="00000000000"):
        from .mutation import Mutant, build_mutant
        if forceShortHandle != "00000000000":
            raise ValueError("the controlled mutation supports only the zero short handle")
        owner = self.context.repository / "src/search/handles.rs"
        original = owner.read_bytes()
        needle = b"base62(xxh64(&input, 0))"
        self.assertEqual(original.count(needle), 1, "controlled replacement owner changed")
        binary = build_mutant(self.context, "src/search/handles.rs", original, needle,
                              b"base62({ let _ = xxh64(&input, 0); 0 })")
        return Mutant(binary, owner, original, self.context.mutations[-1].copy())

    def assertProductionSourceUnchanged(self, mutant):
        self.assertEqual(mutant.owner.read_bytes(), mutant.original, "production source changed")

    @contextmanager
    def project(self, files=None, *, parent=None):
        with tempfile.TemporaryDirectory(prefix="source-down-e2e-project-", dir=parent) as temporary:
            project = Project(self.context, temporary)
            for name, value in (files or {}).items():
                project.write_bytes(name, value.encode("utf-8") if isinstance(value, str) else value)
            yield project
