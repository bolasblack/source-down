# 较早插件的完整有效声明在较晚插件崩溃时仍是已知事实，不能一同丢弃。
# 两个具名插件运行阅读页展示的同一程序，第二个在返回结果前故障。
# {% include "tests-e2e/fixtures/watch/partial_dependencies.py" %}
from support import E2ECase


class PartialDependencies(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-013")

    def test_scenario(self):
        """后一个插件崩溃时保留前一个插件的新依赖，修复排除目录中的材料即可继续"""
        with self.project({
            "docs/index.md": "Known material repaired\n",
            "target/material.bin": b"broken",
            "plugin.py": self.fixture("watch/partial_dependencies.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": 'config_version=1\n[plugins.a_material]\ncommand=["python","plugin.py"]\n[plugins.z_failure]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                project.writeInPlace("target/material.bin", b"fixed!")
                watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                found = project.sourceDown.searchSuccessfully("repaired")
                self.assertIn(b"Known material repaired", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
