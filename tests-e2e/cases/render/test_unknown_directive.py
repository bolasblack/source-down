# 未注册的名称没有可执行的 owner；本轮失败且旧产物保持不变。
from support.project import SelfUseCase, markdown_snapshot


class UnknownDirective(SelfUseCase):
    specs = ("SPEC-CLI-003", "SPEC-CLI-004")

    def test_scenario(self):
        """未注册指令导致执行失败，修复后重新通过"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            before = project.snapshot()
            original = project.read_bytes("src/lib.rs")
            project.write_bytes("src/lib.rs", b"//! {% unregistered %}\n" + original)
            failed = project.run(command)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, b"")
            self.assertIn(b"unregistered", failed.stderr)
            self.assertEqual(project.snapshot(), before)
            project.write_bytes("src/lib.rs", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), {k: v for k, v in before.items() if k.endswith(".md")})
