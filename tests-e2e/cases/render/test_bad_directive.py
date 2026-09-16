# 已有完整产物后写入坏指令语法。执行故障必须保留页面、报告和索引。
from support.project import SelfUseCase


class BadDirective(SelfUseCase):
    specs = ('SPEC-DIR-006', 'SPEC-CLI-004')

    def test_scenario(self):
        """坏指令语法不改变任何旧产物，修复后恢复生成"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            published = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("src/lib.rs"):
                project.prependBytes("src/lib.rs", b'//! {% package "unterminated %}\n')
                failed = project.sourceDown.render(inputs=inputs)

                self.assertRunResult(failed, exitCode=1, stdout=b"", stderrNotEmpty=True)
                self.assertOutputUnchanged(project, since=published)

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=published)
