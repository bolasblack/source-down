# 参数边界先于目标查询；失败后保留最近成功发布的完整输出。
from support import E2ECase


class LinkArguments(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-004")

    def test_scenario(self):
        """link 接受页面路径，未知参数和非法路径均明确失败"""
        with self.project({
            "index.md": '{% link "details.md" %}\n',
            "details.md": "",
        }) as project:
            published = project.sourceDown.render(inputs=["index.md", "details.md"])
            self.assertRunResult(published, exitCode=0)

            for arguments in (
                '"details.md" text="下一篇"',
                '"details.md" title="Title"',
                '"details.md" anchor="section"',
                '"details.md" id="Heading"',
                '"details.md" lines=[1,2]',
                "",
                "null",
                '"details.md" "index.md"',
                '"../details.md"',
            ):
                with self.subTest(arguments=arguments):
                    project.writeInPlace("index.md", "{% link " + arguments + " %}\n")
                    rejected = project.sourceDown.render(inputs=["index.md", "details.md"])
                    self.assertRunResult(rejected, exitCode=1, stdout=b"", stderrContains=[
                        "error invalid_arguments:",
                    ])
                    self.assertOutputUnchanged(project, since=published)
