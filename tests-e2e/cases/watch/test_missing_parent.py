# include 的已知缺失查询必须覆盖最近安全祖先，不能要求新父目录再产生一次编辑。
from support import E2ECase


class MissingParent(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-BLT-006")

    def test_scenario(self):
        """排除目录中的已知材料连父目录都不存在时，一次创建完整目录和材料即可恢复"""
        with self.project({"docs/index.md": '{% include "target/new/material.md" %}\n'}) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["checks failed; watching"])
                self.assertWatchDiagnostics(watch, contains=["watch: backend native"])

                # target/new and the known material are created by this single write.
                project.writeFiles({"target/new/material.md": "Recovered missing parents\n"})
                watch.waitForOutputState(filesPresent=[
                    ".source-down/pages/docs/index.md.md",
                ])
                self.assertIn(b"Recovered missing parents", project.readBytes(".source-down/pages/docs/index.md.md"))
                project.sourceDown.searchSuccessfully("Recovered")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
