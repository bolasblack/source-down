# 插件已经进入不返回的长批次时，取消必须终止并回收该进程。
# {% include "tests-e2e/fixtures/watch/process_block_batch.py" %}
from support import E2ECase


class BatchCancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """插件写出批次 ready 后持续阻塞，取消回收插件且 CLI 退出 130"""
        with self.project({
            "docs/index.md": "Cancellation proof\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/process_block_batch.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForOutputState(filesPresent=[".source-down/batch.ready"])
                child = int(project.readBytes(".source-down/plugin.pid"))
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
                self.assertProcessReaped(child)
