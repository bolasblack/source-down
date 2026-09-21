# 空页面与已有 layout 通过真实插件接收附录，检查最终页面的完整 framing 字节。
# {% include "tests-e2e/fixtures/render/empty_page_appendices.py" %}
from support import E2ECase


class EmptyPageAppendices(E2ECase):
    specs = ("SPEC-REN-013",)

    def test_scenario(self):
        """附录补足两个前置 LF，保留更多 layout，并在重复生成时只出现一次标题"""
        with self.project({
            "empty.md": "", "one.md": "\n", "two.md": "\n\n", "three.md": "\n\n\n",
            "empty.rs": "", "plain.md": "",
            "plugin.py": self.fixture("render/empty_page_appendices.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.notes]\ncommand=['python','plugin.py']\n",
        }) as project:
            inputs = ["empty.md", "one.md", "two.md", "three.md", "empty.rs", "plain.md"]
            published = project.sourceDown.renderSuccessfully(inputs=inputs)
            appendix = (b"# Appendix\n\n> **Plugin**: `notes`\n\nFirst\n\n"
                        b"> **Plugin**: `notes`\n\nSecond\n\n")
            # Nonempty layout retains its own two framing LFs before appendix framing.
            for path, prefix in [("empty.md", b"\n\n"), ("one.md", b"\n\n\n"),
                                 ("two.md", b"\n\n\n\n"), ("three.md", b"\n\n\n\n\n"),
                                 ("empty.rs", b"# `empty.rs`\n\n")]:
                with self.subTest(path=path):
                    self.assertEqual(project.readBytes(f".source-down/pages/{path}.md"), prefix + appendix)
            self.assertEqual(project.readBytes(".source-down/pages/plain.md.md"), b"")
            project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertOutputUnchanged(project, since=published)
