# 只改变 wire 的结果数组与报告对象成员顺序，所有内容及其来源保持相同。
# {% include "tests-e2e/fixtures/render/reordered_results.py" %}
import json
from support import E2ECase


class ResponseOrder(E2ECase):
    specs = ("SPEC-MOD-004",)

    def test_scenario(self):
        """结果项和报告成员逆序后，整份发布产物路径与字节保持完全一致"""
        with self.project({
            "src/a.rs": '// {% note "First note" %}\n// {% note "Second note" %}\n',
            "plugin.py": self.fixture("render/reordered_results.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.notes]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            project.sourceDown.renderSuccessfully(inputs=["src/a.rs"])
            first = project.snapshot()
            reply = json.loads(project.readBytes("reply.json"))
            self.assertEqual([item["id"] for item in reply["results"]], ["d1", "d2"])
            self.assertEqual(list(reply["reports"]), ["alpha", "zeta"])
            self.assertEqual(set(first), {"pages/src/a.rs.md", "reports/notes/alpha.md",
                                          "reports/notes/zeta.md", "search/index.json"})
            self.assertLess(first["pages/src/a.rs.md"].index(b"First note"),
                            first["pages/src/a.rs.md"].index(b"Second note"))
            project.writeFiles({"reverse-order": "reverse the wire ordering only"})
            project.sourceDown.renderSuccessfully(inputs=["src/a.rs"])
            reversedReply = json.loads(project.readBytes("reply.json"))
            self.assertEqual([item["id"] for item in reversedReply["results"]], ["d2", "d1"])
            self.assertEqual(list(reversedReply["reports"]), ["zeta", "alpha"])
            self.assertEqual(reversedReply["results"], list(reversed(reply["results"])))
            self.assertEqual(reversedReply["reports"], reply["reports"])
            self.assertEqual(project.snapshot(), first)
