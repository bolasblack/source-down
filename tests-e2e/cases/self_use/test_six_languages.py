# 同一条真实命令生成自身 Rust 实现、Python 工具、测试、六语言示例和使用指南。
# 页面中的原文标签及三类来源共同证明所选择的材料已进入这次生成。
from support.project import SelfUseCase, markdown_snapshot


class SixLanguages(SelfUseCase):
    specs = ("SPEC-MOD-001", "SPEC-REN-001", "SPEC-REN-008", "SPEC-PRJ-003")

    def test_scenario(self):
        """六语言真实源码与项目插件一起生成阅读材料"""
        with self.self_use() as project:
            result = project.run(["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            pages = markdown_snapshot(project)
            content = b"\n".join(pages.values())
            self.assertIn(b"Build identity:", content)
            self.assertIn(b"src/model.rs", content)
            self.assertIn(b"# `tools/project_docs.py`", content)
            for language in ("OCaml", "JavaScript", "TypeScript", "Go", "Python"):
                with self.subTest(language=language):
                    self.assertIn(f"{language} example uses the same project plugin:".encode(), content)
            for label in ("rust", "ocaml", "javascript", "jsx", "typescript", "tsx", "go", "python"):
                with self.subTest(code_label=label):
                    self.assertIn(f"```{label}\n".encode(), content)
            for source in (b"> **Source**:", b"> **Call site**:", b"> **Content source**:"):
                self.assertIn(source, content)
            self.assertIn("reports/spec/coverage.md", pages)
