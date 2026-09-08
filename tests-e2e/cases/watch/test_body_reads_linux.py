# 用内核文件访问记录交叉验证正文读取；页面不变或 CPU 低不足以证明没有扫描。
import ctypes
import os
import struct
import time
from support import E2ECase


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
                if mask & 0x4000:  # IN_Q_OVERFLOW makes the trace inconclusive, never a zero-read pass.
                    raise AssertionError("access trace overflow")
                observations.append((self.names[descriptor], mask))
                offset += 16 + length

    def __exit__(self, *error):
        os.close(self.fd)


class NativeBodyReads(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """原生健康与故障空闲不打开或读取正文，已知输入生成也不读取未知普通材料"""
        for failing in (False, True):
            with self.subTest(failing=failing), self.project({"outside.bin": b"outside material\n"}) as outside, self.project({
                "docs/index.md": "Initial body\n",
                "material/blob.bin": bytes(range(256)) * 4096,
                "broken.py": "raise SystemExit(9)\n",
            }) as project:
                (project.root / "outside-tree").symlink_to(outside.root, target_is_directory=True)
                if failing:
                    project.write_text("source-down.toml", 'config_version=1\n[plugins.broken]\ncommand=["python","broken.py"]\n')
                with AccessTrace({"source": project.root / "docs/index.md", "unknown": project.root / "material/blob.bin",
                                  "outside": outside.root / "outside.bin"}) as trace:
                    with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                        expected = b"execution failure; watching" if failing else b"pages; watching"
                        process.wait_for(lambda: expected in process.stderr)
                        initial = trace.take()
                        self.assertTrue(any(name == "source" for name, _ in initial), initial)
                        self.assertFalse(any(name == "unknown" for name, _ in initial), initial)
                        self.assertFalse(any(name == "outside" for name, _ in initial), initial)
                        time.sleep(1.6)  # A quiet observation window spans several old scan intervals.
                        self.assertEqual(trace.take(), [])
                        self.assertIn(b"watch: backend native", process.stderr)
                        if not failing:
                            project.write_text("docs/index.md", "Updated body\n")
                            trace.take()  # Discard the test author's write-open event.
                            page = project.root / ".source-down/pages/docs/index.md.md"
                            process.wait_for(lambda: b"Updated body" in project.read_bytes(page))
                            changed = trace.take()
                            self.assertTrue(any(name == "source" and mask & 0x01 for name, mask in changed), changed)
                            self.assertFalse(any(name == "unknown" for name, _ in changed), changed)
                            self.assertFalse(any(name == "outside" for name, _ in changed), changed)
                            time.sleep(1.1)
                            self.assertEqual(trace.take(), [])
                        process.interrupt()
                        self.assertEqual(process.wait().returncode, 130)
