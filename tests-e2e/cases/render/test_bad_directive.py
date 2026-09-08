# 已有完整产物后写入坏指令语法。执行故障必须保留页面、报告和索引。
from support.project import SelfUseCase, markdown_snapshot


class BadDirective(SelfUseCase):
    specs = ("SPEC-DIR-006", "SPEC-CLI-004")

    def test_scenario(self):
        """坏指令语法不改变任何旧产物，修复后恢复生成"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            before = project.snapshot()
            original = project.read_bytes("src/lib.rs")
            project.write_bytes("src/lib.rs", b'//! {% package "unterminated %}\n' + original)
            failed = project.run(command)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, b"")
            self.assertTrue(failed.stderr)
            self.assertEqual(project.snapshot(), before)
            project.write_bytes("src/lib.rs", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), {k: v for k, v in before.items() if k.endswith(".md")})
