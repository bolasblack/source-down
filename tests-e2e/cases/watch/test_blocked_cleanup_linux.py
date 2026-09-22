# {% include "tests-e2e/fixtures/watch/cleanup.c" %}
# 发布路径被目录占住时，先确认父目录已订阅，再在清理窗口内修复。
# {% include "tests-e2e/fixtures/watch/observer.py" %}
from support import E2ECase


class BlockedCleanup(E2ECase):
    specs = ("SPEC-CLI-010", "SPEC-CLI-012", "SPEC-PLG-008")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """发布阻断先建立原生覆盖，清理期间一次修复即可发布"""
        with self.project({
            "docs/index.md": "Keep reading\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/observer.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project, self.cleanupWindow(project, source="target/shim.c", library="target/cleanup.so") as cleanup:
            with project.sourceDown.watch(inputs=["docs"], env=cleanup.environment) as watch:
                try:
                    watch.waitForDiagnostics(contains=["pages; watching"])
                    blocked = project.root / ".source-down/pages/docs/new.md.md"
                    blocked.mkdir()
                    project.writeInPlace("docs/new.md", "Repaired publication\n")
                    cleanup.waitUntilPaused(watch)
                    self.assertInotifyRegistration(watch, path=blocked.parent)
                    blocked.rmdir()
                    cleanup.release()
                    watch.waitForOutputState(filesPresent=[".source-down/pages/docs/new.md.md"],
                                             contains={".source-down/pages/docs/new.md.md": "Repaired publication"})
                    found = project.sourceDown.search("Repaired")
                    self.assertRunResult(found, exitCode=0)
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
                finally:
                    cleanup.release()
