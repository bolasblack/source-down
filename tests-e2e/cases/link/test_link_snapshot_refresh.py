# 默认读取核对当前事实；作者 fragment 改变后，旧句柄必须等待重新生成。
from support import E2ECase


class LinkSnapshotRefresh(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-SRH-001", "SPEC-SRH-003", "SPEC-SRH-006")

    def test_scenario(self):
        """作者 fragment 改变使旧快照读取失败，原输出保持，重新生成后正文更新。"""
        original = 'needle [下一篇]({% link "docs/details.md" %}#manual)\r\n'
        expected = 'needle [下一篇](details.md.md#manual)\r\n'
        with self.project({"docs/index.md": original, "docs/details.md": ""}) as project:
            for output in (".source-down", "nested/reading"):
                initial = project.sourceDown.render(inputs=["docs"], outputDir=output)
                self.assertRunResult(initial, exitCode=0)
                found = project.run(["search", "needle", "--limit", "1", "--json", "--output-dir", output])
                self.assertRunResult(found, exitCode=0)
                hit = self.assertOnlyHit(found)
                originalRead = project.run(["read", hit.handle, "--json", "--output-dir", output])
                self.assertRunResult(originalRead, exitCode=0)
                self.assertReadText(originalRead, equals=expected)
                published = project.captureOutput(outputDir=output)

                project.writeInPlace("docs/index.md", original.replace("manual", "changed"))
                stale = project.run(["read", hit.handle, "--json", "--output-dir", output])
                self.assertRunResult(stale, exitCode=1, stdout=b"", stderrContains=["render"])
                self.assertOutputUnchanged(project, since=published)

                repaired = project.sourceDown.render(inputs=["docs"], outputDir=output)
                self.assertRunResult(repaired, exitCode=0)
                self.assertPageContent(repaired, "pages/docs/index.md.md", contains=[
                    "needle [下一篇](details.md.md#changed)\r\n",
                ])
                project.writeInPlace("docs/index.md", original)
