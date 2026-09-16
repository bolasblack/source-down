# 加载时默认配置暂缺，恢复同一文件后必须使用该配置生成，不能保留默认 Session。
# {% include "tests-e2e/fixtures/watch/configuration_window.c" %}
# {% include "tests-e2e/fixtures/watch/configuration_window.py" %}
import time
from support import E2ECase


class AbsentConfigurationReadWindow(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011")
    platforms = ("linux",)

    def test_scenario(self):
        """默认配置在 Session 加载时暂缺，原文件恢复后重载并发布正确插件结果"""
        with self.project({
            "docs/index.md": "Configuration presence proof\n",
            "source-down.toml": (
                'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n'
                '[plugins.observe.options]\nlabel="A"\n'
            ),
            "plugin.py": self.fixture("watch/configuration_window.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
        }) as project, self.configurationReadWindow(project, afterLoaded=True) as window:
            project.writeFiles({".source-down/plugin.release": "continue"})
            with project.sourceDown.watch(inputs=["docs"], env=window.environment) as watch:
                try:
                    window.waitUntilPaused(watch)
                    project.replaceFile(".source-down/parked.toml", fromPath="source-down.toml")
                    window.release()
                    window.waitUntilLoaded(watch)
                    self.assertFalse((project.root / ".source-down/initializations").exists())
                    project.replaceFile("source-down.toml", fromPath=".source-down/parked.toml")
                    window.releaseLoaded()

                    watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                    self.assertIn(b"Loaded A", project.readBytes(".source-down/pages/docs/index.md.md"))
                    self.assertFileContent(project, ".source-down/initializations", "A\n")
                    self.assertFileContent(project, ".source-down/batches", "A\n")
                    found = project.sourceDown.searchSuccessfully("Loaded A")
                    self.assertIn(b"Loaded A", found.raw.stdout)
                    time.sleep(1.1)
                    self.assertFileContent(project, ".source-down/batches", "A\n")
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130, stdout=b"")
                finally:
                    window.release()
                    window.releaseLoaded()
