# 索引写入处的真实 statx EIO 允许页面完成，但仍保留旧索引直到下一轮。
# {% include "tests-e2e/fixtures/watch/publication.c" %}
from support import E2ECase


class IndexPublicationFailure(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """索引发布失败明确报告页面完成，释放故障后清理并更新索引"""
        with self.project({
            "docs/keep.md": "Keep chapter\n",
            "docs/obsolete.md": "Obsolete\n",
            "docs/z.md": "Last chapter\n",
        }) as project:
            with self.publicationFault(project, mode="index") as fault:
                prepared = project.sourceDown.render(inputs=["docs"])
                self.assertRunResult(prepared, exitCode=0)
                with project.sourceDown.watch(inputs=["docs"], env=fault.environment) as watch:
                    try:
                        watch.waitForPublishedPages(3)
                        oldIndex = project.readBytes(".source-down/search/index.json")
                        project.writeInPlace("docs/a.md", "New owned chapter\n")
                        (project.root / "docs/obsolete.md").unlink()

                        watch.waitForDiagnostics(contains=["publication failure; watching"])
                        self.assertFilesPresent(project, [".source-down/pages/docs/a.md.md"])
                        self.assertFileContent(project, ".source-down/search/index.json", oldIndex)
                        self.assertWatchDiagnostics(watch, contains=[
                            "completed:",
                            "pages published; index not updated",
                        ])
                        self.assertFalse(any(".tmp" in name for name in project.snapshot()))

                        fault.release()
                        (project.root / "docs/a.md").unlink()
                        watch.waitForOutputState(
                            absent=[".source-down/pages/docs/a.md.md"],
                            changed={".source-down/search/index.json": oldIndex},
                        )
                        self.assertPathAbsent(project, ".source-down/pages/docs/obsolete.md.md")
                        project.sourceDown.searchSuccessfully("Keep")
                        watch.interrupt()
                        self.assertRunResult(watch.wait(), exitCode=130)
                    finally:
                        fault.release()
