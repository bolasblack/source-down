# 查询当前事实时非法配置仍是 usage/configuration failure，不能降为普通快照过期。
from support import E2ECase


class InvalidConfiguration(E2ECase):
    specs = ("SPEC-SRH-003",)

    def test_scenario(self):
        """默认搜索与句柄读对非法配置退出 2，快照读保留旧内容，修复配置后恢复"""
        valid = "config_version=1\n"
        with self.project({"guide.md": "needle original\n", "source-down.toml": valid}) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["guide.md"])
            handle = project.sourceDown.searchSuccessfully("needle").hits[0].handle
            for invalid in ["config_version=2\n", "config_version=1\nunknown=true\n",
                            "[broken\n", "config_version=1\n[plugins.demo]\ncommand=[]\n"]:
                with self.subTest(config=invalid):
                    project.writeInPlace("source-down.toml", invalid)
                    for operation in ["search", "read"]:
                        with self.subTest(operation=operation):
                            result = (project.sourceDown.search("needle") if operation == "search"
                                      else project.sourceDown.read(handle))
                            self.assertRunResult(result, exitCode=2, stdout=b"", stderrContains=["source-down.toml"])
                    historical = project.sourceDown.read(handle, snapshot=True)
                    self.assertReadResult(historical, exitCode=0, freshness="unchecked", content=b"needle original\n")
                    self.assertNoCurrentLinks(historical, sources=True, occurrences=True)
                    self.assertOutputUnchanged(project, since=published)

            project.writeInPlace("source-down.toml", valid)
            project.sourceDown.searchSuccessfully("needle")
            current = project.sourceDown.read(handle)
            self.assertReadResult(current, exitCode=0, freshness="matched", content=b"needle original\n")
            self.assertOutputUnchanged(project, since=published)
