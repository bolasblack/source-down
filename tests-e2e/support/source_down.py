"""Real CLI actions retain command facts; assertions declare their expectations."""
from copy import deepcopy
from dataclasses import dataclass
import json
import subprocess
import time
from .artifacts import UNSET, OutputSnapshot, utf8


class CommandResult:
    def __init__(self, raw):
        self._command = deepcopy(raw)

    @property
    def raw(self):
        return deepcopy(self._command)

    @property
    def data(self):
        return json.loads(self._command.stdout)


class IndexView:
    def __init__(self, output):
        self._output = output

    @property
    def data(self):
        content = self._output if isinstance(self._output, bytes) else self._output.files["search/index.json"]
        return json.loads(content)

    @property
    def recordIds(self):
        return tuple(record["id"] for record in self.data["records"])


class RenderResult(CommandResult):
    def __init__(self, raw, project, output):
        super().__init__(raw)
        self._project, self._output = project, output

    @property
    def project(self):
        return self._project

    @property
    def outputRoot(self):
        return self._output.outputRoot

    @property
    def output(self):
        return self._output

    @property
    def index(self):
        return IndexView(self.output)


class Hit:
    def __init__(self, data):
        self._data = deepcopy(data)

    @property
    def data(self):
        return deepcopy(self._data)

    @property
    def handle(self):
        return self._data["handle"]

    @property
    def kind(self):
        return self._data["kind"]

    @property
    def snippet(self):
        return self._data["snippet"]


class SearchResult(CommandResult):
    @property
    def hits(self):
        return tuple(Hit(hit) for hit in self.data["hits"])

    @property
    def snapshot(self):
        return self.data["snapshot"]


@dataclass(frozen=True)
class PageInspection:
    nextOffset: int | None = None
    problems: tuple = ()
    error: Exception | None = None


def inspectPage(page):
    """Inspect progress once, independently of the fixture's expected content."""
    try:
        body = page.body
        problems = []
        if set(body) != {"text", "range", "total_bytes", "truncated", "next_offset"}:
            problems.append("body fields differ")
        end = page.requestedOffset + len(body["text"].encode("utf-8"))
        if body["range"] != [page.requestedOffset, end]:
            problems.append("body range differs from requested offset and UTF-8 bytes")
        following = body["next_offset"]
        if following is None:
            if body["truncated"] is not False:
                problems.append("final page must have truncated=False")
        elif (type(following) is not int or following <= page.requestedOffset or
              following != end or body["truncated"] is not True):
            problems.append("continuation must advance to range end with truncated=True")
        return PageInspection(following, tuple(problems))
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        return PageInspection(error=error)


class ReadPage(CommandResult):
    def __init__(self, raw, requestedOffset):
        super().__init__(raw)
        self._offset = requestedOffset

    @property
    def requestedOffset(self):
        return self._offset

    @property
    def body(self):
        return self.data["body"]

    @property
    def inspection(self):
        return inspectPage(self)


class ReadResult:
    def __init__(self, pages, stopReason):
        self._pages, self._stopReason = tuple(pages), stopReason

    @property
    def pages(self):
        return self._pages

    @property
    def stopReason(self):
        return self._stopReason

    @property
    def commands(self):
        return tuple(page.raw for page in self.pages)

    def singlePage(self):
        if len(self.pages) != 1:
            raise ValueError("this convenience property requires a single-page ReadResult")
        return self.pages[0]

    @property
    def raw(self):
        return self.singlePage().raw

    @property
    def data(self):
        return self.singlePage().data

    @property
    def body(self):
        return self.singlePage().body

    @property
    def snapshot(self):
        return self.data["snapshot"]


class SourceDown:
    def __init__(self, project, *, binary=None):
        self.project = project
        self._binary = project.context.binary if binary is None else binary

    def withBinary(self, binary):
        return SourceDown(self.project, binary=binary)

    def watch(self, inputs, *, outputDir=UNSET, config=UNSET, poll=False, env=None):
        arguments = ["watch", *inputs]
        if poll:
            arguments.append("--poll")
        arguments.extend(["--root", self.project.root])
        for flag, value in (("--config", config), ("--output-dir", outputDir)):
            if value is not UNSET:
                arguments.extend([flag, value])
        return self.watchCommand(arguments, env=env)

    def watchCommand(self, arguments, *, env=None):
        from .watch import Watch
        running = self.project.context.running([self._binary, *arguments],
                                               cwd=self.project.root, env=env)
        return Watch(self, running)

    def render(self, inputs, *, outputDir=UNSET, timeout=30):
        arguments = ["render", *inputs]
        if outputDir is not UNSET:
            arguments.extend(["--output-dir", outputDir])
        raw = self.project.run(arguments, binary=self._binary, timeout=timeout)
        return RenderResult(raw, self.project, self.project.captureOutput(outputDir=outputDir))

    def renderSuccessfully(self, inputs, *, outputDir=UNSET, indexRecords=UNSET, includesFiles=UNSET, timeout=30):
        reading = self.render(inputs, outputDir=outputDir, timeout=timeout)
        _checkRunResult(reading, exitCode=0, stdout=b"")
        if indexRecords is not UNSET:
            _checkIndexRecords(reading, indexRecords)
        if includesFiles is not UNSET:
            _checkOutputFiles(reading, includesFiles)
        return reading

    def search(self, query, *, path=UNSET, limit=UNSET, snapshot=False, outputDir=UNSET, timeout=30):
        arguments = ["search", query]
        for flag, value in (("--path", path), ("--limit", limit)):
            if value is not UNSET:
                arguments.extend([flag, str(value)])
        return SearchResult(self.project.run(self.queryArguments(arguments, snapshot, outputDir),
                                              binary=self._binary, timeout=timeout))

    def searchSuccessfully(self, query, *, path=UNSET, limit=UNSET, snapshot=False, outputDir=UNSET, timeout=30):
        found = self.search(query, path=path, limit=limit, snapshot=snapshot, outputDir=outputDir, timeout=timeout)
        _checkRunResult(found, exitCode=0)
        return found

    def read(self, handle, *, snapshot=False, outputDir=UNSET, timeout=30):
        raw = self.project.run(self.queryArguments(["read", handle], snapshot, outputDir),
                               binary=self._binary, timeout=timeout)
        return ReadResult([ReadPage(raw, 0)], "single")

    @staticmethod
    def queryArguments(arguments, snapshot, outputDir):
        if snapshot:
            arguments.append("--snapshot")
        if outputDir is not UNSET:
            arguments.extend(["--output-dir", outputDir])
        return [*arguments, "--json"]

    def readEntity(self, path, entity, *, offset=UNSET, followContinuation=False, timeout=30, totalTimeout=30):
        current = 0 if offset is UNSET else offset
        pages = []
        deadline = time.monotonic() + totalTimeout
        while True:
            arguments = ["read", path, f"--id={entity}"]
            if followContinuation or offset is not UNSET:
                arguments.extend(["--offset", str(current)])
            arguments.append("--json")
            budget = timeout
            if followContinuation:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments, totalTimeout)
                budget = min(timeout, remaining)
            page = ReadPage(self.project.run(arguments, binary=self._binary, timeout=budget), current)
            pages.append(page)
            if not followContinuation:
                return ReadResult(pages, "single")
            if page.raw.returncode:
                return ReadResult(pages, "nonzero exit")
            inspection = page.inspection
            if inspection.error is not None or inspection.problems:
                return ReadResult(pages, "invalid response")
            if inspection.nextOffset is None:
                return ReadResult(pages, "complete")
            current = inspection.nextOffset

    def readEntityToEnd(self, path, entity, *, timeout=30, totalTimeout=30):
        return self.readEntity(path, entity, followContinuation=True, timeout=timeout, totalTimeout=totalTimeout)


def _checkRunResult(actual, *, exitCode=UNSET, stdout=UNSET, stderr=UNSET,
                    stderrContains=UNSET, stderrNotEmpty=UNSET):
    raw = actual if isinstance(actual, subprocess.CompletedProcess) else actual.raw
    context = f"command {raw.args!r}; exit {raw.returncode}; stderr {raw.stderr!r}"
    for name, observed, expected in (("exit", raw.returncode, exitCode),
                                     ("stdout", raw.stdout, stdout), ("stderr", raw.stderr, stderr)):
        if expected is UNSET:
            continue
        if name != "exit":
            expected = utf8(expected)
        if observed != expected:
            raise AssertionError(f"{context}\n{name}: expected {expected!r}, got {observed!r}")
    if stderrContains is not UNSET:
        for piece in stderrContains:
            if utf8(piece) not in raw.stderr:
                raise AssertionError(f"{context}\nmissing stderr fragment {piece!r}")
    if stderrNotEmpty is not UNSET and bool(raw.stderr) != stderrNotEmpty:
        raise AssertionError(f"{context}\nstderr nonempty: expected {stderrNotEmpty!r}")
    return raw, context


def _checkIndexRecords(reading, expected):
    context = f"command {reading.raw.args!r}; output {reading.outputRoot}"
    files = reading.output.files
    if "search/index.json" not in files:
        raise AssertionError(f"{context}: missing search/index.json")
    count = len(json.loads(files["search/index.json"])["records"])
    if count != expected:
        raise AssertionError(f"{context}: expected {expected!r} records, got {count}")


def _checkOutputFiles(reading, expected):
    for name in expected:
        if name not in reading.output.files:
            raise AssertionError(f"{reading.outputRoot}: missing artifact {name}")


class RunAssertions:
    def assertScopeCollision(self, result, *, handle, recordId=UNSET):
        from .mutation import ScopeCollision
        self.assertRunResult(result, exitCode=1, stdout=b"", error=ScopeCollision(handle=handle, recordId=recordId))

    def assertRecordCollision(self, result, *, handle, recordIds=UNSET):
        from .mutation import RecordCollision
        self.assertRunResult(result, exitCode=1, stdout=b"", error=RecordCollision(handle=handle, recordIds=recordIds))

    def assertRunResult(self, actual, *, exitCode=UNSET, stdout=UNSET, stderr=UNSET,
                        stderrContains=UNSET, stderrNotEmpty=UNSET, error=UNSET):
        raw, context = _checkRunResult(actual, exitCode=exitCode, stdout=stdout, stderr=stderr,
                                       stderrContains=stderrContains, stderrNotEmpty=stderrNotEmpty)
        if error is not UNSET:
            from .mutation import assertCollision
            assertCollision(self, raw.stderr, error, context)

    def assertRenderResult(self, actual, *, includesFiles=UNSET, indexRecords=UNSET, **process):
        if not isinstance(actual, RenderResult):
            raise TypeError("expected RenderResult")
        self.assertRunResult(actual, **process)
        if includesFiles is not UNSET:
            _checkOutputFiles(actual, includesFiles)
        if indexRecords is not UNSET:
            _checkIndexRecords(actual, indexRecords)
