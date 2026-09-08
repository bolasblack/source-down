# 大实体包含中文、emoji、CRLF 和缺失的末尾换行；续读按字符预算前进，偏移仍以字节计。
# 故意损坏配置与搜索索引，证明直接文件读取不依赖这些生成状态。
import hashlib
import json
from support import E2ECase


class Utf8Continuation(E2ECase):
    specs = ("SPEC-SRH-006", "SPEC-SRH-007", "SPEC-MOD-003")

    def test_scenario(self):
        """大实体的 UTF-8 续读完整保留 CRLF 和无换行的尾部"""
        selection = "class Cache:\r\n    # " + "甲乙😀a" * 8000 + "\r\n    def get(self):\r\n        return '終'"
        text = ("# preamble\r\n" + selection).encode("utf-8")
        with self.project({"cache.py": text, "source-down.toml": "broken configuration = [",
                           ".source-down/search/index.json": "broken index"}) as project:
            offset, chunks = 0, []
            while True:
                command = project.run(["read", "cache.py", "--id=Cache", "--offset", str(offset), "--json"])
                self.assertEqual(command.returncode, 0, command.stderr)
                result = json.loads(command.stdout)
                self.assertEqual(set(result), {"format_version", "mode", "id", "format", "language", "file_sha256", "source", "body"})
                self.assertEqual(result["mode"], "file")
                self.assertEqual(result["file_sha256"], hashlib.sha256(text).hexdigest())
                self.assertEqual(result["source"], {"path": "cache.py", "start_byte": len(b"# preamble\r\n"),
                                                  "end_byte": len(text), "start_line": 2, "end_line": 5})
                body = result["body"]
                self.assertEqual(set(body), {"text", "range", "total_bytes", "truncated", "next_offset"})
                self.assertLessEqual(len(body["text"]), 12000)
                self.assertEqual(body["range"], [offset, offset + len(body["text"].encode("utf-8"))])
                self.assertEqual(body["total_bytes"], len(selection.encode("utf-8")))
                chunks.append(body["text"])
                if body["next_offset"] is None:
                    self.assertFalse(body["truncated"])
                    break
                self.assertTrue(body["truncated"])
                self.assertGreater(body["next_offset"], offset)
                self.assertEqual(body["next_offset"], body["range"][1])
                offset = body["next_offset"]
            self.assertEqual("".join(chunks).encode("utf-8"), selection.encode("utf-8"))
            self.assertEqual(project.read_bytes(".source-down/search/index.json"), b"broken index")
            self.assertFalse((project.root / ".source-down/pages").exists())
