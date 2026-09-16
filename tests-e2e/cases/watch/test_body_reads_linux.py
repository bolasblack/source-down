# 真实 inotify 访问事件证明健康 watch 空闲不重读正文，也不读取未知材料。
import time
from support import E2ECase


class NativeBodyReads(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """健康原生 watch 只在轮次读取选中正文，空闲时不扫描任何正文"""
        with self.project({"outside.bin": b"outside material\n"}) as outside, self.project({
            "docs/index.md": "Initial body\n",
            "material/blob.bin": bytes(range(256)) * 4096,
            "broken.py": "raise SystemExit(9)\n",
        }) as project:
            project.symlink("outside-tree", target=outside.root, directory=True)
            paths = {
                "source": project.root / "docs/index.md",
                "unknown": project.root / "material/blob.bin",
                "outside": outside.root / "outside.bin",
            }
            with self.traceFileAccess(paths) as trace, project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                initial = trace.take()
                self.assertTrue(any(name == "source" for name, _ in initial), initial)
                self.assertFalse(any(name == "unknown" for name, _ in initial), initial)
                self.assertFalse(any(name == "outside" for name, _ in initial), initial)
                time.sleep(1.6)
                self.assertEqual(trace.take(), [])
                self.assertWatchDiagnostics(watch, contains=["watch: backend native"])

                project.writeInPlace("docs/index.md", "Updated body\n")
                trace.take()
                watch.waitForOutputState(contains={".source-down/pages/docs/index.md.md": "Updated body"})
                changed = trace.take()
                self.assertTrue(any(name == "source" and mask & 0x01 for name, mask in changed), changed)
                self.assertFalse(any(name == "unknown" for name, _ in changed), changed)
                self.assertFalse(any(name == "outside" for name, _ in changed), changed)
                time.sleep(1.1)
                self.assertEqual(trace.take(), [])
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
