# The failing plugin exits before ready and returns no dependency that could trigger repair.
# {% include "tests-e2e/fixtures/watch/execution_start_failure.py" %}
# {% include "tests-e2e/fixtures/watch/execution_start_healthy.py" %}
import time
from support import E2ECase


class ExecutionRepair(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-008")

    def test_scenario(self):
        """首次插件崩溃不按时钟重试，替换同一项目脚本后恢复页面和搜索"""
        with self.project({
            "docs/index.md": "A repaired project\n",
            "plugin.py": self.fixture("watch/execution_start_failure.py"),
            "healthy.py": self.fixture("watch/execution_start_healthy.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": 'config_version=1\n[inputs]\nexclude=["plugin.py"]\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                self.assertFileContent(project, ".source-down/starts", "start\n")
                time.sleep(1.1)
                self.assertFileContent(project, ".source-down/starts", "start\n")

                project.replaceFile("plugin.py", fromPath="healthy.py")
                page = ".source-down/pages/docs/index.md.md"
                index = ".source-down/search/index.json"
                watch.waitForOutputState(filesPresent=[index])
                self.assertIn(b"A repaired project", project.readBytes(page))
                self.assertFileContent(project, ".source-down/starts", "start\nstart\n")
                self.assertRunResult(project.sourceDown.search("repaired"), exitCode=0)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
