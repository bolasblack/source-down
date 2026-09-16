# 同一条真实命令生成自身 Rust 实现、Python 工具、测试、六语言示例和使用指南。
# 页面中的原文标签及三类来源共同证明所选择的材料已进入这次生成。
from support.project import SelfUseCase


class SixLanguages(SelfUseCase):
    specs = ('SPEC-MOD-001', 'SPEC-REN-001', 'SPEC-REN-008', 'SPEC-PRJ-003')

    def test_scenario(self):
        """六语言真实源码与项目插件一起生成阅读材料"""
        with self.selfUseProject() as project:
            reading = project.sourceDown.renderSuccessfully(
                inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
            )

            self.assertMarkdownOutput(reading, contains=[
                b"Build identity:", b"src/model.rs", b"# `tools/project_docs.py`",
            ])

            for language in ("OCaml", "JavaScript", "TypeScript", "Go", "Python"):
                with self.subTest(language=language):
                    self.assertMarkdownOutput(
                        reading,
                        contains=[f"{language} example uses the same project plugin:"],
                    )
            for label in ("rust", "ocaml", "javascript", "jsx", "typescript", "tsx", "go", "python"):
                with self.subTest(code_label=label):
                    self.assertMarkdownOutput(reading, codeLabels=[label])

            self.assertMarkdownOutput(reading, contains=[
                b"> **Source**:", b"> **Call site**:", b"> **Content source**:",
            ], includesFiles=["reports/spec/coverage.md"])
