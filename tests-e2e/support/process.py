"""Own a subprocess scope, including children, until its logs are complete."""
import base64
import ctypes
import json
import os
import signal
import subprocess
import sys


class WindowsJob:
    def __init__(self):
        # Job objects retain ownership even after an intermediate parent exits.
        # The bootstrap waits on stdin until it has been assigned to this job.
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                        ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", ctypes.c_uint64 * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, result, arguments in (
            ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
            ("SetInformationJobObject", wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]),
            ("AssignProcessToJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
            ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE]),
        ):
            function = getattr(self.api, name)
            function.restype, function.argtypes = result, arguments
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


class ProcessScope:
    def __init__(self, arguments, *, cwd, input, env, stdout, stderr, record):
        self.process, self.job, self.record = None, None, record
        self.input = input
        command = arguments
        if os.name == "nt":
            self.job = WindowsJob()
            bootstrap = ("import base64,json,signal,subprocess,sys; "
                         "signal.signal(signal.SIGBREAK, signal.SIG_IGN); "
                         "p=json.loads(sys.stdin.buffer.readline()); "
                         "sys.exit(subprocess.run(p['argv'], input=base64.b64decode(p['input']) "
                         "if p['input'] is not None else None).returncode)")
            command = [sys.executable, "-c", bootstrap]
            record["bootstrap_argv"] = command
            self.input = (json.dumps({"argv": arguments, "input": base64.b64encode(input).decode("ascii")
                                     if input is not None else None}) + "\n").encode("utf-8")
        try:
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
            self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                            stdout=stdout, stderr=stderr, start_new_session=os.name == "posix", **options)
            record["pid"] = self.process.pid
            if self.job:
                self.job.assign(self.process)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def interrupt(self):
        self.process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)

    def close(self):
        # Log files avoid waiting on an inherited stdout pipe after a parent exits.
        # Cleanup also runs on normal completion to remove any surviving descendants.
        if self.job:
            self.job.close()
        if self.process:
            if os.name == "posix":
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            if self.process.stdin:
                self.process.stdin.close()
            self.record["exit_code"] = self.process.returncode
        self.record["cleanup_complete"] = True


def execute(arguments, *, cwd, input, env, timeout, stdout, stderr, record):
    with ProcessScope(arguments, cwd=cwd, input=input, env=env,
                      stdout=stdout, stderr=stderr, record=record) as scope:
        scope.process.communicate(scope.input, timeout=timeout)
        return scope.process.returncode
