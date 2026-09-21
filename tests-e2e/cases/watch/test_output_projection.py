# 目录依赖的成员事实包含发布创建的父目录，watch 只排除自己的生成操作。
# 三条目录声明和事件记录来自阅读页展示的同一真实插件。
# {% include "tests-e2e/fixtures/watch/output_projection.py" %}
import time
from support import E2ECase


class OutputProjection(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """root 与输出祖先依赖不因发布循环，手改输出只使搜索过期，其他成员仍触发生成"""
        with self.project({
            "docs/index.md": "Needle projection\n",
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            "plugin.py": self.fixture("watch/output_projection.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
        }) as project:
            with project.sourceDown.watch(inputs=["docs"], outputDir="review/nested") as watch:
                watch.waitForPublishedPages(1)
                events = project.readBytes(".source-down/observer.events")
                project.sourceDown.searchSuccessfully("Needle", outputDir="review/nested")
                project.writeInPlace("review/nested/pages/docs/index.md.md", "manually edited output\n")
                time.sleep(1.2)  # Two complete idle intervals must not send another batch.
                self.assertFileContent(project, ".source-down/observer.events", events)
                self.assertFileContent(project, "review/nested/pages/docs/index.md.md", b"manually edited output\n")
                stale = project.sourceDown.search("Needle", outputDir="review/nested")
                self.assertRunResult(stale, exitCode=1)
                self.assertIn(b"stale search index", stale.raw.stderr)

                # Every generated subtree and its temporary files share the exclusion.
                # Observe each edit separately so a report-triggered round cannot hide.
                for path in ["review/nested/reports/observe/manual.md",
                             "review/nested/search/index.json",
                             "review/nested/pages/docs/.source-down-manual.tmp"]:
                    with self.subTest(output=path):
                        project.writeFiles({path: "manually edited output\n"})
                        time.sleep(1.2)
                        self.assertFileContent(project, ".source-down/observer.events", events)
                        self.assertFileContent(project, path, b"manually edited output\n")

                project.writeInPlace("review/authored.txt", "A real new directory member\n")
                watch.waitForOutputState(contains={
                    "review/nested/pages/docs/index.md.md": "Needle projection",
                })
                watch.waitForEventCount(
                    ".source-down/observer.events",
                    "initialize\n",
                    greaterThan=events.count(b"initialize\n"),
                )
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
