# Selection order and duplicate inputs do not change a valid adoption scope.
from support import E2ECase


class ReorderedPageAdoption(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """同范围参数重排并重复时仍接管未修改的旧页"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/obsolete.md": "Obsolete chapter\n",
            "extra.md": "Extra chapter\n",
        }) as project:
            published = project.sourceDown.render(inputs=["docs", "extra.md"])
            self.assertRunResult(published, exitCode=0)
            obsoletePage = ".source-down/pages/docs/obsolete.md.md"
            (project.root / "docs/obsolete.md").unlink()

            with project.sourceDown.watch(inputs=["extra.md", "docs", "docs"]) as watch:
                watch.waitForDiagnostics(contains=["watch round 1: published"])
                self.assertPathAbsent(project, obsoletePage)
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
