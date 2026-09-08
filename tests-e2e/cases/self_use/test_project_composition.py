# Python 项目插件将标题、标准 include 和说明组成有序内容。
# 返回的指令样式文字保持字面内容；核心不把它作为新的作者调用执行。
from support.project import SelfUseCase


class ProjectComposition(SelfUseCase):
    specs = ("SPEC-PLG-007", "SPEC-REN-011")

    def test_scenario(self):
        """真实 Python 插件的内容按节点顺序组合"""
        with self.self_use() as project:
            result = project.run(["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            page = project.read_bytes(".source-down/pages/docs/guide/expanding-directives.md.md")
            heading = b"## API ` SourceSpan `"
            declaration = b"pub struct SourceSpan"
            tail = b"The source above keeps its original bytes and location."
            for piece in (heading, declaration, tail, b'`{% include "src/model.rs" %}`'):
                self.assertIn(piece, page)
            self.assertLess(page.index(heading), page.index(declaration))
            self.assertLess(page.index(declaration), page.index(tail))
