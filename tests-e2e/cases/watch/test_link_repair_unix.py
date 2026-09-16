# 普通恢复域保存链接文本变化，不把链接目标全文当成未知材料扫描。
# 链接先后指向以下真实失败和健康插件。
# {% include "tests-e2e/fixtures/watch/execution_start_failure.py" %}
# {% include "tests-e2e/fixtures/watch/execution_start_healthy.py" %}
import time
from support import E2ECase


class LinkRepair(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """未声明的脚本链接在首次崩溃后重定向，一次链接替换即可恢复页面和搜索"""
        with self.project({
            "docs/index.md": "Linked repair proof\n",
            "broken.py": self.fixture("watch/execution_start_failure.py"),
            "fixed.py": self.fixture("watch/execution_start_healthy.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","entry"]\n',
        }) as project:
            project.symlink("entry", target="broken.py")
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["execution failure; watching"])
                self.assertFileContent(project, ".source-down/starts", b"start\n")

                replacement = project.root / ".source-down/new-entry"
                replacement.symlink_to("fixed.py")
                replacement.replace(project.root / "entry")
                watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                found = project.sourceDown.searchSuccessfully("Linked repair")
                self.assertIn(b"Linked repair proof", found.raw.stdout)
                self.assertFileContent(project, ".source-down/starts", b"start\nstart\n")
                time.sleep(1.1)  # Reading the link target cannot manufacture another attempt.
                self.assertFileContent(project, ".source-down/starts", b"start\nstart\n")
                self.assertNotIn(b"switching to poll", watch.stderr)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
