# 直接读取 Python 方法保留装饰器、内部注释和原始字节，不要求先生成文档。
import hashlib
import json
from support import E2ECase


class CurrentEntity(E2ECase):
    specs = ("SPEC-SRH-007", "SPEC-ENT-006", "SPEC-MOD-003")

    def test_scenario(self):
        """直接读取当前 Python 方法的完整原文与精确来源"""
        prefix = b"# File preamble\nclass Cache:\n    "
        selection = "@staticmethod\n    def get():\n        # 内部注释\n        return 'value'".encode("utf-8")
        text = prefix + selection + b"\n"
        with self.project({"cache.py": text}) as project:
            command = project.run(["read", "cache.py", "--id=Cache.get", "--json"])
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertEqual(json.loads(command.stdout), {
                "format_version": 1, "mode": "file", "id": "Cache.get", "format": "code", "language": "python",
                "file_sha256": hashlib.sha256(text).hexdigest(),
                "source": {"path": "cache.py", "start_byte": len(prefix), "end_byte": len(text) - 1,
                           "start_line": 3, "end_line": 6},
                "body": {"text": selection.decode("utf-8"), "range": [0, len(selection)],
                         "total_bytes": len(selection), "truncated": False, "next_offset": None},
            })
            self.assertFalse((project.root / ".source-down").exists())
