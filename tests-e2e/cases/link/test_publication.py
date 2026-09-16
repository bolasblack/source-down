# 检查失败时，报告内容决定它能否在旧页面保持期间单独更新。
# state.txt 直接声明每轮 reports 和 diagnostics；真实 report 插件每批读取该文件。
# {% include "tests-e2e/fixtures/link/report.py" %}
# {% include "tests-e2e/fixtures/plugin_wire.py" %}
# {% include "tests-e2e/cases/link/fixtures.py" id="reportPluginFiles" %}
from support import E2ECase
from .fixtures import reportPluginFiles, writeReportReply


class LinkPublication(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-PLG-007", "SPEC-CLI-004")

    def test_scenario(self):
        """检查失败时按报告导航保护输出，普通报告可更新，修复后发布新页面。"""
        navigationReport = {"current": {"content": [{
            "kind": "standard_call", "directive": "link",
            "arguments": {"positional": ["details.md"], "named": {}},
        }]}}
        with self.project({
            **reportPluginFiles(self),
            "details.md": "Original page\n",
        }) as project:
            # 检查通过，导航报告与 Original 页面成功发布并成为保护基线。
            writeReportReply(project, reports=navigationReport, diagnostics=[])
            published = project.sourceDown.render(inputs=["details.md"])
            self.assertRunResult(published, exitCode=0)

            # 页面已修改，检查失败；引用本轮未发布页的报告也不能更新。
            project.writeInPlace("details.md", "Updated page\n")
            failedCheck = [{"severity": "error", "code": "check",
                            "message": "Project check failed", "sources": []}]
            writeReportReply(project, reports=navigationReport, diagnostics=failedCheck)
            rejected = project.sourceDown.render(inputs=["details.md"])
            self.assertRunResult(rejected, exitCode=1, stderrContains=[
                "page_not_published", "plugin report, report current, content[0]",
            ])
            self.assertOutputUnchanged(project, since=published)

            # 检查仍失败，普通报告可以更新，页面和搜索索引继续保持旧字节。
            writeReportReply(project, reports={
                "current": {"markdown": "Fresh report", "sources": []},
            }, diagnostics=failedCheck)
            reported = project.sourceDown.render(inputs=["details.md"])
            self.assertRunResult(reported, exitCode=1)
            self.assertNotIn(b"page_not_published", reported.raw.stderr)
            self.assertOutputUnchanged(project, since=published, files=[
                "pages/details.md.md", "search/index.json",
            ])
            self.assertPageContent(reported, "reports/report/current.md", contains=["Fresh report"])

            # 修复检查并恢复导航报告，保留输入中的 Updated 页面后再生成。
            writeReportReply(project, reports=navigationReport, diagnostics=[])
            repaired = project.sourceDown.render(inputs=["details.md"])
            self.assertRunResult(repaired, exitCode=0)
            self.assertPageContent(repaired, "pages/details.md.md", contains=["Updated page"])
