# {% include "tests-e2e/fixtures/watch/notify_failure.c" %}
# 显式 --poll 必须绕过原生初始化；故障 shim 的调用记录因此不存在。
from support import E2ECase


class ExplicitPolling(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """显式轮询从不调用真实原生初始化，且正文修改继续发布"""
        with self.notificationInitializationFault() as fault, self.project({
            "docs/index.md": "Fallback before\n",
        }) as project:
            record = fault.root / "explicit.calls"
            environment = fault.environment(record=record)
            with project.sourceDown.watchCommand(
                ["watch", "docs", "--root", project.root, "--poll"], env=environment,
            ) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                self.assertWatchDiagnostics(watch, contains=["watch: backend poll"])
                self.assertFalse(record.exists())
                project.writeInPlace("docs/index.md", "Fallback after\n")
                watch.waitForOutputState(contains={".source-down/pages/docs/index.md.md": "Fallback after"})
                self.assertEqual(watch.stderr.count(b"switching to poll"), 0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
