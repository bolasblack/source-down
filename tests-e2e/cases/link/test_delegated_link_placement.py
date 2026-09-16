# navigation 插件把 Before、include、标准 link、After 组成主文；附录和报告也返回标准 link。
# 作者 link 的项目覆盖与这些标准委托共享真实协议输入。
# {% include "tests-e2e/fixtures/link/navigation.py" %}
# {% include "tests-e2e/fixtures/plugin_wire.py" %}
# {% include "tests-e2e/cases/link/fixtures.py" id="navigationPluginFiles" %}
from support import E2ECase
from .fixtures import navigationPluginFiles


class DelegatedLinkPlacement(E2ECase):
    specs = ("SPEC-BLT-001", "SPEC-BLT-008", "SPEC-PLG-007", "SPEC-PLG-011", "SPEC-CLI-007")

    def test_scenario(self):
        """标准 link 在主文、附录和报告的实际位置得到各自 URL、来源与依赖。"""
        with self.project({
            **navigationPluginFiles(self, target="docs/end.md", material="material.txt",
                                    projectText="Project navigation", directives=["compose", "link"],
                                    override=["link"]),
            "docs/deep/start.md": '{% compose %}\n{% link "anything" %}\n',
            "docs/end.md": "",
            "material.txt": "Included material\r\n",
        }) as project:
            for output in (".source-down", "nested/reading"):
                with self.subTest(output=output):
                    reading = project.sourceDown.render(inputs=["docs"], outputDir=output)
                    self.assertRunResult(reading, exitCode=0, stdout=b"")

                    self.assertPageContent(reading, "pages/docs/deep/start.md.md", firstOccurrencesInOrder=[
                        "Before", "Included material\r\n", "\n\n../end.md.md\n\n", "After",
                    ])
                    self.assertPageContent(reading, "pages/docs/end.md.md", contains=[
                        "\n\nend.md.md\n\n",
                    ], excludes=["**Content source**"])
                    self.assertPageContent(reading, "reports/navigation/overview.md", contains=[
                        "\n\n../../pages/docs/end.md.md\n\n",
                    ], excludes=["**Content source**"])
                    self.assertNavigationRecordSources(reading, matchingText=[
                        "../end.md.md", "end.md.md", "../../pages/docs/end.md.md",
                    ], count=3)
                    self.assertIndexMetadata(reading, fields={"format_version": 1})
                    self.assertIndexDependencyPaths(reading, owner="navigation", equals=[
                        "docs/end.md", "material.txt",
                    ])
