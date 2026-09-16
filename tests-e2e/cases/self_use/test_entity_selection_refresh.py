# 不相关声明只改变位置；同名声明改变选择是否唯一。
# 显式下标随后按当前声明顺序选择，恢复输入后完整页面回到原值。
from support.project import SelfUseCase
from .guide_expectations import assertGuideNavigation, assertGuideSources


class EntitySelectionRefresh(SelfUseCase):
    specs = ('SPEC-BLT-007', 'SPEC-MOD-004', 'SPEC-CLI-004', 'SPEC-REN-008')

    def test_scenario(self):
        """源码变化后重新定位实体并明确处理重名与下标"""
        # {% include "tests-e2e/cases/self_use/guide_expectations.py" %}
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            chapters = (
                "docs/guide/reading-source.md",
                "docs/guide/expanding-directives.md",
            )

            # 1. 原始项目成功生成，保存指南的源码片段与完整 Markdown 基线。
            baseline = project.sourceDown.renderSuccessfully(inputs=inputs)
            assertGuideNavigation(self, baseline)
            originalExcerpts = assertGuideSources(self, baseline)

            with project.editing("src/source.rs", *chapters) as original:
                # 2. 前面添加不相关声明，所有片段的正文和顺序都不变。
                project.writeInPlace("src/source.rs", b"fn unrelated() {}\n" + original["src/source.rs"])
                shifted = project.sourceDown.renderSuccessfully(inputs=inputs)
                assertGuideNavigation(self, shifted)
                shiftedExcerpts = assertGuideSources(self, shifted)
                self.assertExcerptBodiesUnchanged(shiftedExcerpts, since=originalExcerpts)

                # 3. 前面添加同名声明，选择含糊，旧页面与索引保持原样。
                project.writeInPlace("src/source.rs", b"pub fn parse() {}\n" + original["src/source.rs"])
                ambiguous = project.sourceDown.render(inputs=inputs)
                self.assertRunResult(ambiguous, exitCode=1, stdout=b"", stderrContains=[b"selection_ambiguous"])
                self.assertOutputUnchanged(project, since=shifted, trees=["pages"], files=["search/index.json"])

                # 4. 两份指南显式选择第 0 个 parse，选中新增的声明。
                project.replaceInFiles(chapters, replacements=[
                    (b'id="parse"', b'id=["parse",0]'),
                    (b'id=["parse"]', b'id=["parse",0]'),
                ])
                first = project.sourceDown.renderSuccessfully(inputs=inputs)
                assertGuideNavigation(self, first)
                firstExcerpts = assertGuideSources(self, first)
                self.assertExcerptBodiesEqual(firstExcerpts, source="src/source.rs", expected=[
                    "pub fn parse() {}", "pub fn parse() {}",
                ])

                # 5. 同名声明移到后面，第 0 个选择恢复原来的 parse。
                project.writeInPlace("src/source.rs", original["src/source.rs"] + b"\npub fn parse() {}\n")
                reordered = project.sourceDown.renderSuccessfully(inputs=inputs)
                assertGuideNavigation(self, reordered)
                reorderedExcerpts = assertGuideSources(self, reordered)
                self.assertExcerptBodiesUnchanged(reorderedExcerpts, since=originalExcerpts, source="src/source.rs")

            # 6. 源码和两份指南恢复原文，全部 Markdown 字节恢复到基线。
            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=baseline)
