# 配置在基线与 Session 读取之间变为 B，初始化后回到 A；稳定后须重建并发布 A。
# {% include "tests-e2e/fixtures/watch/configuration_window.c" %}
# {% include "tests-e2e/fixtures/watch/configuration_window.py" %}
import time
from support import E2ECase


class ConfigurationReadWindow(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011")
    platforms = ("linux",)

    def test_scenario(self):
        """配置 A→B→A 的真实读取窗口结束后，重建 Session 并发布 A，空闲不重复执行"""
        configurationA = (
            'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n'
            '[plugins.observe.options]\nlabel="A"\n'
        )
        configurationB = configurationA.replace('label="A"', 'label="B"')
        with self.project({
            "docs/index.md": "Configuration reload proof\n",
            "source-down.toml": configurationA,
            "plugin.py": self.fixture("watch/configuration_window.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
        }) as project, self.configurationReadWindow(project) as window:
            with project.sourceDown.watch(inputs=["docs"], env=window.environment) as watch:
                try:
                    window.waitUntilPaused(watch)
                    project.writeInPlace("source-down.toml", configurationB)
                    window.release()
                    loaded = watch.waitForOutputState(
                        filesPresent=[".source-down/initializations"],
                        contains={".source-down/initializations": "B\n"},
                    )
                    self.assertEqual(loaded.files[".source-down/initializations"], b"B\n")
                    project.writeInPlace("source-down.toml", configurationA)
                    project.writeInPlace(".source-down/plugin.release", "continue")
                    watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                    page = project.readBytes(".source-down/pages/docs/index.md.md")
                    self.assertIn(b"Loaded A", page)
                    self.assertNotIn(b"Loaded B", page)
                    self.assertFileContent(project, ".source-down/initializations", "B\nA\n")
                    self.assertFileContent(project, ".source-down/batches", "B\nA\n")
                    found = project.sourceDown.searchSuccessfully("Loaded A")
                    self.assertIn(b"Loaded A", found.raw.stdout)
                    time.sleep(1.1)
                    self.assertFileContent(project, ".source-down/batches", "B\nA\n")
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130, stdout=b"")
                finally:
                    window.release()
