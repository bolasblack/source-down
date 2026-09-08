# 搜索和阅读使用真正展开后的正文；作者字节和生成 URL 有不同的来源映射。
import json
from support import E2ECase


class SearchNavigation(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-SRH-001", "SPEC-SRH-003", "SPEC-SRH-006")

    def test_scenario(self):
        """搜索读回完整内联正文与纯 URL，来源修改后拒绝旧快照并可重新生成"""
        original = 'needle [下一篇]({% link "docs/details.md" %}#manual)\r\n'
        expected = 'needle [下一篇](details.md.md#manual)\r\n'
        with self.project({"docs/index.md": original, "docs/details.md": ""}) as project:
            for output in (".source-down", "nested/reading"):
                result = project.run(["render", "docs", "--output-dir", output])
                self.assertEqual(result.returncode, 0, result.stderr)
                search = project.run(["search", "needle", "--limit", "1", "--json", "--output-dir", output])
                self.assertEqual(search.returncode, 0, search.stderr)
                hit, = json.loads(search.stdout)["hits"]
                read = project.run(["read", hit["handle"], "--json", "--output-dir", output])
                self.assertEqual(read.returncode, 0, read.stderr)
                self.assertEqual(json.loads(read.stdout)["body"]["text"], expected)
                search = project.run(["search", "details.md.md", "--json", "--output-dir", output])
                self.assertEqual(search.returncode, 0, search.stderr)
                expansion, = [hit for hit in json.loads(search.stdout)["hits"] if hit["kind"] == "expansion"]
                read = project.run(["read", expansion["handle"], "--json", "--output-dir", output])
                self.assertEqual(read.returncode, 0, read.stderr)
                self.assertEqual(json.loads(read.stdout)["body"]["text"], "details.md.md")
                index = json.loads(project.read_bytes(f"{output}/search/index.json"))
                prose, = [r for r in index["records"] if r["body"] == expected]
                generated_start = len('needle [下一篇]('.encode())
                generated_end = generated_start + len(b'details.md.md')
                for origin in prose["sources"]:
                    for mapping in origin["mapping"]:
                        start, end = mapping["body"]
                        self.assertTrue(end <= generated_start or start >= generated_end)
                        self.assertEqual(expected.encode()[start:end], original.encode()[slice(*mapping["source"])])
                saved = project.snapshot(output)
                project.write_text("docs/index.md", original.replace("manual", "changed"))
                stale = project.run(["read", hit["handle"], "--json", "--output-dir", output])
                self.assertEqual(stale.returncode, 1, stale.stderr)
                self.assertEqual(stale.stdout, b"")
                self.assertIn(b"render", stale.stderr)
                self.assertEqual(project.snapshot(output), saved)
                result = project.run(["render", "docs", "--output-dir", output])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected.replace("manual", "changed").encode(), project.read_bytes(f"{output}/pages/docs/index.md.md"))
                project.write_text("docs/index.md", original)
