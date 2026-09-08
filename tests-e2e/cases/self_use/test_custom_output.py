# 改变输出根后，仍以同一输入集生成完整页面；回到默认根不会改变原有结果。
# 两个根的查询另见搜索场景，导航断言由指南场景共同维护。
from support.project import SelfUseCase, markdown_snapshot
from .test_guide_navigation import assert_guide_sources_and_links


class CustomOutput(SelfUseCase):
    specs = ("SPEC-CLI-001", "SPEC-CLI-007", "SPEC-REN-009")

    def test_scenario(self):
        """自定义输出生成完整阅读集并能恢复默认输出"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            baseline = markdown_snapshot(project)
            custom = project.run([*command, "--output-dir", "reading/custom"])
            self.assertEqual(custom.returncode, 0, custom.stderr)
            self.assertEqual(custom.stdout, b"")
            pages = markdown_snapshot(project, "reading/custom")
            self.assertEqual(set(pages), set(baseline))
            assert_guide_sources_and_links(self, project, pages, "reading/custom")
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), baseline)
