# 已发布的页面、附录、报告和索引不能被跨越片段边界的 Markdown 部分替换。
# {% include "tests-e2e/fixtures/render/fragment_outputs.py" %}
import json
from support import E2ECase


class UnclosedOutputFragments(E2ECase):
    specs = ("SPEC-REN-012",)

    def test_scenario(self):
        """附录及报告的未闭合 fence/HTML 都拒绝整轮发布，修复后正常更新"""
        reply = {"sources": [], "append": [{"page": "a.rs", "markdown": "Stable appendix", "sources": []}],
                 "reports": {"status": {"markdown": "Stable report", "sources": []}}}
        with self.project({
            "a.rs": "// Original page\n",
            "plugin.py": self.fixture("render/fragment_outputs.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "reply.json": json.dumps(reply),
            "source-down.toml": "config_version=1\n[plugins.notes]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            project.writeInPlace("a.rs", "// Repaired page\n")
            for location in ["appendix", "report"]:
                for markdown, category in [("```text\nUnclosed", "closing fence"),
                                           ("<script>\nUnclosed", "HTML block")]:
                    with self.subTest(location=location, markdown=markdown):
                        invalid = json.loads(json.dumps(reply))
                        target = invalid["append"][0] if location == "appendix" else invalid["reports"]["status"]
                        target["markdown"] = markdown
                        project.writeInPlace("reply.json", json.dumps(invalid))
                        failed = project.sourceDown.render(inputs=["a.rs"])
                        self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=[category])
                        self.assertOutputUnchanged(project, since=published)
            project.writeInPlace("reply.json", json.dumps(reply))
            project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            self.assertIn(b"Repaired page", project.readBytes(".source-down/pages/a.rs.md"))
