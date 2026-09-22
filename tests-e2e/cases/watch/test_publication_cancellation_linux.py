# z 页检查处注入真实 SIGINT；取消保留已经完成的页与旧索引并退出 130。
# {% include "tests-e2e/fixtures/watch/publication.c" %}
from support import E2ECase


class PublicationCancellation(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """发布到部分页面时收到真实中断，保留完成范围与旧索引并退出 130"""
        with self.project({
            "docs/keep.md": "Keep chapter\n",
            "docs/obsolete.md": "Obsolete\n",
            "docs/z.md": "Last chapter\n",
        }) as project:
            with self.publicationFault(project, mode="cancel") as fault:
                prepared = project.sourceDown.render(inputs=["docs"])
                self.assertRunResult(prepared, exitCode=0)
                with project.sourceDown.watch(inputs=["docs"], env=fault.environment) as watch:
                    try:
                        watch.waitForPublishedPages(3)
                        oldIndex = project.readBytes(".source-down/search/index.json")
                        project.writeInPlace("docs/a.md", "New owned chapter\n")
                        (project.root / "docs/obsolete.md").unlink()

                        self.assertRunResult(watch.wait(), exitCode=130)
                        self.assertFilesPresent(project, [".source-down/pages/docs/a.md.md"])
                        self.assertFileContent(project, ".source-down/search/index.json", oldIndex)
                        self.assertWatchDiagnostics(watch, contains=["completed:"])
                        self.assertFalse(any(".tmp" in name for name in project.snapshot()))
                    finally:
                        fault.release()
