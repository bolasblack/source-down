# 作者拥有显示文字、括号和 fragment；七种作者文件共享同一正文。
# 注释包裹、CRLF 和代码尾部来自这份固定文件准备。
# {% include "tests-e2e/cases/link/fixtures.py" id="inlineLanguageFiles" %}
from support import E2ECase
from .fixtures import inlineLanguageFiles


class InlineRendering(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-BLT-009", "SPEC-DIR-004", "SPEC-DIR-006", "SPEC-REN-011")

    def test_scenario(self):
        """Markdown 与六语言内联替换得到完整正文，作者 fragment 和 Markdown CRLF 保持。"""
        prose = '[下一篇]({% link "docs/details.md" %}#anchor) 与 [{% include "label.txt" %}]({% link "docs/details.md" %})'
        paths = ("index.md", "index.rs", "index.ml", "index.js", "index.ts", "index.go", "index.py")
        files = {
            **inlineLanguageFiles(prose),
            "docs/details.md": "# A page without an anchor declaration\n",
            "label.txt": "更多",
            "catalog.md": "\n".join('[next]({% link "' + path + '" %})' for path in paths),
        }
        with self.project(files) as project:
            reading = project.sourceDown.render(inputs=["."])
            self.assertRunResult(reading, exitCode=0, stdout=b"")

            self.assertPageContent(reading, "pages/catalog.md.md", contains=[
                "[next](index.md.md)", "[next](index.rs.md)", "[next](index.ml.md)",
                "[next](index.js.md)", "[next](index.ts.md)", "[next](index.go.md)",
                "[next](index.py.md)",
            ])
            expected = "[下一篇](docs/details.md.md#anchor) 与 [更多](docs/details.md.md)"
            for path in paths:
                with self.subTest(path=path):
                    self.assertPageContent(reading, f"pages/{path}.md", contains=[expected],
                                           excludes=["{% link"], counts={"**Call site**": 3})
                    if path == "index.md":
                        self.assertPageContent(reading, f"pages/{path}.md", contains=[expected + "\r\n"])
