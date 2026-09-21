# 中文前缀用于区别原始 UTF-8 字节位置与提取后的注释位置。
# {% include "tests-e2e/fixtures/render/observe_inputs.py" %}
from support import E2ECase


class DirectiveFailures(E2ECase):
    specs = ("SPEC-DIR-005", "SPEC-PLG-002")

    def test_scenario(self):
        """重复参数、位置参数顺序和未知 owner 都在启动前按原文件位置报错"""
        with self.project({
            "src/a.rs": "// Initial\n",
            "plugin.py": self.fixture("render/observe_inputs.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.observer]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["src/a.rs"])
            project.removeFile("started.json")
            project.removeFile("batches.jsonl")
            for tag, location in [
                ('{% note key=1 key=2 %}', 'src/a.rs:2: byte 13:'),
                ('{% note key=1 "later" %}', 'src/a.rs:2: byte 13:'),
                ('{% unregistered %}', 'src/a.rs:2 bytes [13,31): unregistered directive unregistered'),
            ]:
                with self.subTest(tag=tag):
                    project.writeInPlace("src/a.rs", "// 中文\n// " + tag + "\n")
                    failed = project.sourceDown.render(inputs=["src/a.rs"])
                    self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=[location])
                    self.assertFalse((project.root / "started.json").exists())
                    self.assertFalse((project.root / "batches.jsonl").exists())
                    self.assertOutputUnchanged(project, since=published)
