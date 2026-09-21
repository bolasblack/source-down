# 单次 render 保留未选中的旧页；watch 只有在成功轮次才清理自己拥有的退出页面。
# {% include "tests-e2e/fixtures/search/directory_facts.py" %}
from support import E2ECase
from support.protocol import writeReportReply
from cases.search.fixtures import directoryFactsPluginFiles


class ObsoletePageCheckFailure(E2ECase):
    specs = ("SPEC-CLI-012",)

    def test_scenario(self):
        """成功 render 缩小选择不删旧页，watch 检查失败保留退出页，修复后才删除"""
        with self.project({
            "docs/a.md": "Keep page\n", "docs/b.md": "Obsolete page\n",
            **directoryFactsPluginFiles(self, dependencies=[{"kind": "file", "path": "state.txt"}]),
        }) as project:
            writeReportReply(project, reports={}, diagnostics=[])
            project.sourceDown.renderSuccessfully(inputs=["docs"])
            obsolete = ".source-down/pages/docs/b.md.md"
            oldPage = project.readBytes(obsolete)
            project.sourceDown.renderSuccessfully(inputs=["docs/a.md"])
            self.assertFileContent(project, obsolete, oldPage)

            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForPublishedPages(2)
                index = ".source-down/search/index.json"
                oldIndex = project.readBytes(index)
                checkpoint = watch.checkpoint()
                writeReportReply(project, reports={}, diagnostics=[{
                    "severity": "error", "code": "check.failed", "message": "Repair required", "sources": [],
                }])
                watch.waitForDiagnostics(contains=["checks failed; watching"], since=checkpoint)

                checkpoint = watch.checkpoint()
                project.removeFile("docs/b.md")
                watch.waitForDiagnostics(contains=["checks failed; watching"], since=checkpoint)
                self.assertFileContent(project, obsolete, oldPage)
                self.assertFileContent(project, index, oldIndex)

                writeReportReply(project, reports={}, diagnostics=[])
                repaired = watch.waitForOutputState(absent=[obsolete], changed={index: oldIndex})
                self.assertIndexManifest(repaired.files[index], fields={"input_files": ["docs/a.md"]})
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
