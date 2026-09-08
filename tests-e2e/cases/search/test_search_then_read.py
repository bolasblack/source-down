# 先生成文档，再搜索其中的原文，通过实际返回的句柄读回完整片段。
import json
from support import E2ECase


class SearchThenRead(E2ECase):
    specs = ("SPEC-SRH-001", "SPEC-SRH-004", "SPEC-SRH-005", "SPEC-SRH-006")

    def test_scenario(self):
        """搜索结果的句柄读回完整原文且不改变生成物"""
        text = "needle 中文正文，保持原文。\n"
        with self.project({"guide.md": text}) as project:
            generated = project.run(["render", "guide.md"])
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(generated.stdout, b"")
            saved = project.snapshot()
            search = project.run(["search", "needle", "--limit", "1", "--json"])
            self.assertEqual(search.returncode, 0, search.stderr)
            found = json.loads(search.stdout)
            self.assertEqual(found["freshness"], "matched")
            self.assertEqual(found["returned"], 1)
            hit, = found["hits"]
            self.assertRegex(hit["handle"], r"^[0-9A-Za-z]{11}$")
            self.assertEqual(hit["kind"], "prose")
            read = project.run(["read", hit["handle"], "--json"])
            self.assertEqual(read.returncode, 0, read.stderr)
            body = json.loads(read.stdout)
            self.assertEqual(body["snapshot"], found["snapshot"])
            self.assertEqual(body["handle"], hit["handle"])
            self.assertEqual(body["body"], {"text": text, "range": [0, len(text.encode("utf-8"))],
                                          "total_bytes": len(text.encode("utf-8")), "truncated": False, "next_offset": None})
            self.assertEqual(body["sources"]["items"][0]["current_link"], "guide.md#L1")
            self.assertEqual(project.snapshot(), saved)
