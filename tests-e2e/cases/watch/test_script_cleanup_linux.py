# 同一个真实进程清理握手覆盖普通未知脚本与排除目录内的显式程序。
# 两种脚本都从固定失败程序切换为固定健康程序，清理窗口使用真实 C shim。
# {% include "tests-e2e/fixtures/watch/execution_start_failure.py" %}
# {% include "tests-e2e/fixtures/watch/execution_start_healthy.py" %}
# {% include "tests-e2e/fixtures/watch/cleanup.c" %}
from support import E2ECase


class ScriptCleanup(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """清理暂停时修复普通未知脚本或 target 内显式程序，释放后无需再次编辑即可恢复"""
        for script, command in (("plugin.py", '["python","plugin.py"]'),
                                ("target/plugin.py", '["target/plugin.py"]')):
            wire = "e2e_wire.py" if script == "plugin.py" else "target/e2e_wire.py"
            with self.subTest(script=script), self.project({
                "docs/index.md": "Cleanup script proof\n",
                script: b"#!/usr/bin/env python\n" + self.fixture("watch/execution_start_failure.py"),
                wire: self.fixture("plugin_wire.py"),
                "source-down.toml": f'config_version=1\n[plugins.check]\ncommand={command}\n',
            }) as project:
                (project.root / script).chmod(0o755)
                with self.cleanupWindow(
                    project, source="target/shim.c", library="target/cleanup.so",
                ) as fault:
                    with project.sourceDown.watch(inputs=["docs"], env=fault.environment) as watch:
                        try:
                            fault.waitUntilPaused(watch)
                            project.writeInPlace(
                                script,
                                b"#!/usr/bin/env python\n" + self.fixture("watch/execution_start_healthy.py"),
                            )
                            fault.release()
                            watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                            found = project.sourceDown.searchSuccessfully("Cleanup script")
                            self.assertIn(b"Cleanup script proof", found.raw.stdout)
                            self.assertNotIn(b"switching to poll", watch.stderr)
                            watch.interrupt()
                            self.assertRunResult(watch.wait(), exitCode=130)
                        finally:
                            fault.release()
