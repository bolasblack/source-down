# 队列溢出触发真实 Rescan；同一变更只执行所需的第二轮插件批次。
# 恢复插件和原生通知注入器均为本场景运行并展示的固定 fixture。
# 固定在 pages/docs/a.md.md 已出现、检查 pages/docs/z.md.md 时注入 Rescan。
# {% include "tests-e2e/fixtures/watch/notification_recovery.py" %}
# {% include "tests-e2e/fixtures/watch/notification_publication.c" %}
import time
from support import E2ECase


class NotificationRescanPublication(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """发布中的通知 Rescan 完成页面和索引，静止后不再重复执行插件"""
        with self.project({
            "docs/keep.md": "Keep chapter\n",
            "docs/obsolete.md": "Obsolete\n",
            "docs/z.md": "Last chapter\n",
            "plugin.py": self.notificationRecoveryObserver(),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": (
                'config_version=1\n[plugins.observe]\n'
                'command=["python","plugin.py"]\n'
            ),
        }) as project:
            with self.notificationPublicationFault(
                project,
                mode="rescan",
            ) as fault:
                with project.sourceDown.watch(inputs=["docs"], env=fault.environment) as watch:
                    try:
                        watch.waitForPublishedPages(3)
                        oldIndex = project.readBytes(".source-down/search/index.json")
                        project.writeInPlace("docs/a.md", "New owned chapter\n")
                        (project.root / "docs/obsolete.md").unlink()

                        fault.waitUntilCallbackReturned(watch)
                        watch.waitForOutputState(changed={".source-down/search/index.json": oldIndex})
                        self.assertFilesPresent(project, [".source-down/pages/docs/a.md.md"])
                        self.assertPathAbsent(project, ".source-down/pages/docs/obsolete.md.md")
                        self.assertNotIn(b"switching to poll", watch.stderr)
                        time.sleep(1.1)
                        self.assertFileContent(
                            project,
                            ".source-down/observer.events",
                            b"initialize\nrun\nrun\n",
                        )
                        project.sourceDown.searchSuccessfully("Keep")
                        watch.interrupt()
                        self.assertRunResult(watch.wait(), exitCode=130)
                    finally:
                        fault.releaseRecovery()
