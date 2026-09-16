# 指南片段的来源区间逐字节对照真实原文件，并保留同一选区跨页两次。
from support.project import SelfUseCase


class GuideSourceExcerpts(SelfUseCase):
    specs = ("SPEC-REN-008", "SPEC-REN-009", "SPEC-BLT-003", "SPEC-BLT-008", "SPEC-CLI-007")

    def test_scenario(self):
        """默认与自定义输出中的指南片段保留四份来源原文及跨页重复"""
        with self.selfUseProject() as project:
            for output in (".source-down", "reading/custom"):
                with self.subTest(output=output):
                    reading = project.sourceDown.renderSuccessfully(
                        inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
                        outputDir=output,
                    )

                    self.assertSourceExcerptsMatchOriginals(
                        reading,
                        inPagesUnder="docs/guide",
                        language="rust",
                        exactlyFrom=[
                            "src/source.rs", "src/engine.rs", "src/render.rs", "src/model.rs",
                        ],
                    )
                    self.assertSameExcerptOnDifferentPages(
                        reading,
                        source="src/source.rs",
                        inPagesUnder="docs/guide",
                        language="rust",
                        times=2,
                    )
