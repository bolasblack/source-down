# 同一个 CRLF 注释的前后正文保留完整来源；两个无尾 LF 的展开由 layout 分开。
# {% include "tests-e2e/fixtures/render/fragment_outputs.py" %}
import json
from support import E2ECase


class CommentExpansionBoundaries(E2ECase):
    specs = ("SPEC-REN-012",)

    def test_scenario(self):
        """真实插件的双来源展开保留精确调用区间、完整原注释来源和空白片段"""
        original = '// before\r\n// {% note "first" %}\r\n// \r\n// {% note "second" %}\r\n// after'
        sources = [{"path": path, "start_byte": 0, "end_byte": length, "start_line": 1, "end_line": 1}
                   for path, length in [("first.md", 6), ("second.md", 7)]]
        with self.project({
            "a.rs": original, "first.md": "First\n", "second.md": "Second\n",
            "plugin.py": self.fixture("render/fragment_outputs.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "reply.json": json.dumps({"sources": sources, "append": [], "reports": {}}),
            "source-down.toml": "config_version=1\n[plugins.notes]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            source = f'> **Source**: [`a.rs:L1-L5`](../../a.rs#L1) · bytes [0,{len(original.encode())})'
            content = (
                '\n>\n> **Content source**: [`first.md:L1-L1`](../../first.md#L1) · bytes [0,6)'
                '\n>\n> **Content source**: [`second.md:L1-L1`](../../second.md#L1) · bytes [0,7)'
            )
            calls = []
            for word, line in [("first", 2), ("second", 4)]:
                tag = '{% note "' + word + '" %}'
                start = original.index(tag)
                calls.append(f'> **Call site**: [`a.rs:L{line}-L{line}`](../../a.rs#L{line}) · bytes [{start},{start + len(tag)})' + content)
            expected = (f'# `a.rs`\n\n{source}\n\nbefore\n\n\n{calls[0]}\n\nfirst\n\n\n\n\n'
                        f'{calls[1]}\n\nsecond\n\n{source}\n\nafter\n\n')
            self.assertFileContent(project, ".source-down/pages/a.rs.md", expected.encode())
            self.assertFileContent(project, "a.rs", original.encode())
