# 普通文件的名字不决定目录排除，重复未知提示必须按真实事实去重。
# 修复后运行阅读页展示的固定健康程序；故障程序因 marker 参数不同而留在正文。
# {% include "tests-e2e/fixtures/watch/execution_start_healthy.py" %}
import time
from support import E2ECase


class UnknownRepairs(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011")

    def test_scenario(self):
        """同名普通 marker 首次提示可发现，已知文件与重复相同事实不能使崩溃插件无限重启"""
        for marker, text, attempts in (("target", "same marker", 2), ("docs/index.md", "Marker recovery proof\n", 1)):
            with self.subTest(marker=marker):
                self.exercise_marker(marker, text, attempts)

    def exercise_marker(self, marker, text, attempts):
        failure = (
            "from pathlib import Path\n"
            "Path('.source-down').mkdir(exist_ok=True)\n"
            "with Path('.source-down/starts').open('a', newline='') as log: log.write('start\\n')\n"
            f"Path({marker!r}).write_bytes({text.encode()!r})\n"
            "raise SystemExit(9)\n"
        )
        with self.project({
            "docs/index.md": "Marker recovery proof\n",
            "plugin.py": failure,
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForEventCount(
                    ".source-down/starts", "start\n", greaterThan=attempts - 1,
                    filesPresent=[".source-down/starts"],
                )
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                time.sleep(1.2)  # Identical writes must remain quiet for several old polling periods.
                self.assertFileContent(project, ".source-down/starts", b"start\n" * attempts)
                self.assertWatchDiagnostics(watch, contains=["backend native"])
                self.assertNotIn(b"switching to poll", watch.stderr)

                project.writeInPlace("plugin.py", self.fixture("watch/execution_start_healthy.py"))
                watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                found = project.sourceDown.searchSuccessfully("Marker recovery")
                self.assertIn(b"Marker recovery proof", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
