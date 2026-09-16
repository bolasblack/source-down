# Matching bytes never grant permission to delete a link that points at real source.
import os
from support import E2ECase


class AdoptionLinks(E2ECase):
    specs = ("SPEC-CLI-007", "SPEC-CLI-012", "SPEC-SRH-002")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """旧页替换为真实源码的软链接或硬链接后保持链接身份和目标字节"""
        for linkKind in ("symlink", "hardlink"):
            with self.subTest(link=linkKind), self.project({
                "docs/keep.md": "Identical source\n",
                "docs/obsolete.md": "Identical source\n",
            }) as project:
                published = project.sourceDown.render(inputs=["docs"])
                self.assertRunResult(published, exitCode=0)

                obsoletePage = project.root / ".source-down/pages/docs/obsolete.md.md"
                oldBytes = project.readBytes(obsoletePage)
                obsoletePage.unlink()
                realSource = project.root / "docs/keep.md"
                realSource.write_bytes(oldBytes)
                if linkKind == "symlink":
                    obsoletePage.symlink_to(realSource)
                else:
                    os.link(realSource, obsoletePage)
                linkInode = obsoletePage.lstat().st_ino
                (project.root / "docs/obsolete.md").unlink()

                with project.sourceDown.watch(inputs=["docs"]) as watch:
                    watch.waitForPublishedPages(1)
                    self.assertEqual(obsoletePage.lstat().st_ino, linkInode)
                    self.assertFileContent(project, obsoletePage, oldBytes)
                    self.assertFileContent(project, realSource, oldBytes)
                    self.assertWatchDiagnostics(watch, contains=["not adopting"])
                    self.assertRunResult(project.sourceDown.search("Identical"), exitCode=0)
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
