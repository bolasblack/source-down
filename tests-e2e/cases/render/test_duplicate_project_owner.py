# 即使没有作者调用，同一指令名也只能由一个项目实例注册。
from support import E2ECase


class DuplicateProjectOwner(E2ECase):
    specs = ("SPEC-CLI-003",)

    def test_scenario(self):
        """两个项目插件抢占同名指令时退出 2，均未启动且全部既有产物保持"""
        with self.project({
            "a.md": "Original page\n",
            "plugin.py": "import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text('started')\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["a.md"])
            project.writeInPlace("a.md", "Unpublished page\n")
            project.writeFiles({"source-down.toml": """config_version=1
[plugins.first]
command=["python","plugin.py","first.started"]
directives=["note"]
[plugins.second]
command=["python","plugin.py","second.started"]
directives=["note"]
"""})
            result = project.sourceDown.render(inputs=["a.md"])
            self.assertRunResult(result, exitCode=2, stdout=b"", stderrContains=["duplicate project owner", "note"])
            for marker in ["first.started", "second.started"]:
                self.assertFalse((project.root / marker).exists())
            self.assertOutputUnchanged(project, since=published)
