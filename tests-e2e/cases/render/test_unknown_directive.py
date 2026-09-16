# 未注册的名称没有可执行的 owner；本轮失败且旧产物保持不变。
from support.project import SelfUseCase


class UnknownDirective(SelfUseCase):
    specs = ('SPEC-CLI-003', 'SPEC-CLI-004')

    def test_scenario(self):
        """未注册指令导致执行失败，修复后重新通过"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            published = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("src/lib.rs"):
                project.prependBytes("src/lib.rs", b"//! {% unregistered %}\n")
                failed = project.sourceDown.render(inputs=inputs)

                self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=[b"unregistered"])
                self.assertOutputUnchanged(project, since=published)

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=published)
