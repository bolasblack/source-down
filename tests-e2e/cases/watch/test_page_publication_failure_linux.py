# 页面写入后的真实 statx EIO 保留旧索引；释放后下一轮清理部分页面。
# {% include "tests-e2e/fixtures/watch/publication.c" %}
from support import E2ECase


class PagePublicationFailure(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """页面发布失败保留已完成范围，释放故障后准确清理并更新索引"""
        with self.project({
            "docs/keep.md": "Keep chapter\n",
            "docs/obsolete.md": "Obsolete\n",
            "docs/z.md": "Last chapter\n",
        }) as project:
            with self.publicationFault(project, mode="page") as fault:
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
                        self.assertWatchDiagnostics(watch, contains=["completed:"])
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
