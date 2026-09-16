from support import E2ECase


class UnreadableInput(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """实际目录权限暂时禁止读取时保持监听，恢复权限后发布剩余输入"""
        with self.project({"docs/keep.md": "Keep reading\n", "docs/locked/page.md": "Locked chapter\n"}, parent="/tmp") as project:
            locked = project.root / "docs/locked"
            with self.ordinaryUserWatch(project, inputs=["docs"]) as watch:
                watch.waitForPublishedPages(2)
                saved = project.snapshot()
                try:
                    locked.chmod(0)
                    watch.waitForDiagnostics(contains=["failure; watching"])
                    self.assertEqual(project.snapshot(), saved)
                    project.writeInPlace("docs/keep.md", "Keep repaired\n")
                    locked.chmod(0o755)
                    watch.waitForOutputState(contains={
                        ".source-down/pages/docs/keep.md.md": "Keep repaired",
                    })
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
                finally:
                    locked.chmod(0o755)
