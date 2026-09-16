# 首批插件故障后，真实 inotify 访问事件证明等待修复时不重读正文或未知材料。
import time
from support import E2ECase


class FailedNativeBodyReads(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """真实插件首次退出 9 后，原生 watch 的修复等待期不扫描正文"""
        with self.project({"outside.bin": b"outside material\n"}) as outside, self.project({
            "docs/index.md": "Initial body\n",
            "material/blob.bin": bytes(range(256)) * 4096,
            "broken.py": "raise SystemExit(9)\n",
            "source-down.toml": 'config_version=1\n[plugins.broken]\ncommand=["python","broken.py"]\n',
        }) as project:
            project.symlink("outside-tree", target=outside.root, directory=True)
            paths = {
                "source": project.root / "docs/index.md",
                "unknown": project.root / "material/blob.bin",
                "outside": outside.root / "outside.bin",
            }
            with self.traceFileAccess(paths) as trace, project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                initial = trace.take()
                self.assertTrue(any(name == "source" for name, _ in initial), initial)
                self.assertFalse(any(name == "unknown" for name, _ in initial), initial)
                self.assertFalse(any(name == "outside" for name, _ in initial), initial)
                time.sleep(1.6)
                self.assertEqual(trace.take(), [])
                self.assertWatchDiagnostics(watch, contains=["watch: backend native"])
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
