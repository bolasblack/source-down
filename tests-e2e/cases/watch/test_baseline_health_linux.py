# {% include "tests-e2e/fixtures/watch/scan.c" %}
# 下一轮 baseline 读取暂停时插件退出；旧发布保持，项目修复后继续发布。
# {% include "tests-e2e/fixtures/watch/baseline_health.py" %}
from support import E2ECase


class BaselineHealth(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-008")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """baseline 读取中插件退出，故障被回收且旧索引保持，修复后恢复"""
        with self.project({
            "docs/index.md": "Previous published body\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/baseline_health.py"),
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project, self.scanBaselineWindow(project) as baseline:
            with project.sourceDown.watch(inputs=["docs"], env=baseline.environment) as watch:
                try:
                    watch.waitForPublishedPages(1)
                    index = ".source-down/search/index.json"
                    oldIndex = project.readBytes(index)
                    child = int(project.readBytes(".source-down/plugin.pid"))
                    baseline.arm()
                    project.writeInPlace("docs/index.md", "Pending baseline body\n")
                    baseline.waitUntilPaused(watch)

                    project.writeInPlace(".source-down/die", "exit")
                    watch.waitForProcessExit(child)
                    baseline.release()
                    watch.waitForDiagnostics(contains=["execution failure; watching"])
                    self.assertFileContent(project, index, oldIndex)
                    self.assertProcessReaped(child)

                    project.removeFile(".source-down/die")
                    project.writeInPlace("docs/index.md", "Recovered baseline proof\n")
                    watch.waitForOutputState(changed={index: oldIndex})
                    found = project.sourceDown.search("Recovered baseline")
                    self.assertRunResult(found, exitCode=0)
                    child = int(project.readBytes(".source-down/plugin.pid"))
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
                    self.assertProcessReaped(child)
                finally:
                    baseline.release()
