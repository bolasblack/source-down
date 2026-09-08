# 操作系统的 root 别名不改变材料归属；进入项目后仍检查每段链接。
import json
import os
from support import E2ECase


class RootAlias(E2ECase):
    specs = ("SPEC-SRH-007", "SPEC-MOD-003")

    def test_scenario(self):
        """绝对路径通过 root 的目录别名读取准确原文，项目内链接越界仍明确失败"""
        with self.project({"nested/note.md": "# Note\nExact body\n"}) as project, self.project({"outside.md": "# Note\nOutside\n"}) as aliases:
            alias = aliases.root / "root"
            os.symlink(project.root, alias, target_is_directory=True)
            expected = project.run(["read", "nested/note.md", "--id", "Note", "--json"])
            self.assertEqual(expected.returncode, 0, expected.stderr)
            os.symlink(alias / "nested/note.md", project.root / "inside.md")
            for target in (alias / "nested/note.md", "inside.md"):
                result = project.run(["read", target, "--id", "Note", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), json.loads(expected.stdout))
                self.assertEqual(json.loads(result.stdout)["source"]["path"], "nested/note.md")
            os.symlink(aliases.root / "outside.md", project.root / "escape.md")
            result = project.run(["read", alias / "escape.md", "--id", "Note", "--json"])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"outside project root", result.stderr)
