# 先生成文档，再搜索其中的原文，通过实际返回的句柄读回完整片段。
from support import E2ECase


class SearchThenRead(E2ECase):
    specs = ('SPEC-SRH-001', 'SPEC-SRH-004', 'SPEC-SRH-005', 'SPEC-SRH-006')

    def test_scenario(self):
        """搜索结果的句柄读回完整原文且不改变生成物"""
        text = "needle 中文正文，保持原文。\n"
        with self.project({"guide.md": text}) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["guide.md"])

            found = project.sourceDown.search("needle", limit=1)
            self.assertSearchResult(found, exitCode=0, freshness="matched", returned=1)
            hit = self.assertOnlyHit(found, kind="prose", handlePattern=r"^[0-9A-Za-z]{11}$")

            read = project.sourceDown.read(hit.handle)
            self.assertCompleteSinglePage(read, text)
            self.assertReadResult(
                read,
                snapshot=found.snapshot,
                handle=hit.handle,
                currentSourceLinkAt={0: "guide.md#L1"},
            )
            self.assertOutputUnchanged(project, since=published)
