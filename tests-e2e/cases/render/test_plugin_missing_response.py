# 漏掉请求结果属于协议执行故障，报告也必须保留，不能作为检查完成发布。
# {% include "tests-e2e/fixtures/render/plugin_missing_response.py" %}
from support.project import SelfUseCase


class PluginMissingResponse(SelfUseCase):
    specs = ('SPEC-PLG-006', 'SPEC-PLG-008', 'SPEC-CLI-004')

    def test_scenario(self):
        """插件遗漏响应不改变页面、报告或索引"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            published = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("tools/project_docs.py"):
                project.writeInPlace("tools/project_docs.py", self.fixture("render/plugin_missing_response.py"))
                failed = project.sourceDown.render(inputs=inputs)

                self.assertRunResult(failed, exitCode=1, stdout=b"", stderrNotEmpty=True)
                self.assertOutputUnchanged(project, since=published)

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=published)
