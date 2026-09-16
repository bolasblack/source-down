"""Named observations over the existing real continuous command."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from .artifacts import UNSET, utf8


@dataclass(frozen=True)
class OutputObservation:
    projectRoot: Path
    files: object
    presentFiles: tuple
    absentPaths: tuple


@dataclass(frozen=True)
class WatchCheckpoint:
    _owner: object
    offset: int


@dataclass(frozen=True)
class LogObservation:
    stderr: bytes
    checkpoint: WatchCheckpoint


@dataclass(frozen=True)
class EventObservation:
    path: str | Path
    content: bytes
    count: int


class Watch:
    def __init__(self, sourceDown, running):
        self.sourceDown, self._running = sourceDown, running
        self.project = sourceDown.project
        self._identity = None

    def __enter__(self):
        self._running.__enter__()
        self._identity = object()
        return self

    def __exit__(self, kind, error, traceback):
        try:
            return self._running.__exit__(kind, error, traceback)
        finally:
            self._identity = None

    @property
    def stdout(self):
        return self._running.stdout

    @property
    def stderr(self):
        return self._running.stderr

    def checkpoint(self):
        if self._identity is None:
            raise RuntimeError("checkpoint requires an entered watch")
        return WatchCheckpoint(self._identity, len(self.stderr))

    def waitForDiagnostics(self, *, contains, since=UNSET, timeout=15):
        offset = 0
        if since is not UNSET:
            if not isinstance(since, WatchCheckpoint):
                raise TypeError("since requires a WatchCheckpoint")
            if self._identity is None or since._owner is not self._identity:
                raise ValueError("checkpoint belongs to another watch start")
            if type(since.offset) is not int or not 0 <= since.offset <= len(self.stderr):
                raise ValueError("checkpoint offset is outside the watch log")
            offset = since.offset

        def observed():
            current = self.stderr
            interval = current[offset:]
            if all(utf8(text) in interval for text in contains):
                return LogObservation(interval, WatchCheckpoint(self._identity, len(current)))
            return None
        return self._running.wait_for(observed, timeout=timeout)

    def waitForPublishedPages(self, count, *, since=UNSET, timeout=15):
        return self.waitForDiagnostics(contains=[f"published {count} pages"], since=since, timeout=timeout)

    def waitForOutputState(self, *, filesPresent=(), absent=(), changed=None, contains=None,
                           indexManifest=None, timeout=15):
        presentFiles, absentPaths = tuple(filesPresent), tuple(absent)

        def observed():
            from .source_down import IndexView
            files = {}

            def read(path):
                if path not in files:
                    files[path] = self.project.readBytes(path)
                return files[path]

            if not all((self.project.root / path).is_file() for path in presentFiles):
                return None
            if not all(not (self.project.root / path).exists() for path in absentPaths):
                return None
            if not all(read(path) != utf8(before) for path, before in (changed or {}).items()):
                return None
            if not all(utf8(text) in read(path) for path, text in (contains or {}).items()):
                return None
            for path, expected in (indexManifest or {}).items():
                manifest = IndexView(read(path)).data["manifest"]
                if any(manifest[key] != value for key, value in expected.items()):
                    return None
            return OutputObservation(self.project.root, MappingProxyType(files.copy()), presentFiles, absentPaths)
        return self._running.wait_for(observed, timeout=timeout)

    def waitForSearchOutput(self, query, *, contains, outputDir=UNSET, timeout=15):
        return self._waitForSearch(query, contains, outputDir, timeout, successful=False)

    def waitForSuccessfulSearch(self, query, *, contains, outputDir=UNSET, timeout=15):
        return self._waitForSearch(query, contains, outputDir, timeout, successful=True)

    def _waitForSearch(self, query, contains, outputDir, timeout, *, successful):
        def observed():
            found = self.sourceDown.search(query, outputDir=outputDir)
            return found if (not successful or found.raw.returncode == 0) and utf8(contains) in found.raw.stdout else None
        return self._running.wait_for(observed, timeout=timeout)

    def waitForProcessExit(self, pid, *, timeout=15):
        from .native_fixtures import processExited
        return self._running.wait_for(lambda: processExited(pid), timeout=timeout)

    def waitForEventCount(self, path, event, *, greaterThan, filesPresent=(), timeout=15):
        def observed():
            if not all((self.project.root / item).is_file() for item in filesPresent):
                return None
            content = self.project.readBytes(path)
            count = content.count(utf8(event))
            return EventObservation(path, content, count) if count > greaterThan else None
        return self._running.wait_for(observed, timeout=timeout)

    def interrupt(self):
        self._running.interrupt()

    def wait(self, *, timeout=10):
        return self._running.wait(timeout=timeout)


class WatchAssertions:
    def assertWatchDiagnostics(self, watch, *, contains):
        current = watch.stderr
        for text in contains:
            self.assertIn(utf8(text), current)
