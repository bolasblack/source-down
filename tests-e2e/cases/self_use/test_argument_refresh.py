# 同一项目指令的标签参数变化应进入本轮内容；原始源码恢复后结果也恢复。
from support.project import SelfUseCase


class ArgumentRefresh(SelfUseCase):
    specs = ('SPEC-MOD-004', 'SPEC-PLG-003')

    def test_scenario(self):
        """项目指令参数改变后立即生效，恢复后重现原字节"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            baseline = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("src/lib.rs"):
                project.replaceBytes("src/lib.rs", b"Build identity", b"Changed identity")
                changed = project.sourceDown.renderSuccessfully(inputs=inputs)

                self.assertMarkdownOutput(
                    changed, differentFrom=baseline, contains=[b"Changed identity:"],
                )

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=baseline)
