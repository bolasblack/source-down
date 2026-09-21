"""Own test and fixture subprocess scopes until their logs and cleanup are complete."""
import base64
import ctypes
import json
import os
import signal
import subprocess
import sys
import time


class WindowsJob:
    def __init__(self, record):
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

        self.record = record
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, result, arguments in (
            ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
            ("SetInformationJobObject", wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]),
            ("AssignProcessToJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
            ("TerminateJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
            ("QueryInformationJobObject", wintypes.BOOL,
             [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]),
            ("OpenProcess", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
            ("WaitForSingleObject", wintypes.DWORD, [wintypes.HANDLE, wintypes.DWORD]),
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

    def members(self, handle):
        from ctypes import wintypes
        capacity = 16
        while True:
            class ProcessIds(ctypes.Structure):
                _fields_ = [("assigned", wintypes.DWORD), ("count", wintypes.DWORD),
                            ("ids", ctypes.c_size_t * capacity)]

            members = ProcessIds()
            if self.api.QueryInformationJobObject(handle, 3, ctypes.byref(members), ctypes.sizeof(members), None):
                if members.count == members.assigned:
                    return list(members.ids[:members.count])
            elif ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                raise ctypes.WinError(ctypes.get_last_error())
            capacity = max(capacity * 2, members.assigned)

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            processes = {}
            self.record["windows_job_pids"] = []
            self.record["windows_waited_pids"] = []
            try:
                # Job accounting can reach zero before process teardown releases
                # its cwd. Capture handles before termination and wait for their
                # signaled exit state, including children whose parents exited.
                deadline = time.monotonic() + 5
                while True:
                    for pid in self.members(handle):
                        if pid not in processes:
                            process = self.api.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                            if process:
                                processes[pid] = process
                                self.record["windows_job_pids"].append(pid)
                            elif ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER: already gone
                                raise ctypes.WinError(ctypes.get_last_error())
                    if not self.api.TerminateJobObject(handle, 1):
                        raise ctypes.WinError(ctypes.get_last_error())
                    for pid, process in processes.items():
                        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                        status = self.api.WaitForSingleObject(process, remaining_ms)
                        if status == 258:  # WAIT_TIMEOUT
                            raise TimeoutError(f"Windows job process {pid} has not exited after termination")
                        if status != 0:  # WAIT_OBJECT_0
                            raise ctypes.WinError(ctypes.get_last_error())
                        if pid not in self.record["windows_waited_pids"]:
                            self.record["windows_waited_pids"].append(pid)
                    if not self.members(handle):
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Windows job still owns processes after termination")
            finally:
                for process in processes.values():
                    self.api.CloseHandle(process)
                if not self.api.CloseHandle(handle):
                    raise ctypes.WinError(ctypes.get_last_error())


class ProcessScope:
    def __init__(self, arguments, *, cwd, input, env, stdout, stderr, record):
        self.process, self.job, self.record = None, None, record
        self.input = input
        command = arguments
        if os.name == "nt":
            self.job = WindowsJob(record)
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
        try:
            if self.job:
                self.job.close()
        finally:
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
