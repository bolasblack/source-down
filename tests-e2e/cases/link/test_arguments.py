# 参数边界先于目标查询；检查失败保留最近成功发布的页面和索引。
from support import E2ECase


class LinkArguments(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-004")

    def test_scenario(self):
        """link 接受页面路径，未知参数和非法路径均明确失败"""
        with self.project({'index.md': '{% link "details.md" %}\n', 'details.md': ''}) as project:
            result = project.run(['render', 'index.md', 'details.md'])
            self.assertEqual(result.returncode, 0, result.stderr)
            old = project.snapshot()
            for arguments in ('"details.md" text="下一篇"', '"details.md" title="Title"',
                              '"details.md" anchor="section"', '"details.md" id="Heading"', '"details.md" lines=[1,2]',
                              '', 'null', '"details.md" "index.md"', '"../details.md"'):
                with self.subTest(arguments=arguments):
                    project.write_text('index.md', '{% link ' + arguments + ' %}\n')
                    result = project.run(['render', 'index.md', 'details.md'])
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stdout, b'')
                    self.assertIn(b'error invalid_arguments:', result.stderr)
                    self.assertEqual(project.snapshot(), old)
