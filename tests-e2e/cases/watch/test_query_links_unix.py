# 查询链接改变目标时重新选择输入，越界期间保留上一轮，修复后重新发布。
from support import E2ECase


class QueryLinks(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """显式输入链接可重定向；越界时保持旧索引，修复后继续原生观察新目标"""
        with self.project({"outside.md": "Outside root\n"}) as outside, self.project({
            "docs/a.md": "First linked source\n", "docs/b.md": "Second linked source\n",
        }) as project:
            project.symlink("entry.md", target="docs/a.md")
            with project.sourceDown.watch(inputs=["entry.md"]) as watch:
                watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                replacement = project.root / ".source-down/replacement"
                replacement.symlink_to("docs/b.md")
                replacement.replace(project.root / "entry.md")
                watch.waitForOutputState(
                    filesPresent=[".source-down/pages/docs/b.md.md"],
                    absent=[".source-down/pages/docs/a.md.md"],
                )
                watch.waitForSearchOutput("Second", contains="Second linked source")
                oldIndex = project.readBytes(".source-down/search/index.json")

                replacement.symlink_to(outside.root / "outside.md")
                replacement.replace(project.root / "entry.md")
                watch.waitForDiagnostics(contains=["failure; watching"])
                self.assertFileContent(project, ".source-down/search/index.json", oldIndex)

                replacement.symlink_to("docs/b.md")
                replacement.replace(project.root / "entry.md")
                project.writeInPlace("docs/b.md", "Restored linked proof\n")
                watch.waitForOutputState(contains={
                    ".source-down/pages/docs/b.md.md": "Restored linked proof",
                })
                project.sourceDown.searchSuccessfully("Restored linked")
                self.assertNotIn(b"switching to poll", watch.stderr)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
