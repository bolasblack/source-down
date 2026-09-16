# 插件完成检查并为每项请求报告错误，页面与索引保持上轮结果。
# 这里运行的故障插件与阅读展示使用同一个文件。
# {% include "tests-e2e/fixtures/render/plugin_error.py" %}
from support.project import SelfUseCase


class PluginCheckFailure(SelfUseCase):
    specs = ('SPEC-PLG-008', 'SPEC-CLI-004')

    def test_scenario(self):
        """插件检查失败保留旧页面与索引，恢复真实插件后通过"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            published = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("tools/project_docs.py"):
                project.writeInPlace("tools/project_docs.py", self.fixture("render/plugin_error.py"))
                failed = project.sourceDown.render(inputs=inputs)

                self.assertRunResult(
                    failed, exitCode=1, stdout=b"", stderrContains=[b"intentional failure"],
                )
                self.assertOutputUnchanged(
                    project, since=published, trees=["pages"], files=["search/index.json"],
                )

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=published)
