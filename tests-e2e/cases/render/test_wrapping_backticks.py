# 跨行行内反引号不能吞掉顶层指令；切分后的两侧独立排版，fence 内仍是字面正文。
from support import E2ECase


class WrappingBackticks(E2ECase):
    specs = ("SPEC-REN-011", "SPEC-REN-012")

    def test_scenario(self):
        """反引号包围的独立 include 发布原位展开，fence 中的缺失材料标签不执行"""
        tag = '{% include "material.md" %}'
        original = f'// `\n// {tag}\n// `\n// \n// ```text\n// {{% include "missing.md" %}}\n// ```\n'
        with self.project({"a.rs": original, "material.md": "Inserted"}) as project:
            project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            source = f'> **Source**: [`a.rs:L1-L7`](../../a.rs#L1) · bytes [0,{len(original.encode())})'
            call = f'> **Call site**: [`a.rs:L2-L2`](../../a.rs#L2) · bytes [8,{8 + len(tag)})'
            expected = (
                f'# `a.rs`\n\n{source}\n\n`\n\n\n{call}\n>\n'
                '> **Content source**: [`material.md:L1-L1`](../../material.md#L1) · bytes [0,8)\n\n'
                f'Inserted\n\n{source}\n\n`\n\n```text\n{{% include "missing.md" %}}\n```\n\n\n'
            )
            self.assertFileContent(project, ".source-down/pages/a.rs.md", expected.encode())
            self.assertFileContent(project, "a.rs", original.encode())
