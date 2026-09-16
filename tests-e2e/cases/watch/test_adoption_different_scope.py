# A valid old index for a broader selection cannot authorize a narrower watch scope.
from support import E2ECase


class DifferentScopeNotAdopted(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """不同选择范围不能接管旧页或删除其字节"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/obsolete.md": "Obsolete chapter\n",
            "extra.md": "Extra chapter\n",
        }) as project:
            published = project.sourceDown.render(inputs=["docs", "extra.md"])
            self.assertRunResult(published, exitCode=0)
            obsoletePage = ".source-down/pages/docs/obsolete.md.md"
            (project.root / "docs/obsolete.md").unlink()
            oldPage = project.readBytes(obsoletePage)

            with project.sourceDown.watch(inputs=["docs/keep.md", "extra.md"]) as watch:
                watch.waitForDiagnostics(contains=["watch round 1: published"])
                self.assertFileContent(project, obsoletePage, oldPage)
                self.assertWatchDiagnostics(watch, contains=["not adopting"])
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
