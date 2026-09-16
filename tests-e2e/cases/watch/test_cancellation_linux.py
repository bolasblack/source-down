# 健康空闲时取消会回收实际插件子进程。
# {% include "tests-e2e/fixtures/watch/process_idle.py" %}
from support import E2ECase


class Cancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """健康插件已发布并空闲时取消，插件被回收且 CLI 退出 130"""
        with self.project({
            "docs/index.md": "Cancellation proof\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/process_idle.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                child = int(project.readBytes(".source-down/plugin.pid"))
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
                self.assertProcessReaped(child)
