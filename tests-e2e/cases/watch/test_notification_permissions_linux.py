# 可遍历但不可列举的目录允许读取已知文件；观察器不能在登记失败后声称已覆盖它。
from support import E2ECase


class NotificationPermissions(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009")
    platforms = ("linux",)

    def test_scenario(self):
        """显式输入可读但其父目录不允许原生登记时，说明权限原因并用安全轮询继续更新"""
        with self.project({"docs/locked/page.md": "Readable before\n"}, parent="/tmp") as project:
            locked = project.root / "docs/locked"
            try:
                locked.chmod(0o111)
                with self.ordinaryUserWatch(project, inputs=["docs/locked/page.md"]) as watch:
                    watch.waitForDiagnostics(contains=["pages; watching"])
                    self.assertWatchDiagnostics(watch, contains=[
                        "Permission denied",
                        "switching to poll",
                    ])

                    project.writeInPlace("docs/locked/page.md", "Readable after\n")
                    watch.waitForOutputState(contains={
                        ".source-down/pages/docs/locked/page.md.md": "Readable after",
                    })
                    project.sourceDown.searchSuccessfully("Readable")
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
            finally:
                locked.chmod(0o755)
