# A valid check failure updates its report while preserving the previous page and index.
# {% include "tests-e2e/fixtures/watch/check_report.py" %}
from support import E2ECase


class CheckRepair(E2ECase):
    specs = ("SPEC-CLI-010", "SPEC-PLG-013", "SPEC-CLI-004", "SPEC-BLT-006")

    def test_scenario(self):
        """材料缺失时更新报告并保护旧发布，补齐材料后复用插件恢复"""
        with self.project({
            "docs/index.md": '{% include "material.md" %}\n',
            "material.md": "Before repair\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/check_report.py"),
            "source-down.toml": 'config_version=1\n[plugins.report]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                page = ".source-down/pages/docs/index.md.md"
                index = ".source-down/search/index.json"
                report = ".source-down/reports/report/status.md"
                oldPage = project.readBytes(page)
                oldIndex = project.readBytes(index)
                oldReport = project.readBytes(report)

                (project.root / "material.md").unlink()
                watch.waitForDiagnostics(contains=["checks failed; watching"])
                self.assertFileContent(project, page, oldPage)
                self.assertFileContent(project, index, oldIndex)
                self.assertNotEqual(project.readBytes(report), oldReport)

                project.writeInPlace("material.md", "After repair\n")
                watch.waitForOutputState(changed={index: oldIndex}, contains={page: "After repair"})
                found = project.sourceDown.search("repair")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"After repair", found.raw.stdout)
                self.assertFileContent(project, ".source-down/initializations", "initialize\n")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
