# The real plugin declares the generated page during the cycle and a material after repair.
# {% include "tests-e2e/fixtures/watch/dependency_scope.py" %}
from support import E2ECase


class DependencyScope(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-PLG-013")

    def test_scenario(self):
        """生成物依赖循环失败后由同一源码修复并发布"""
        with self.project({
            "docs/index.md": "cycle\n",
            "target/data.bin": b"\x00\xff",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/dependency_scope.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["generated-output dependency cycle", "failure; watching"])
                index = ".source-down/search/index.json"
                self.assertPathAbsent(project, index)
                project.writeInPlace("docs/index.md", "repaired dependency\n")
                watch.waitForOutputState(filesPresent=[index])
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
