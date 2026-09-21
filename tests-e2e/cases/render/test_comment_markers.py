# 最多移除 marker 后一个 space；重叠的 OCaml 空注释不能产生残留字符。
from support import E2ECase


class CommentMarkers(E2ECase):
    specs = ("SPEC-REN-004",)

    def test_scenario(self):
        """真实文件的 outer doc、inner doc 和空 OCaml 注释按精确字节发布"""
        with self.project({"outer.rs": "///   item\n", "inner.rs": "//! item\n", "empty.ml": "(**)"}) as project:
            project.sourceDown.renderSuccessfully(inputs=["outer.rs", "inner.rs", "empty.ml"])
            self.assertEqual(project.readBytes(".source-down/pages/outer.rs.md"),
                             "# `outer.rs`\n\n> **Source**: [`outer.rs:L1-L1`](../../outer.rs#L1) · bytes [0,11)\n\n  item\n\n\n".encode())
            self.assertEqual(project.readBytes(".source-down/pages/inner.rs.md"),
                             "# `inner.rs`\n\n> **Source**: [`inner.rs:L1-L1`](../../inner.rs#L1) · bytes [0,9)\n\nitem\n\n\n".encode())
            self.assertEqual(project.readBytes(".source-down/pages/empty.ml.md"), b"# `empty.ml`\n\n")
