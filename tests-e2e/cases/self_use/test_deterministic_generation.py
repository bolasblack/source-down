# 同一份项目事实重复生成，比较页面与报告的完整路径和原始字节。
from support.project import SelfUseCase, markdown_snapshot


class DeterministicGeneration(SelfUseCase):
    specs = ("SPEC-MOD-004", "SPEC-CLI-004")

    def test_scenario(self):
        """不变的项目事实产生相同页面和报告"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            baseline = markdown_snapshot(project)
            repeated = project.run(command)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(repeated.stdout, b"")
            self.assertEqual(markdown_snapshot(project), baseline)
