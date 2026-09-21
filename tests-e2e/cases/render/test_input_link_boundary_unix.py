# 链接本身位于 root 内仍不足以获得读取权限，必须检查实际目标。
# {% include "tests-e2e/fixtures/render/observe_inputs.py" %}
from support import E2ECase


class InputLinkBoundary(E2ECase):
    specs = ("SPEC-CLI-002",)
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """显式输入链接越出 root 时在插件启动前拒绝，所有旧产物不变"""
        with self.project({"outside.rs": "// Outside\n"}) as outside, self.project({
            "inside.rs": "// Inside\n",
            "plugin.py": self.fixture("render/observe_inputs.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.observer]\ncommand=['python','plugin.py']\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["inside.rs"])
            project.removeFile("started.json")
            project.removeFile("batches.jsonl")
            project.symlink("alias.rs", target=outside.root / "outside.rs")
            failed = project.sourceDown.render(inputs=["alias.rs"])
            self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=["outside project root"])
            self.assertFalse((project.root / "started.json").exists())
            self.assertFalse((project.root / "batches.jsonl").exists())
            self.assertOutputUnchanged(project, since=published)
