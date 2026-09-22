# 真实通知 EIO 必须停在已发布页面与旧索引之间，恢复后仍清理完整 ownership。
# 恢复插件和原生通知注入器均为本场景运行并展示的固定 fixture。
# 固定在 pages/docs/a.md.md 已出现、检查 pages/docs/z.md.md 时注入 EIO。
# {% include "tests-e2e/fixtures/watch/notification_recovery.py" %}
# {% include "tests-e2e/fixtures/watch/notification_publication.c" %}
from support import E2ECase


class NotificationErrorPublication(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """发布中通知读取 EIO 后保留旧索引，恢复时清理所有已取得 ownership 的页面"""
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
                mode="error",
            ) as fault:
                with project.sourceDown.watch(inputs=["docs"], env=fault.environment) as watch:
                    try:
                        watch.waitForPublishedPages(3)
                        oldIndex = project.readBytes(".source-down/search/index.json")

                        project.writeInPlace("docs/a.md", "New owned chapter\n")
                        (project.root / "docs/obsolete.md").unlink()

                        # 通知回调已返回；轮询恢复批次则仍停在真实插件响应前。
                        fault.waitUntilCallbackReturned(watch)
                        fault.waitUntilRecoveryBatchPaused(watch)
                        self.assertWatchDiagnostics(watch, contains=[
                            "file notification coverage failed",
                            "switching to poll",
                            "completed:",
                        ])
                        self.assertFileContent(project, ".source-down/search/index.json", oldIndex)
                        self.assertFilesPresent(project, [
                            ".source-down/pages/docs/a.md.md",
                            ".source-down/pages/docs/obsolete.md.md",
                        ])

                        # a 已经部分发布；恢复前删除它，验证两个已拥有页面一起清理。
                        (project.root / "docs/a.md").unlink()
                        fault.releaseRecovery()
                        watch.waitForOutputState(
                            absent=[
                                ".source-down/pages/docs/a.md.md",
                                ".source-down/pages/docs/obsolete.md.md",
                            ],
                            changed={".source-down/search/index.json": oldIndex},
                        )
                        project.sourceDown.searchSuccessfully("Keep")
                        watch.interrupt()
                        self.assertRunResult(watch.wait(), exitCode=130)
                    finally:
                        fault.releaseRecovery()
