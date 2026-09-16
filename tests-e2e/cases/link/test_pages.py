# 作者用输入路径声明双向导航；每条 URL 的来源是作者实际写下的指令。
from support import E2ECase


class PageLinks(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-007", "SPEC-PLG-007")

    def test_scenario(self):
        """两篇 Markdown 相互链接，保留各自真实的调用来源"""
        with self.project({
            "docs/index.md": '{% link "docs/details.md" %}\n',
            "docs/details.md": '# Details\n\n{% link "docs/index.md" %}\n',
        }) as project:
            reading = project.sourceDown.render(inputs=["docs"])
            self.assertRunResult(reading, exitCode=0, stdout=b"")

            self.assertPageContent(reading, "pages/docs/index.md.md", contains=[
                "\n\ndetails.md.md\n\n",
            ], counts={"**Call site**": 1, "**Content source**": 1})
            self.assertPageContent(reading, "pages/docs/details.md.md", contains=[
                "\n\nindex.md.md\n\n",
            ])
            self.assertPageLinkRecords(reading, texts=["details.md.md", "index.md.md"])
            self.assertIndexDependencies(reading, owner="builtin:link", equals=[
                {"kind": "file", "path": "docs/details.md"},
                {"kind": "file", "path": "docs/index.md"},
            ])
