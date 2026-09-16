# 空目录成员变化本身属于目录发现输入，会触发完整的新轮次。
# {% include "tests-e2e/fixtures/watch/observer.py" %}
from support import E2ECase


class DiscoveryScope(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012")

    def test_scenario(self):
        """已发布目录中新建空子目录会触发一次完整轮次"""
        with self.project({
            "docs/index.md": "Last chapter\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/observer.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForPublishedPages(1)
                events = project.readBytes(".source-down/observer.events")
                checkpoint = watch.checkpoint()
                project.makeDirectory("docs/new-directory")
                watch.waitForOutputState(changed={".source-down/observer.events": events})
                watch.waitForPublishedPages(1, since=checkpoint)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
