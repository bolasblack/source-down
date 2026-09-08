# 普通文件的名字不决定目录排除，重复未知提示必须按真实事实去重。
import time
from support import E2ECase
from .test_execution_repair import START, HEALTHY


class UnknownRepairs(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011")

    def test_scenario(self):
        """同名普通 marker 首次提示可发现，已知文件与重复相同事实不能使崩溃插件无限重启"""
        for marker, text, attempts in (("target", "same marker", 2), ("docs/index.md", "Marker recovery proof\n", 1)):
            with self.subTest(marker=marker):
                self.exercise_marker(marker, text, attempts)

    def exercise_marker(self, marker, text, attempts):
        with self.project({
            "docs/index.md": "Marker recovery proof\n",
            "plugin.py": START + f"Path({marker!r}).write_bytes({text.encode()!r})\nraise SystemExit(9)\n",
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                starts = project.root / ".source-down/starts"
                process.wait_for(lambda: starts.is_file() and starts.read_bytes().count(b"start\n") >= attempts)
                process.wait_for(lambda: b"execution failure; watching" in process.stderr)
                time.sleep(1.2)  # Identical writes must remain quiet for several old polling periods.
                self.assertEqual(starts.read_bytes(), b"start\n" * attempts)
                self.assertIn(b"backend native", process.stderr)
                self.assertNotIn(b"switching to poll", process.stderr)
                project.write_text("plugin.py", START + HEALTHY)
                process.wait_for(lambda: (project.root / ".source-down/search/index.json").is_file())
                result = project.run(["search", "Marker recovery", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"Marker recovery proof", result.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
