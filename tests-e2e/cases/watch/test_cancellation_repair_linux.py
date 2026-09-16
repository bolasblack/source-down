# 插件批次退出后 watch 等待修复；取消仍要确认该直接子进程已被 reap。
# {% include "tests-e2e/fixtures/watch/process_exit_batch.py" %}
from support import E2ECase


class RepairCancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """插件退出 9 后等待修复时取消，插件被回收且 CLI 退出 130"""
        with self.project({
            "docs/index.md": "Cancellation proof\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/process_exit_batch.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                child = int(project.readBytes(".source-down/plugin.pid"))
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
                self.assertProcessReaped(child)
