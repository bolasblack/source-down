# 同一项目指令的标签参数变化应进入本轮内容；原始源码恢复后结果也恢复。
from support.project import SelfUseCase, markdown_snapshot


class ArgumentRefresh(SelfUseCase):
    specs = ("SPEC-MOD-004", "SPEC-PLG-003")

    def test_scenario(self):
        """项目指令参数改变后立即生效，恢复后重现原字节"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            baseline = markdown_snapshot(project)
            original = project.read_bytes("src/lib.rs")
            project.write_bytes("src/lib.rs", original.replace(b"Build identity", b"Changed identity"))
            changed = project.run(command)
            self.assertEqual(changed.returncode, 0, changed.stderr)
            self.assertEqual(changed.stdout, b"")
            pages = markdown_snapshot(project)
            self.assertNotEqual(pages, baseline)
            self.assertIn(b"Changed identity:", b"\n".join(pages.values()))
            project.write_bytes("src/lib.rs", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), baseline)
