# {% include "tests-e2e/fixtures/watch/notify_failure.c" %}
# 原生初始化真实阻塞时取消；释放后只能退出，不能发布任何索引。
from support import E2ECase


class FallbackCancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)

    def test_scenario(self):
        """通知初始化阻塞窗口中取消，返回 EMFILE 后退出 130 且没有发布"""
        with self.notificationInitializationFault() as fault, self.project({
            "docs/index.md": "Cancel before fallback\n",
        }) as project:
            record = fault.root / "cancel.calls"
            release = fault.root / "cancel.release"
            with project.sourceDown.watch(inputs=["docs"],
                                          env=fault.environment(record=record, release=release)) as watch:
                try:
                    watch.waitForOutputState(filesPresent=[record])
                    watch.interrupt()
                    fault.release()
                    self.assertRunResult(watch.wait(), exitCode=130)
                    self.assertFalse((project.root / ".source-down/search/index.json").exists())
                finally:
                    fault.release()
