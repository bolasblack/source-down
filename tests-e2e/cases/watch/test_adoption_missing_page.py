# A missing old page is already in the correct state and must not prevent publication.
from support import E2ECase


class MissingPageAdoption(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """同范围输入与旧页都已删除时仍能接管并继续发布"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/obsolete.md": "Obsolete chapter\n",
            "extra.md": "Extra chapter\n",
        }) as project:
            published = project.sourceDown.render(inputs=["docs", "extra.md"])
            self.assertRunResult(published, exitCode=0)
            obsoletePage = ".source-down/pages/docs/obsolete.md.md"
            (project.root / "docs/obsolete.md").unlink()
            (project.root / obsoletePage).unlink()

            with project.sourceDown.watch(inputs=["docs", "extra.md"]) as watch:
                watch.waitForDiagnostics(contains=["watch round 1: published"])
                self.assertPathAbsent(project, obsoletePage)
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
