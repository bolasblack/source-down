# {% include "tests-e2e/fixtures/watch/notify_failure.c" %}
# 真实 inotify_init1 返回 EMFILE 时自动降级为轮询并继续发布。
from support import E2ECase


class NativeFallback(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """原生通知初始化资源耗尽时说明原因，切换一次轮询并持续更新"""
        with self.notificationInitializationFault() as fault, self.project({
            "docs/index.md": "Fallback before\n",
        }) as project:
            record = fault.root / "fallback.calls"
            with project.sourceDown.watch(inputs=["docs"], env=fault.environment(record=record)) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                self.assertWatchDiagnostics(watch, contains=[
                    "watch: backend poll", "switching to poll", "Too many open files",
                ])
                self.assertEqual(record.read_bytes(), b"init\n")
                project.writeInPlace("docs/index.md", "Fallback after\n")
                watch.waitForOutputState(contains={".source-down/pages/docs/index.md.md": "Fallback after"})
                self.assertEqual(watch.stderr.count(b"switching to poll"), 1)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
