# A dependency can become active after cycle repair and later leave the same live session.
# {% include "tests-e2e/fixtures/watch/dependency_scope.py" %}
import time
from support import E2ECase


class DependencyRemoval(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-PLG-013")

    def test_scenario(self):
        """循环修复后的材料依赖先触发生成，退出依赖后材料变化不再运行"""
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
                repairedIndex = project.readBytes(index)
                project.writeInPlace("target/data.bin", b"")
                watch.waitForOutputState(changed={index: repairedIndex})

                project.writeInPlace("docs/index.md", "drop dependency\n")
                page = ".source-down/pages/docs/index.md.md"
                watch.waitForOutputState(contains={page: "drop dependency"})
                events = project.readBytes(".source-down/observer.events")
                project.writeInPlace("target/data.bin", b"not observed now")
                time.sleep(1.2)
                self.assertFileContent(project, ".source-down/observer.events", events)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
