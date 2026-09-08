# 当前文件改变后，默认读拒绝过期索引；显式快照读取保留旧正文并撤掉当前链接。
import json
from support import E2ECase


class StaleSnapshot(E2ECase):
    specs = ("SPEC-SRH-002", "SPEC-SRH-003", "SPEC-SRH-006")

    def test_scenario(self):
        """修改来源后默认查询失败，显式快照仍能读取原文"""
        with self.project({"guide.md": "needle original\n"}) as project:
            rendered = project.run(["render", "guide.md"])
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            search = project.run(["search", "needle", "--json"])
            self.assertEqual(search.returncode, 0, search.stderr)
            hit = json.loads(search.stdout)["hits"][0]
            saved = project.snapshot()
            project.write_text("guide.md", "needle changed!\n")
            for command in (["search", "needle"], ["read", hit["handle"]]):
                with self.subTest(command=command):
                    stale = project.run([*command, "--json"])
                    self.assertEqual(stale.returncode, 1)
                    self.assertEqual(stale.stdout, b"")
                    self.assertIn(b"render", stale.stderr)
            historical = project.run(["read", hit["handle"], "--snapshot", "--json"])
            self.assertEqual(historical.returncode, 0, historical.stderr)
            read = json.loads(historical.stdout)
            self.assertEqual(read["freshness"], "unchecked")
            self.assertEqual(read["body"]["text"].encode("utf-8"), b"needle original\n")
            self.assertTrue(all(s["current_link"] is None for s in read["sources"]["items"]))
            self.assertTrue(all(o["current_link"] is None for o in read["occurrences"]["items"]))
            self.assertEqual(project.snapshot(), saved)
