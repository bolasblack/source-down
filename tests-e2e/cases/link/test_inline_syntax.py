# 真实 words 插件按参数顺序返回多个 text 块，每块来源均为原始请求。
# {% include "tests-e2e/fixtures/link/words.py" %}
# {% include "tests-e2e/fixtures/plugin_wire.py" %}
# {% include "tests-e2e/cases/link/fixtures.py" id="wordsPluginFiles" %}
from support import E2ECase
from .fixtures import wordsPluginFiles


class InlineSyntax(E2ECase):
    specs = ("SPEC-DIR-005", "SPEC-DIR-006", "SPEC-REN-011", "SPEC-CLI-004")

    def test_scenario(self):
        """中文前缀后的未闭合标签报告原始 byte 6，并保留全部旧输出。"""
        with self.project({
            **wordsPluginFiles(self),
            "index.md": '前缀{% words "AB" "CD" %}后缀\r\n',
        }) as project:
            published = project.sourceDown.render(inputs=["index.md"])
            self.assertRunResult(published, exitCode=0)
            self.assertPageContent(published, "pages/index.md.md", contains=["前缀ABCD后缀\r\n"])

            project.writeInPlace("index.md", '前缀{% words "unclosed" 后缀\n')
            rejected = project.sourceDown.render(inputs=["index.md"])
            self.assertRunResult(rejected, exitCode=1, stderrContains=["index.md:1: byte 6:"])
            self.assertOutputUnchanged(project, since=published)
