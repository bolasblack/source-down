# 持续生成立即完成首轮，不把 stdin EOF 当作停止请求；用户中断退出后输出保持。
# 空健康观察插件记录首轮批次；阅读页展示运行的同一文件。
# {% include "tests-e2e/fixtures/watch/observer.py" %}
from support import E2ECase


class FirstRound(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-MOD-004", "SPEC-PLG-003", "SPEC-PLG-008")

    def test_scenario(self):
        """watch 自动生成两个页面，关闭 stdin 后继续监听，原生中断退出 130"""
        with self.project({
            "docs/start.md": '[next]({% link "docs/end.md" %}#author)\n',
            "docs/end.md": 'End\n',
            "settings.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            "plugin.py": self.fixture("watch/observer.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
        }) as project:
            with project.sourceDown.watch(
                inputs=["docs"], config="settings.toml", outputDir="reading/nested",
            ) as watch:
                watch.waitForOutputState(filesPresent=["reading/nested/search/index.json"])
                self.assertIn(b"[next](end.md.md#author)", project.readBytes("reading/nested/pages/docs/start.md.md"))
                self.assertIn(b"End\n", project.readBytes("reading/nested/pages/docs/end.md.md"))
                watch.waitForDiagnostics(contains=["watching"])
                self.assertEqual(watch.stdout, b"")
                self.assertWatchDiagnostics(watch, contains=["watch round 1"])
                saved = project.snapshot("reading/nested")
                watch.interrupt()
                result = watch.wait()
                self.assertRunResult(result, exitCode=130, stdout=b"")
                self.assertEqual(project.snapshot("reading/nested"), saved)
