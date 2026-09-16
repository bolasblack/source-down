# 指南的九条明确 URL 在本轮输出中都有页面和唯一锚点。
from support.project import SelfUseCase


class GuideNavigation(SelfUseCase):
    specs = ("SPEC-REN-008", "SPEC-REN-009", "SPEC-BLT-003", "SPEC-BLT-008", "SPEC-CLI-007")

    def test_scenario(self):
        """默认与自定义输出中的九条指南链接都有准确目标"""
        with self.selfUseProject() as project:
            for output in (".source-down", "reading/custom"):
                with self.subTest(output=output):
                    reading = project.sourceDown.renderSuccessfully(
                        inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
                        outputDir=output,
                    )

                    self.assertPageLinks(reading, fromPage="docs/guide/index.md", to=[
                        "reading-source.md.md#reading-source",
                        "expanding-directives.md.md#expanding-directives",
                        "building-pages.md.md#building-pages",
                        "searching.md.md#searching",
                    ])
                    self.assertPageLinks(reading, fromPage="docs/guide/reading-source.md", to=[
                        "expanding-directives.md.md#expanding-directives",
                    ])
                    self.assertPageLinks(reading, fromPage="docs/guide/expanding-directives.md", to=[
                        "reading-source.md.md#parse-source",
                        "building-pages.md.md#building-pages",
                    ])
                    self.assertPageLinks(reading, fromPage="docs/guide/building-pages.md", to=[
                        "expanding-directives.md.md#directive-routing",
                        "index.md.md#source-down-book",
                    ])
