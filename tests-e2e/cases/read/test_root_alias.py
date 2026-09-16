# 操作系统的 root 别名不改变材料归属；进入项目后仍检查每段链接。
from support import E2ECase


class RootAlias(E2ECase):
    specs = ("SPEC-SRH-007", "SPEC-MOD-003")

    def test_scenario(self):
        """绝对路径通过 root 的目录别名读取准确原文，项目内链接越界仍明确失败"""
        with self.project({"nested/note.md": "# Note\nExact body\n"}) as project, self.project({"outside.md": "# Note\nOutside\n"}) as aliases:
            alias = aliases.root / "root"
            aliases.symlink("root", target=project.root, directory=True)
            originalRead = project.run(["read", "nested/note.md", "--id", "Note", "--json"])
            self.assertRunResult(originalRead, exitCode=0)
            project.symlink("inside.md", target=alias / "nested/note.md")
            for target in (alias / "nested/note.md", "inside.md"):
                result = project.run(["read", target, "--id", "Note", "--json"])
                self.assertRunResult(result, exitCode=0)
                self.assertReadAlias(result, sameAs=originalRead, path="nested/note.md")
            project.symlink("escape.md", target=aliases.root / "outside.md")
            result = project.run(["read", alias / "escape.md", "--id", "Note", "--json"])
            self.assertRunResult(result, exitCode=1, stderrContains=["outside project root"])
