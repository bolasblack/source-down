# A valid index from the same selection grants ownership of an unchanged old page.
from support import E2ECase


class PageAdoption(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """同范围有效索引接管未修改的旧页，并在输入退出后删除该页"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/obsolete.md": "Obsolete chapter\n",
            "extra.md": "Extra chapter\n",
        }) as project:
            published = project.sourceDown.render(inputs=["docs", "extra.md"])
            self.assertRunResult(published, exitCode=0)
            obsoletePage = ".source-down/pages/docs/obsolete.md.md"
            (project.root / "docs/obsolete.md").unlink()

            with project.sourceDown.watch(inputs=["docs", "extra.md"]) as watch:
                watch.waitForPublishedPages(2)
                self.assertPathAbsent(project, obsoletePage)
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
