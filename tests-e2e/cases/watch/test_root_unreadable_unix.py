# root 本身不可读时，观察范围无法保持；不能把这类失败显示为可修复等待。
from support import E2ECase


class RootUnreadable(E2ECase):
    specs = ("SPEC-CLI-008",)
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """普通用户 watch 的 root 失去读取权限后以 1 退出，保留已发布文件"""
        with self.project({"a.rs": "// Initial page\n"}, parent="/tmp") as project:
            with self.ordinaryUserWatch(project, inputs=["a.rs"]) as watch:
                watch.waitForPublishedPages(1)
                saved = project.snapshot()
                try:
                    project.root.chmod(0o111)
                    result = watch.wait()
                    self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["Permission denied"])
                finally:
                    project.root.chmod(0o777)
                self.assertEqual(project.snapshot(), saved)
