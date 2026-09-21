# 原生访问事件只用于观察真实 poll 的文件读取，不参与产品的变更检测。
# {% include "tests-e2e/fixtures/watch/poll_scope.py" %}
import time
from support import E2ECase


class PollScope(E2ECase):
    specs = ("SPEC-CLI-009",)
    platforms = ("linux",)

    def test_scenario(self):
        """健康轮询只读输入和依赖，故障等待额外扫描恢复正文，未知材料变化后恢复"""
        with self.project({"outside.bin": b"outside"}) as outside, self.project({
            "docs/index.md": "Original page\n", "known.bin": b"known",
            "material/blob.bin": b"unknown", "target/ignored.bin": b"excluded",
            ".source-down/events": b"",
            "plugin.py": self.fixture("watch/poll_scope.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.observer]\ncommand=['python','plugin.py']\n",
        }) as project:
            project.symlink("outside-tree", target=outside.root, directory=True)
            paths = {"source": project.root / "docs/index.md", "known": project.root / "known.bin",
                     "unknown": project.root / "material/blob.bin", "excluded": project.root / "target/ignored.bin",
                     "outside": outside.root / "outside.bin"}
            with self.traceFileAccess(paths) as trace, project.sourceDown.watch(inputs=["docs"], poll=True) as watch:
                watch.waitForPublishedPages(1)
                self.assertWatchDiagnostics(watch, contains=["backend poll"])
                time.sleep(0.4)
                trace.take()  # Per-attempt recovery baselines may read unknown files.
                before = project.readBytes(".source-down/events")
                oldPage = project.readBytes(".source-down/pages/docs/index.md.md")
                oldIndex = project.readBytes(".source-down/search/index.json")
                time.sleep(1.1)
                healthy = {name for name, mask in trace.take() if mask & 0x01}
                self.assertEqual(healthy, {"source", "known"})
                self.assertEqual(project.readBytes(".source-down/events"), before)

                # The failed plugin never opens blob.bin; subsequent access is the recovery scan.
                checkpoint = watch.checkpoint()
                project.writeFiles({".source-down/fail": "crash"})
                project.writeInPlace("docs/index.md", "Changed page!\n")
                watch.waitForDiagnostics(contains=["execution failure; watching"], since=checkpoint)
                trace.take()
                failedEvents = project.readBytes(".source-down/events")
                time.sleep(1.1)
                failed = {name for name, mask in trace.take() if mask & 0x01}
                self.assertEqual(failed, {"source", "known", "unknown"})
                self.assertEqual(project.readBytes(".source-down/events"), failedEvents)
                self.assertEqual(project.readBytes(".source-down/pages/docs/index.md.md"), oldPage)
                self.assertEqual(project.readBytes(".source-down/search/index.json"), oldIndex)

                project.removeFile(".source-down/fail")
                project.writeInPlace("material/blob.bin", b"repair!")
                watch.waitForOutputState(contains={".source-down/pages/docs/index.md.md": "Changed page!"})
                time.sleep(0.4)
                trace.take()
                time.sleep(1.1)
                self.assertEqual({name for name, mask in trace.take() if mask & 0x01}, {"source", "known"})
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
