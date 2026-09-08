# 作者用输入文件路径声明导航；生成器从各篇阅读页面计算实际链接。
import json
from support import E2ECase


class PageLinks(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-007", "SPEC-PLG-007")

    def test_scenario(self):
        """两篇 Markdown 相互链接，保留各自真实的调用来源"""
        with self.project({
            "docs/index.md": '{% link "docs/details.md" %}\n',
            "docs/details.md": '# Details\n\n{% link "docs/index.md" %}\n',
        }) as project:
            result = project.run(["render", "docs"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            index_page = project.read_bytes(".source-down/pages/docs/index.md.md")
            details_page = project.read_bytes(".source-down/pages/docs/details.md.md")
            self.assertIn(b"\n\ndetails.md.md\n\n", index_page)
            self.assertIn(b"\n\nindex.md.md\n\n", details_page)
            self.assertEqual(index_page.count(b"**Call site**"), 1)
            self.assertEqual(index_page.count(b"**Content source**"), 1)
            snapshot = json.loads(project.read_bytes(".source-down/search/index.json"))
            links = [record for record in snapshot["records"] if record["kind"] == "expansion"]
            self.assertEqual(len(links), 2)
            self.assertEqual({record["body"] for record in links}, {"details.md.md", "index.md.md"})
            for record in links:
                occurrence, = record["occurrences"]
                origin, = record["sources"]
                self.assertEqual(origin["span"], occurrence["call_site"])
                self.assertEqual(origin["span"]["path"], occurrence["input_path"])
            self.assertEqual(
                [fact["dependency"] for fact in snapshot["manifest"]["dependencies"]["builtin:link"]],
                [{"kind": "file", "path": "docs/details.md"},
                 {"kind": "file", "path": "docs/index.md"}],
            )
