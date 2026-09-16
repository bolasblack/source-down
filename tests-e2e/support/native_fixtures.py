"""Existing native failure windows, kernel observations and ordinary credentials."""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import shutil
import struct
import sys
from .artifacts import UNSET
from .source_down import _checkRunResult
from .watch import Watch


def _compile(case, project, source, library):
    result = case.context.command([
        sys.executable, case.context.repository / "tools/build.py", "--",
        case.context.repository / "tools/cc", "-shared", "-fPIC", project.root / source,
        "-o", project.root / library, "-ldl",
    ], cwd=project.root, timeout=60)
    _checkRunResult(result, exitCode=0)
    return project.root / library


def _release(path):
    path.parent.mkdir(exist_ok=True)
    path.write_text("continue")


def processExited(pid):
    stat = Path(f"/proc/{pid}/stat")
    return not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] == "Z"


class ScanBaselineWindow:
    def __init__(self, project, library):
        self.project = project
        self.environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_SCAN_ROOT=str(project.root))

    def arm(self):
        self.project.writeFiles({".source-down/scan.arm": "pause baseline"})

    def waitUntilPaused(self, watch):
        return watch._running.wait_for((self.project.root / ".source-down/scan.ready").is_file)

    def release(self):
        _release(self.project.root / ".source-down/scan.release")


class CleanupWindow:
    def __init__(self, project, library):
        self.project = project
        self.environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_CLEANUP_ROOT=str(project.root))

    def waitUntilPaused(self, watch):
        return watch._running.wait_for((self.project.root / ".source-down/cleanup.ready").is_file)

    def release(self):
        _release(self.project.root / ".source-down/cleanup.release")


class NotificationPublicationFault:
    def __init__(self, project, library, mode):
        self.project = project
        self.environment = dict(os.environ, LD_PRELOAD=str(library),
                                SD_WATCH_NOTIFY_ROOT=str(project.root), SD_WATCH_NOTIFY_MODE=mode)

    def waitUntilCallbackReturned(self, watch):
        return watch.waitForOutputState(filesPresent=[".source-down/notify.delivered"])

    def waitUntilRecoveryBatchPaused(self, watch):
        return watch._running.wait_for((self.project.root / ".source-down/recovery.ready").is_file)

    def releaseRecovery(self):
        _release(self.project.root / ".source-down/recovery.release")


class PublicationFault:
    def __init__(self, project, library, mode):
        self.project = project
        self.environment = dict(os.environ, LD_PRELOAD=str(library),
                                SD_WATCH_PUBLICATION_ROOT=str(project.root), SD_WATCH_PUBLICATION_MODE=mode)

    def release(self):
        self.project.writeFiles({".source-down/fault.release": "allow publication"})


class NotificationInitializationFault:
    def __init__(self, root, library):
        self.root, self.library, self._release = root, library, None

    def environment(self, *, record, release=UNSET):
        environment = dict(os.environ, LD_PRELOAD=str(self.library), SD_WATCH_NOTIFY_FAILURE_RECORD=str(record))
        if release is not UNSET:
            self._release = Path(release)
            environment["SD_WATCH_NOTIFY_RELEASE"] = str(release)
        return environment

    def release(self):
        if self._release is not None:
            self._release.write_text("allow backend failure to return")


class AccessTrace:
    def __init__(self, paths):
        self.paths = paths

    def __enter__(self):
        libc = self.libc = ctypes.CDLL(None, use_errno=True)
        libc.inotify_init1.argtypes = [ctypes.c_int]
        libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1")
        self.names = {}
        try:
            self.add(self.paths)
        except BaseException:
            os.close(self.fd)
            raise
        return self

    def add(self, paths):
        for name, path in paths.items():
            descriptor = self.libc.inotify_add_watch(self.fd, os.fsencode(path), 0x01 | 0x20)  # IN_ACCESS | IN_OPEN
            if descriptor < 0:
                raise OSError(ctypes.get_errno(), "inotify_add_watch", path)
            self.names[descriptor] = name

    def take(self):
        observations = []
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                return observations
            offset = 0
            while offset < len(data):
                descriptor, mask, _, length = struct.unpack_from("iIII", data, offset)
                if mask & 0x4000:  # IN_Q_OVERFLOW invalidates the evidence.
                    raise AssertionError("access trace overflow")
                observations.append((self.names[descriptor], mask))
                offset += 16 + length

    def __exit__(self, *error):
        os.close(self.fd)


class NativeAssertions:
    @contextmanager
    def scanBaselineWindow(self, project):
        project.writeFiles({"target/scan.c": self.fixture("watch/scan.c")})
        yield ScanBaselineWindow(project, _compile(self, project, "target/scan.c", "target/scan.so"))

    @contextmanager
    def cleanupWindow(self, project, *, source="target/shim.c", library="target/cleanup.so"):
        project.writeFiles({source: self.fixture("watch/cleanup.c")})
        yield CleanupWindow(project, _compile(self, project, source, library))

    @contextmanager
    def notificationPublicationFault(self, project, *, mode):
        """Inject while checking pages/docs/z.md.md after pages/docs/a.md.md appears."""
        if mode not in ("error", "rescan"):
            raise ValueError("notification fixture supports only error/rescan")
        with self.project({"fault.c": self.fixture("watch/notification_publication.c")}) as fixture:
            yield NotificationPublicationFault(project, _compile(self, fixture, "fault.c", "fault.so"), mode)

    def notificationRecoveryObserver(self):
        return self.fixture("watch/notification_recovery.py")

    @contextmanager
    def publicationFault(self, project, *, mode):
        if mode not in ("page", "delete", "index", "cancel"):
            raise ValueError("publication fixture supports page/delete/index/cancel")
        with self.project({"fault.c": self.fixture("watch/publication.c")}) as fixture:
            yield PublicationFault(project, _compile(self, fixture, "fault.c", "fault.so"), mode)

    @contextmanager
    def notificationInitializationFault(self):
        with self.project({"fault.c": self.fixture("watch/notify_failure.c")}) as fixture:
            yield NotificationInitializationFault(fixture.root, _compile(self, fixture, "fault.c", "notify_failure.so"))

    def traceFileAccess(self, paths):
        return AccessTrace(paths)

    def assertProcessReaped(self, pid):
        self.assertFalse(Path(f"/proc/{pid}").exists(), f"direct child {pid} must be reaped")

    def assertInotifyRegistration(self, watch, *, path):
        inode = f"ino:{Path(path).stat().st_ino:x} "
        directory = f"/proc/{watch._running.scope.process.pid}/fdinfo"
        registrations = []
        for name in os.listdir(directory):
            try:
                with open(f"{directory}/{name}") as info:
                    registrations.extend(info.readlines())
            except FileNotFoundError:
                pass
        self.assertTrue(any(line.startswith("inotify ") and inode in line for line in registrations), registrations)

    def ordinaryUserWatch(self, project, *, inputs):
        command = [self.context.binary, "watch", *inputs, "--root", project.root]
        if os.geteuid() == 0:
            copied = project.root / "target/source-down"
            copied.parent.mkdir()
            shutil.copy2(self.context.binary, copied)
            project.root.chmod(0o777)
            command = [sys.executable, "-c", "import os,sys; os.setgroups([]); os.setgid(65534); os.setuid(65534); os.execv(sys.argv[1],sys.argv[1:])",
                       copied, "watch", *inputs, "--root", project.root]
        return Watch(project.sourceDown, self.context.running(command, cwd=project.root))
