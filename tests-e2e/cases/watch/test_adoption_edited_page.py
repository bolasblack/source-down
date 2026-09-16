# Author edits revoke deletion ownership even when the old index is otherwise valid.
from support import E2ECase


class EditedPageNotAdopted(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """作者修改过的旧页保持原字节且不会被接管删除"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/obsolete.md": "Obsolete chapter\n",
            "extra.md": "Extra chapter\n",
        }) as project:
            published = project.sourceDown.render(inputs=["docs", "extra.md"])
            self.assertRunResult(published, exitCode=0)
            obsoletePage = ".source-down/pages/docs/obsolete.md.md"
            (project.root / "docs/obsolete.md").unlink()
            project.writeFiles({obsoletePage: "The author owns this edited page\n"})
            authorBytes = project.readBytes(obsoletePage)

            with project.sourceDown.watch(inputs=["docs", "extra.md"]) as watch:
                watch.waitForDiagnostics(contains=["watch round 1: published"])
                self.assertFileContent(project, obsoletePage, authorBytes)
                self.assertWatchDiagnostics(watch, contains=["not adopting"])
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
