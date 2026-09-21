# 区间形状合法仍不足够：核心必须检查真实文件、文件长度和行号。
# {% include "tests-e2e/fixtures/render/declared_source.py" %}
import json
from support import E2ECase


class PluginSourceValidation(E2ECase):
    specs = ("SPEC-PLG-007", "SPEC-MOD-003")

    def test_scenario(self):
        """插件声明不存在的文件、超出 EOF 的合法形状区间或错误行号，整轮拒绝发布"""
        source = {"path": "material.txt", "start_byte": 0, "end_byte": 8, "start_line": 1, "end_line": 1}
        with self.project({
            "a.rs": "// {% note %}\n", "material.txt": "Material\n",
            "source.json": json.dumps(source),
            "plugin.py": self.fixture("render/declared_source.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.notes]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            for invalid, reason in [
                (dict(source, path="missing.txt"), "missing.txt"),
                (dict(source, end_byte=99), "byte"),
                (dict(source, end_line=2), "source position"),
            ]:
                with self.subTest(source=invalid):
                    project.writeInPlace("source.json", json.dumps(invalid))
                    failed = project.sourceDown.render(inputs=["a.rs"])
                    self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=["notes", reason])
                    self.assertOutputUnchanged(project, since=published)
