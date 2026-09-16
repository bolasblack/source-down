# 默认排除目录的成员变化不能触发插件批次。
# {% include "tests-e2e/fixtures/watch/observer.py" %}
import time
from support import E2ECase


class ExcludedDiscovery(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012")

    def test_scenario(self):
        """排除目录中新增文件静置一段时间后仍不触发轮次"""
        with self.project({
            "docs/index.md": "Last chapter\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/observer.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            project.makeDirectory("docs/new-directory")
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForPublishedPages(1)
                events = project.readBytes(".source-down/observer.events")
                project.writeFiles({"docs/target/ignored.md": "Not selected\n"})
                time.sleep(1.2)
                self.assertFileContent(project, ".source-down/observer.events", events)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
