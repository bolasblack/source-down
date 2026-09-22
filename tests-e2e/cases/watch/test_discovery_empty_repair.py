# 最后一个有效输入消失时保留旧产物；其他未选中成员不改变这一事实。
# {% include "tests-e2e/fixtures/watch/observer.py" %}
from support import E2ECase


class EmptyDiscoveryRepair(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012")

    def test_scenario(self):
        """最后输入删除时完整保留发布，恢复有效输入后旧页退出"""
        with self.project({
            "docs/index.md": "Last chapter\n",
            "docs/target/ignored.md": "Not selected\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/observer.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            project.makeDirectory("docs/new-directory")
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForPublishedPages(1)
                saved = project.snapshot()
                failure = watch.checkpoint()
                project.removeFile("docs/index.md")
                watch.waitForDiagnostics(contains=["no supported source files selected", "failure; watching"],
                                         since=failure)
                self.assertEqual(project.snapshot(), saved)

                restored = watch.checkpoint()
                project.writeInPlace("docs/restored.py", "# Restored chapter\nvalue = 1\n")
                watch.waitForOutputState(filesPresent=[".source-down/pages/docs/restored.py.md"])
                watch.waitForOutputState(absent=[".source-down/pages/docs/index.md.md"])
                watch.waitForPublishedPages(1, since=restored)
                found = project.sourceDown.search("Restored")
                self.assertRunResult(found, exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
