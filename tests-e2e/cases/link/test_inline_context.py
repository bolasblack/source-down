# 同一篇正文包含四种有效内联位置和四种保持字面的示例。
# {% include "tests-e2e/fixtures/link/inline_context.py" %}
from support import E2ECase
from fixtures.link.inline_context import SOURCE


class InlineContext(E2ECase):
    specs = ("SPEC-DIR-002", "SPEC-DIR-004", "SPEC-REN-011", "SPEC-BLT-009")

    def test_scenario(self):
        """标题、紧凑列表和引用内联展开，字面代码与转义保持"""
        with self.project({
            "docs/index.md": SOURCE,
            "docs/details.md": "",
            "label.txt": "Title",
        }) as project:
            reading = project.sourceDown.render(inputs=["docs"])
            self.assertRunResult(reading, exitCode=0)

            self.assertPageContent(reading, "pages/docs/index.md.md", contains=[
                "# [Title](details.md.md)", "- [item](details.md.md#manual)",
                "> [quote](details.md.md)", "URL: details.md.md",
            ])
            self.assertPageContent(reading, "pages/docs/index.md.md", contains=[
                "`[literal]({% unknown %})`", "\\{% unknown %}",
                "```text\n{% unknown %}\n```", "<div>\n{% unknown %}\n</div>",
            ], counts={"**Call site**": 5})
            self.assertExpansionOccurrences(reading, inputPath="docs/index.md", count=5)
            self.assertIndexContainsText(reading, text="[item](details.md.md#manual)")
