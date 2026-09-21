# 静态命令约束拒绝启动，不能进入等待修复的 watch 循环。
from support import E2ECase


class WatchStartupErrors(E2ECase):
    specs = ("SPEC-CLI-008",)

    def test_scenario(self):
        """缺少输入、未知参数、无效 root 和字面越界查询都以 2 退出"""
        with self.project({"a.rs": "// Page\n"}) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            commands = [
                ["watch", "--root", project.root],
                ["watch", "a.rs", "--unknown", "--root", project.root],
                ["watch", "a.rs", "--root", project.root / "missing"],
                ["watch", "a.rs", "--root", project.root / "a.rs"],
                ["watch", "../outside.rs", "--root", project.root],
            ]
            for arguments in commands:
                with self.subTest(arguments=[str(value) for value in arguments]):
                    result = self.context.command([self.context.binary, *arguments], cwd=project.root)
                    self.assertRunResult(result, exitCode=2, stdout=b"")
                    self.assertNotIn(b"watch round", result.stderr)
                    self.assertOutputUnchanged(project, since=published)
