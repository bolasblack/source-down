# 两个配置目标具有相同 inode 和字节，链接链仍是配置读取事实的一部分。
# {% include "tests-e2e/fixtures/watch/configuration_window.c" %}
# {% include "tests-e2e/fixtures/watch/configuration_window.py" %}
import time
from support import E2ECase


class LinkedConfigurationReadWindow(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """配置链接在读取时临时指向同字节硬链接，恢复原链后仍重建 Session"""
        with self.project({
            "docs/index.md": "Configuration link proof\n",
            "target/config-a.toml": (
                'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n'
                '[plugins.observe.options]\nlabel="A"\n'
            ),
            "plugin.py": self.fixture("watch/configuration_window.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
        }) as project, self.configurationReadWindow(project) as window:
            project.hardlink("target/config-b.toml", target="target/config-a.toml")
            project.symlink("source-down.toml", target="target/config-a.toml")
            with project.sourceDown.watch(inputs=["docs"], env=window.environment) as watch:
                try:
                    window.waitUntilPaused(watch)
                    project.replaceFile(".source-down/original-config", fromPath="source-down.toml")
                    project.symlink("source-down.toml", target="target/config-b.toml")
                    window.release()
                    watch.waitForOutputState(
                        filesPresent=[".source-down/initializations"],
                        contains={".source-down/initializations": "A\n"},
                    )
                    project.replaceFile("source-down.toml", fromPath=".source-down/original-config")
                    project.writeInPlace(".source-down/plugin.release", "continue")

                    watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                    self.assertFileContent(project, ".source-down/initializations", "A\nA\n")
                    self.assertFileContent(project, ".source-down/batches", "A\nA\n")
                    self.assertIn(b"Loaded A", project.readBytes(".source-down/pages/docs/index.md.md"))
                    found = project.sourceDown.searchSuccessfully("Loaded A")
                    self.assertIn(b"Loaded A", found.raw.stdout)
                    time.sleep(1.1)
                    self.assertFileContent(project, ".source-down/batches", "A\nA\n")
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130, stdout=b"")
                finally:
                    window.release()
