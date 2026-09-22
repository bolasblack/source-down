# 在故障等待中通过真实 inotify reader 注入一次队列溢出，原输入事实保持不变。
# {% include "tests-e2e/fixtures/watch/notification_publication.c" %}
import time
from support import E2ECase


class RecoveryRescan(E2ECase):
    specs = ("SPEC-CLI-010",)
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """未知恢复范围失去覆盖只安排一次明确发现尝试，不伪装成已证实内容变化"""
        source = "Stable input\n"
        crash = ("from pathlib import Path\n"
                 "with Path('.source-down/starts').open('ab') as log: log.write(b'start\\n')\n"
                 "raise SystemExit(9)\n")
        with self.project({"docs/index.md": source}) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["docs"])
            project.writeFiles({
                "broken.py": crash,
                "source-down.toml": "config_version=1\n[plugins.broken]\ncommand=['python','broken.py']\n",
            })
            with self.notificationPublicationFault(project, mode="rescan") as fault:
                environment = dict(fault.environment, SD_WATCH_NOTIFY_ARM=str(project.root / ".source-down/rescan.arm"))
                with project.sourceDown.watch(inputs=["docs"], env=environment) as watch:
                    watch.waitForDiagnostics(contains=["execution failure; watching"])
                    time.sleep(0.4)
                    self.assertEqual(project.readBytes(".source-down/starts"), b"start\n")
                    reason = b"recovery coverage invalidated; scheduling a discovery attempt"
                    self.assertNotIn(reason, watch.stderr)
                    checkpoint = watch.checkpoint()

                    # Waking the reader changes neither bytes nor file identity of the known input.
                    project.writeFiles({".source-down/rescan.arm": "lose coverage"})
                    project.writePreservingTimes("docs/index.md", source)
                    fault.waitUntilCallbackReturned(watch)
                    watch.waitForDiagnostics(contains=[reason, "execution failure; watching"], since=checkpoint)
                    time.sleep(1.2)
                    self.assertEqual(project.readBytes(".source-down/starts"), b"start\nstart\n")
                    self.assertEqual(watch.stderr.count(reason), 1)
                    self.assertWatchDiagnostics(watch, contains=["backend native"])
                    self.assertNotIn(b"switching to poll", watch.stderr)
                    self.assertEqual(project.readBytes("docs/index.md"), source.encode())
                    self.assertOutputUnchanged(project, since=published, trees=["pages", "reports", "search"])
                    watch.interrupt()
                    self.assertRunResult(watch.wait(), exitCode=130)
