# 本轮构建的 Rust navigation-plugin 通过真实 stdin/stdout 协议返回 text、include 和 link。
# 它在三个实际内容位置使用 target，并从 material 读取 CRLF 原文。
# {% include "tests-e2e/cases/link/fixtures.py" id="installRustNavigationPlugin" %}
from support import E2ECase
from .fixtures import installRustNavigationPlugin


class RustNavigation(E2ECase):
    specs = ("SPEC-PLG-004", "SPEC-PLG-007", "SPEC-BLT-008", "SPEC-CLI-007")

    def test_scenario(self):
        """真实 Rust 插件把 text、include 和 link 组合到页面、附录与报告"""
        artifact = self.context.spec_plugin.with_name("navigation-plugin" + self.context.spec_plugin.suffix)
        with self.project({
            "docs/deep/start.md": "{% compose %}\n",
            "docs/end.md": "",
            "material.txt": "Included material\r\n",
        }) as project:
            installRustNavigationPlugin(project, artifact=artifact, target="docs/end.md", material="material.txt")
            for output in (".source-down", "nested/reading"):
                reading = project.sourceDown.render(inputs=["docs"], outputDir=output)
                self.assertRunResult(reading, exitCode=0, stdout=b"")

                self.assertPageContent(reading, "pages/docs/deep/start.md.md", firstOccurrencesInOrder=[
                    "Before", "Included material\r\n", "\n\n../end.md.md\n\n", "After",
                ])
                self.assertPageContent(reading, "pages/docs/end.md.md", contains=["\n\nend.md.md\n\n"])
                self.assertPageContent(reading, "reports/navigation/overview.md", contains=[
                    "\n\n../../pages/docs/end.md.md\n\n",
                ])
                self.assertNavigationRecordSources(reading, matchingText=[
                    "../end.md.md", "end.md.md", "../../pages/docs/end.md.md",
                ], count=3)
                self.assertIndexDependencyPaths(reading, owner="navigation", equals=["docs/end.md", "material.txt"])
