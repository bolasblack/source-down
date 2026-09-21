# A valid check failure updates its report while preserving the previous page and index.
# {% include "tests-e2e/fixtures/watch/check_report.py" %}
from support import E2ECase


class CheckRepair(E2ECase):
    specs = ("SPEC-CLI-010", "SPEC-PLG-013", "SPEC-CLI-004", "SPEC-BLT-006", "SPEC-CLI-005", "SPEC-CLI-011")

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
                initial = watch.waitForDiagnostics(contains=["pages; watching"])
                self.assertIn(b"source-down: report .source-down/reports/report/status.md\n", initial.stderr)
                page = ".source-down/pages/docs/index.md.md"
                index = ".source-down/search/index.json"
                report = ".source-down/reports/report/status.md"
                oldPage = project.readBytes(page)
                oldIndex = project.readBytes(index)
                oldReport = project.readBytes(report)

                checkpoint = watch.checkpoint()
                (project.root / "material.md").unlink()
                failed = watch.waitForDiagnostics(contains=["checks failed; watching"], since=checkpoint)
                self.assertIn(b"source-down: report .source-down/reports/report/status.md\n", failed.stderr)
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
