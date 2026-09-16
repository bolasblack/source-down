# 被选择规则排除的脚本位于已观察的 docs 目录；原子保存仍属于普通恢复范围。
# {% include "tests-e2e/fixtures/watch/execution_start_failure.py" %}
# {% include "tests-e2e/fixtures/watch/execution_self_dependency.py" %}
import time
from support import E2ECase


class ExcludedScriptAtomicRepair(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-013")

    def test_scenario(self):
        """首次崩溃后原子替换排除的插件脚本即可恢复，自声明依赖后相同字节写入不重启"""
        healthy = self.fixture("watch/execution_self_dependency.py")
        with self.project({
            "docs/index.md": "Atomic repair proof\n",
            "docs/plugin.py": self.fixture("watch/execution_start_failure.py"),
            "docs/e2e_wire.py": self.fixture("plugin_wire.py"),
            "target/replacement.py": healthy,
            "source-down.toml": (
                'config_version=1\n[inputs]\nexclude=["docs/plugin.py","docs/e2e_wire.py"]\n'
                '[plugins.check]\ncommand=["python","docs/plugin.py"]\n'
            ),
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                self.assertFileContent(project, ".source-down/starts", "start\n")
                time.sleep(1.1)
                self.assertFileContent(project, ".source-down/starts", "start\n")

                project.replaceFile("docs/plugin.py", fromPath="target/replacement.py")
                index = ".source-down/search/index.json"
                watch.waitForOutputState(filesPresent=[index])
                self.assertIn(b"Atomic repair proof", project.readBytes(".source-down/pages/docs/index.md.md"))
                self.assertIndexIncludesDependency(project.readBytes(index), owner="check", dependency={
                    "kind": "file", "path": "docs/plugin.py",
                })
                # 首次故障、取得新依赖的候选、具有轮前依赖事实的发布各启动一次。
                self.assertFileContent(project, ".source-down/starts", "start\nstart\nstart\n")
                found = project.sourceDown.searchSuccessfully("Atomic repair")
                self.assertIn(b"Atomic repair proof", found.raw.stdout)

                project.writeInPlace("docs/plugin.py", healthy)
                time.sleep(1.1)
                self.assertFileContent(project, ".source-down/starts", "start\nstart\nstart\n")
                self.assertNotIn(b"switching to poll", watch.stderr)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130, stdout=b"")
