# 同一份项目事实重复生成，比较页面与报告的完整路径和原始字节。
from support.project import SelfUseCase


class DeterministicGeneration(SelfUseCase):
    specs = ('SPEC-MOD-004', 'SPEC-CLI-004')

    def test_scenario(self):
        """不变的项目事实产生相同页面和报告"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            baseline = project.sourceDown.render(inputs=inputs)
            self.assertRenderResult(baseline, exitCode=0, stdout=b"")

            repeated = project.sourceDown.render(inputs=inputs)

            self.assertRenderResult(repeated, exitCode=0, stdout=b"")
            self.assertMarkdownOutput(repeated, sameAs=baseline)
