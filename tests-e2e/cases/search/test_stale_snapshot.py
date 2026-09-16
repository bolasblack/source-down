# 当前文件改变后，默认读拒绝过期索引；显式快照读取保留旧正文并撤掉当前链接。
from support import E2ECase


class StaleSnapshot(E2ECase):
    specs = ('SPEC-SRH-002', 'SPEC-SRH-003', 'SPEC-SRH-006')

    def test_scenario(self):
        """修改来源后默认查询失败，显式快照仍能读取原文"""
        with self.project({"guide.md": "needle original\n"}) as project:
            rendered = project.sourceDown.render(inputs=["guide.md"])
            self.assertRunResult(rendered, exitCode=0)
            hit = project.sourceDown.searchSuccessfully("needle").hits[0]
            baseline = project.captureOutput()

            project.writeInPlace("guide.md", "needle changed!\n")

            with self.subTest(operation="search current source"):
                stale = project.sourceDown.search("needle")
                self.assertRunResult(stale, exitCode=1, stdout=b"", stderrContains=["render"])

            with self.subTest(operation="read current source"):
                stale = project.sourceDown.read(hit.handle)
                self.assertRunResult(stale, exitCode=1, stdout=b"", stderrContains=["render"])

            historical = project.sourceDown.read(hit.handle, snapshot=True)
            self.assertReadResult(
                historical, exitCode=0, freshness="unchecked", content=b"needle original\n",
            )
            self.assertNoCurrentLinks(historical, sources=True, occurrences=True)
            self.assertOutputUnchanged(project, since=baseline)
