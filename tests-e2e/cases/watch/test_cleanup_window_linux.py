# {% include "tests-e2e/fixtures/watch/cleanup.c" %}
# 缺失材料在真实进程清理窗口中补齐；不依靠第二次编辑或 sleep。
# {% include "tests-e2e/fixtures/watch/cleanup_report.py" %}
from support import E2ECase


class CleanupWindow(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """报告所引 target/material.md 在清理期间补齐后首次发布恢复"""
        with self.project({
            "docs/index.md": "Keep reading\n",
            "target/.keep": "",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/cleanup_report.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project, self.cleanupWindow(project, source="shim.c", library="target/cleanup.so") as cleanup:
            with project.sourceDown.watch(inputs=["docs"], env=cleanup.environment) as watch:
                try:
                    cleanup.waitUntilPaused(watch)
                    project.writeInPlace("target/material.md", "Fixed!\n")
                    cleanup.release()
                    watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                    found = project.sourceDown.search("Recovered")
                    self.assertRunResult(found, exitCode=0)
                    self.assertIn(b"Recovered query", found.raw.stdout)
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
                finally:
                    cleanup.release()
