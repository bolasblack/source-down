# 真实输入覆盖字面量、嵌套注释、语言扩展、结构缩进与原始代码字节。
# 每个预期片段由 fixture 明确给出，不通过产品解析器计算期望。
# {% include "tests-e2e/fixtures/render/source_matrix.json" %}
import json
from support import E2ECase


class SourceMatrix(E2ECase):
    specs = ("SPEC-REN-002", "SPEC-REN-012")

    def test_scenario(self):
        """六语言词法矩阵经过真实文件和发布，非法边界保留此前全部产物"""
        matrix = json.loads(self.fixture("render/source_matrix.json"))
        with self.project({case["path"]: case["source"] for case in matrix["valid"]}) as project:
            project.sourceDown.renderSuccessfully(inputs=["."])
            published = project.snapshot()
            for case in matrix["valid"]:
                with self.subTest(path=case["path"]):
                    page = published["pages/" + case["path"] + ".md"]
                    self.assertTrue(page.startswith(("# `" + case["path"] + "`\n\n").encode()))
                    self.assertEqual(page.count(b"> **Source**:"), case["source_blocks"])
                    for fenced in case["fenced_code"]:
                        self.assertIn(fenced.encode(), page)
                    for prose in case["prose"]:
                        self.assertIn(("\n\n" + prose + "\n").encode(), page)
                    for fragment in case["fragments"]:
                        self.assertIn(fragment.encode(), page)
                    self.assertEqual(project.readBytes(case["path"]), case["source"].encode())

            for case in matrix["invalid"]:
                with self.subTest(path=case["path"], source=case["source"]):
                    project.writeFiles({case["path"]: case["source"]})
                    failed = project.sourceDown.render(inputs=[case["path"]])
                    self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=[case["path"]])
                    self.assertEqual(project.snapshot(), published)
