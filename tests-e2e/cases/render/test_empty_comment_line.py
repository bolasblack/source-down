# 空注释行属于相邻的同 marker 注释组，整组只生成一次完整来源区。
from support import E2ECase


class EmptyCommentLine(E2ECase):
    specs = ("SPEC-REN-003",)

    def test_scenario(self):
        """Rust 三种行注释、JS 和 Python 的空注释行保留为同一正文中的空行"""
        for path, original, end in [
            ("plain.rs", "// first\n//\n// last\n", 20),
            ("outer.rs", "/// first\n///\n/// last\n", 23),
            ("inner.rs", "//! first\n//!\n//! last\n", 23),
            ("source.js", "// first\n//\n// last\n", 20),
            ("source.py", "# first\n#\n# last\n", 17),
        ]:
            with self.subTest(path=path), self.project({path: original}) as project:
                project.sourceDown.renderSuccessfully(inputs=[path])
                expected = (f"# `{path}`\n\n> **Source**: [`{path}:L1-L3`](../../{path}#L1)"
                            f" · bytes [0,{end})\n\nfirst\n\nlast\n\n\n")
                self.assertEqual(project.readBytes(f".source-down/pages/{path}.md"), expected.encode())
                self.assertEqual(project.readBytes(path), original.encode())
