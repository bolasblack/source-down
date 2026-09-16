# A corrupt snapshot identity cannot confer deletion ownership over an old page.
import json
from support import E2ECase


class CorruptIndexNotAdopted(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """损坏索引身份时保留旧页并拒绝接管"""
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
            index = json.loads(project.readBytes(".source-down/search/index.json"))
            index["snapshot"] = "0" * 64
            project.writeFiles({".source-down/search/index.json": json.dumps(index)})

            with project.sourceDown.watch(inputs=["docs", "extra.md"]) as watch:
                watch.waitForDiagnostics(contains=["watch round 1: published"])
                self.assertFileContent(project, obsoletePage, oldPage)
                self.assertWatchDiagnostics(watch, contains=["not adopting"])
                self.assertRunResult(project.sourceDown.search("Keep"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
