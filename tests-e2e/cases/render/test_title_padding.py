# 合法源文件名以反引号或空格开头时，标题 code span 增加独立定界空格。
from support import E2ECase


class TitlePadding(E2ECase):
    specs = ("SPEC-REN-007",)

    def test_scenario(self):
        """实际含前导空格和反引号的源文件各自发布精确标题，空正文不改变路径身份"""
        expected = {
            "`ticks.rs": b"# `` `ticks.rs ``\n\n",
            " leading.py": b"# `  leading.py `\n\n",
            "``double`.ml": b"# ``` ``double`.ml ```\n\n",
            "ordinary.rs": b"# `ordinary.rs`\n\n",
        }
        with self.project({path: "" for path in expected}) as project:
            rendered = project.sourceDown.renderSuccessfully(inputs=list(expected))
            self.assertEqual({path for path in project.snapshot() if path.startswith("pages/")},
                             {f"pages/{path}.md" for path in expected})
            for path, title in expected.items():
                with self.subTest(path=path):
                    self.assertEqual(project.readBytes(f".source-down/pages/{path}.md"), title)
                    self.assertEqual(project.readBytes(path), b"")
            project.sourceDown.renderSuccessfully(inputs=list(expected))
            self.assertOutputUnchanged(project, since=rendered)
