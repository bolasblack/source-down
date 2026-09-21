# 相同源码与指令名的含义由各项目注册的插件拥有。
# {% include "tests-e2e/fixtures/render/echo_notes.py" %}
# {% include "tests-e2e/fixtures/render/loud_notes.py" %}
from support import E2ECase


class ProjectDirectiveOwnership(E2ECase):
    specs = ("SPEC-MOD-001",)

    def test_scenario(self):
        """两个项目将 note 注册给不同程序，CLI 使用各自插件的正文结果"""
        source = '// {% note "hello" %}\n'
        pages = []
        for owner, fixture, expected in [
            ("quiet", "render/echo_notes.py", "hello"),
            ("loud", "render/loud_notes.py", "**HELLO**"),
        ]:
            with self.subTest(owner=owner), self.project({
                "src/example.rs": source,
                "plugin.py": self.fixture(fixture),
                "e2e_wire.py": self.fixture("plugin_wire.py"),
                "source-down.toml": f"config_version=1\n[plugins.{owner}]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
            }) as project:
                project.sourceDown.renderSuccessfully(inputs=["src/example.rs"])
                page = project.readBytes(".source-down/pages/src/example.rs.md")
                self.assertIn(("\n\n" + expected + "\n").encode(), page)
                self.assertNotIn(b"{% note", page)
                self.assertEqual(project.readBytes("src/example.rs"), source.encode())
                pages.append(page)
        self.assertEqual(len(pages), 2)
        self.assertNotEqual(pages[0], pages[1])
