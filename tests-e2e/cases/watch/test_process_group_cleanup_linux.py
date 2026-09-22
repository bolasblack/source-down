# 真实子进程分别处于已退出未回收和仍存活状态，系统调用边界返回相同权限错误。
# {% include "tests-e2e/fixtures/watch/process_group_cleanup.c" %}
# {% include "tests-e2e/fixtures/watch/execution_start_healthy.py" %}
import os
import signal
from support import E2ECase


class ProcessGroupCleanup(E2ECase):
    specs = ("SPEC-PLG-008", "SPEC-CLI-008", "SPEC-CLI-011")
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """回收后已消失的进程组不报清理失败，仍存活且无法终止的插件必须报错退出"""
        for mode in ("exited", "live"):
            with self.subTest(mode=mode), self.project({
                "docs/index.md": "Cleanup recovery\n",
                "plugin.py": ("raise SystemExit(9)\n" if mode == "exited" else
                              "import sys,time\nsys.stdout.write('invalid\\n');sys.stdout.flush()\ntime.sleep(30)\n"),
                "e2e_wire.py": self.fixture("plugin_wire.py"),
                "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
            }) as project, self.processGroupCleanupFault(project, mode=mode) as environment:
                pid = None
                with project.sourceDown.watch(inputs=["docs"], env=environment) as watch:
                    try:
                        watch.waitForOutputState(filesPresent=[".source-down/cleanup-denied.pid"])
                        pid = int(project.readBytes(".source-down/cleanup-denied.pid"))
                        if mode == "live":
                            self.assertRunResult(watch.wait(timeout=5), exitCode=1,
                                                 stderrContains=["process cleanup", "Operation not permitted"])
                            os.kill(pid, 0)
                        else:
                            watch.waitForDiagnostics(contains=["execution failure; watching"])
                            self.assertNotIn(b"process cleanup", watch.stderr)
                            self.assertProcessReaped(pid)
                            project.writeInPlace("plugin.py", self.fixture("watch/execution_start_healthy.py"))
                            watch.waitForPublishedPages(1)
                            found = project.sourceDown.searchSuccessfully("Cleanup recovery")
                            self.assertIn(b"Cleanup recovery", found.raw.stdout)
                            watch.interrupt()
                            self.assertRunResult(watch.wait(), exitCode=130)
                    finally:
                        if mode == "live" and pid is not None:
                            try:
                                os.killpg(pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
