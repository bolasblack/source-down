# {% include "tests-e2e/fixtures/watch/scan.c" %}
# 下一轮 baseline 读取暂停时主动取消，释放系统调用后回收插件并退出。
# {% include "tests-e2e/fixtures/watch/baseline_health.py" %}
from support import E2ECase


class BaselineCancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """baseline 读取窗口中的取消在释放后退出 130 并回收插件"""
        with self.project({
            "docs/index.md": "Previous published body\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/baseline_health.py"),
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project, self.scanBaselineWindow(project) as baseline:
            with project.sourceDown.watch(inputs=["docs"], env=baseline.environment) as watch:
                try:
                    watch.waitForPublishedPages(1)
                    project.readBytes(".source-down/search/index.json")
                    child = int(project.readBytes(".source-down/plugin.pid"))
                    baseline.arm()
                    project.writeInPlace("docs/index.md", "Pending baseline body\n")
                    baseline.waitUntilPaused(watch)
                    watch.interrupt()
                    baseline.release()
                    self.assertRunResult(watch.wait(), exitCode=130)
                    self.assertProcessReaped(child)
                finally:
                    baseline.release()
