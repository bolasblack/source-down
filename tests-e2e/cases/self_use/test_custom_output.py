# 改变输出根后，仍以同一输入集生成完整页面；回到默认根不会改变原有结果。
# 两个根的查询另见搜索场景，导航断言由指南场景共同维护。
from support.project import SelfUseCase
from .guide_expectations import assertGuideNavigation, assertGuideSources


class CustomOutput(SelfUseCase):
    specs = ('SPEC-CLI-001', 'SPEC-CLI-007', 'SPEC-REN-009')

    def test_scenario(self):
        """自定义输出生成完整阅读集并能恢复默认输出"""
        # {% include "tests-e2e/cases/self_use/guide_expectations.py" %}
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]

            # 先用默认目录生成完整的基线。
            baseline = project.sourceDown.renderSuccessfully(inputs=inputs)

            # 换目录，页面集合相同，指南中的导航和源码来源仍有效。
            custom = project.sourceDown.renderSuccessfully(inputs=inputs, outputDir="reading/custom")
            self.assertMarkdownOutput(custom, samePathsAs=baseline)
            assertGuideNavigation(self, custom)
            assertGuideSources(self, custom)

            # 回到默认目录，全部 Markdown 字节恢复到基线。
            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=baseline)
