# {% include "tests-e2e/fixtures/watch/notify_failure.c" %}
# 原生后端初始化遇到真实 EMFILE，随后 poll 也失去 root，必须终止。
from support import E2ECase


class UnavailableObservers(E2ECase):
    specs = ("SPEC-CLI-008",)
    platforms = ("linux",)
    requires_ld_preload = True

    def test_scenario(self):
        """两种观察方式都无法覆盖 root 时退出 1，未启动业务轮次或改变产物"""
        with self.notificationInitializationFault() as fault, self.project({"a.rs": "// Initial\n"}) as project:
            project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            saved = project.snapshot()
            record, release = fault.root / "calls", fault.root / "release"
            moved = project.root.with_name(project.root.name + "-moved")
            with project.sourceDown.watch(inputs=["a.rs"], env=fault.environment(record=record, release=release)) as watch:
                try:
                    watch.waitForOutputState(filesPresent=[record])
                    project.root.rename(moved)
                    fault.release()
                    result = watch.wait()
                    self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["switching to poll"])
                    self.assertNotIn(b"round 1", result.stderr)
                finally:
                    fault.release()
                    if moved.exists():
                        moved.rename(project.root)
            self.assertEqual(project.snapshot(), saved)
