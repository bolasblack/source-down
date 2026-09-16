# 三个内联调用分别指向原始标签字节；生成 URL 的来源仍是作者调用。
# {% include "tests-e2e/cases/link/fixtures.py" id="inlineLanguageFiles" %}
from support import E2ECase
from .fixtures import inlineLanguageFiles


class InlineSourceSpans(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-BLT-009", "SPEC-DIR-004", "SPEC-DIR-006", "SPEC-REN-011")

    def test_scenario(self):
        """七种作者文件的三个内联调用都保留准确原始标签与 URL 首个来源。"""
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

            for path in paths:
                with self.subTest(path=path):
                    self.assertCallSites(reading, inputPath=path, original=files[path], count=3,
                                         allowedText=['{% link "docs/details.md" %}',
                                                      '{% include "label.txt" %}'], startLine=1)
                    self.assertFirstSourcesMatchCalls(reading, text="docs/details.md.md", inputPath=path)
