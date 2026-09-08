# 把真实 inotify 初始化调用限制为 EMFILE，验证 CLI 的自动降级；--poll 不调用它。
import os
import sys
from support import E2ECase


class NativeFallback(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """真实通知初始化资源故障说明原因并持续轮询，显式 --poll 从不初始化原生后端"""
        with self.project({"fault.c": self.fixture("watch/notify_failure.c")}) as fixture:
            library = fixture.root / "notify_failure.so"
            compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                self.context.repository / "tools/cc", "-shared", "-fPIC", fixture.root / "fault.c",
                "-o", library, "-ldl"], cwd=fixture.root, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for explicit in (False, True):
                with self.subTest(explicit=explicit), self.project({"docs/index.md": "Fallback before\n"}) as project:
                    record = fixture.root / ("explicit.calls" if explicit else "fallback.calls")
                    environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_NOTIFY_FAILURE_RECORD=str(record))
                    arguments = [self.context.binary, "watch", "docs", "--root", project.root]
                    if explicit: arguments.append("--poll")
                    with self.context.running(arguments, cwd=project.root, env=environment) as process:
                        process.wait_for(lambda: b"pages; watching" in process.stderr)
                        self.assertIn(b"watch: backend poll", process.stderr)
                        if explicit:
                            self.assertFalse(record.exists())
                        else:
                            self.assertEqual(record.read_bytes(), b"init\n")
                            self.assertIn(b"switching to poll", process.stderr)
                            self.assertIn(b"Too many open files", process.stderr)
                        project.write_text("docs/index.md", "Fallback after\n")
                        page = project.root / ".source-down/pages/docs/index.md.md"
                        process.wait_for(lambda: b"Fallback after" in project.read_bytes(page))
                        self.assertEqual(process.stderr.count(b"switching to poll"), 0 if explicit else 1)
                        process.interrupt()
                        self.assertEqual(process.wait().returncode, 130)
            with self.project({"docs/index.md": "Cancel before fallback\n"}) as project:
                record, release = fixture.root / "cancel.calls", fixture.root / "cancel.release"
                environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_NOTIFY_FAILURE_RECORD=str(record),
                                   SD_WATCH_NOTIFY_RELEASE=str(release))
                with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root, env=environment) as process:
                    try:
                        process.wait_for(record.is_file)
                        process.interrupt()
                        release.write_text("allow backend failure to return")
                        self.assertEqual(process.wait().returncode, 130)
                        self.assertFalse((project.root / ".source-down/search/index.json").exists())
                    finally:
                        release.write_text("cleanup must not remain blocked")
