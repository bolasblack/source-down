# 输出树的普通编辑不触发生成；具体发布阻断路径的修复必须能触发恢复。
from support import E2ECase


class PublicationRepair(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """发布目标被目录占用时保留旧产物，修复该生成树内路径后自动发布并更新搜索"""
        with self.project({"docs/keep.md": "Keep reading\n"}) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForPublishedPages(1)
                oldIndex = project.readBytes(".source-down/search/index.json")
                oldPage = project.readBytes(".source-down/pages/docs/keep.md.md")
                blocked = project.root / ".source-down/pages/docs/added.md.md"
                blocked.mkdir()
                project.writeInPlace("docs/added.md", "The repaired publication\n")
                watch.waitForDiagnostics(contains=["publication failure; watching"])
                self.assertFileContent(project, ".source-down/search/index.json", oldIndex)
                self.assertFileContent(project, ".source-down/pages/docs/keep.md.md", oldPage)

                blocked.rmdir()
                watch.waitForOutputState(
                    filesPresent=[".source-down/pages/docs/added.md.md"],
                    changed={".source-down/search/index.json": oldIndex},
                )
                found = project.sourceDown.searchSuccessfully("repaired")
                self.assertIn(b"The repaired publication", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
