# 同路径、同成员名的新目录不能沿用已失效的内核订阅；高事件量后仍可继续编辑。
import shutil
from support import E2ECase


class DirectoryReplacement(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """高事件量和同名目录整体替换后，新目录中的后续编辑继续更新准确页面与索引"""
        with self.project({"docs/chapter.md": "Original chapter\n", "docs/keep.md": "Keep\n"}) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                self.assertWatchDiagnostics(watch, contains=["watch: backend native"])
                for number in range(4500):
                    project.writeFiles({f"unselected/event-{number}.txt": "An ordinary material\n"})
                (project.root / "docs").rename(project.root / "retired")
                project.writeFiles({"docs/chapter.md": "Replacement chapter\n", "docs/keep.md": "Keep\n"})
                shutil.rmtree(project.root / "retired")
                page = ".source-down/pages/docs/chapter.md.md"
                watch.waitForOutputState(contains={page: "Replacement chapter"})
                project.writeInPlace("docs/chapter.md", "Later edit in new directory\n")
                watch.waitForOutputState(contains={page: "Later edit in new directory"})
                found = project.sourceDown.search("Later edit")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"Later edit in new directory", found.raw.stdout)
                self.assertNotIn(b"switching to poll", watch.stderr)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
