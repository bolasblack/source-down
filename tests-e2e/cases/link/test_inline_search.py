# 搜索读回作者的完整内联正文与独立 URL，只有保留的作者字节具有逐字来源映射。
from support import E2ECase


class InlineSearch(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-SRH-001", "SPEC-SRH-003", "SPEC-SRH-006")

    def test_scenario(self):
        """两个输出位置都能搜索读回内联正文和 URL，并保持作者字节映射。"""
        original = 'needle [下一篇]({% link "docs/details.md" %}#manual)\r\n'
        expected = 'needle [下一篇](details.md.md#manual)\r\n'
        with self.project({"docs/index.md": original, "docs/details.md": ""}) as project:
            for output in (".source-down", "nested/reading"):
                reading = project.sourceDown.render(inputs=["docs"], outputDir=output)
                self.assertRunResult(reading, exitCode=0)

                # needle 只取一个实际命中，直接用该命中的句柄读回完整原句。
                found = project.run([
                    "search", "needle", "--limit", "1", "--json", "--output-dir", output,
                ])
                self.assertRunResult(found, exitCode=0)
                hit = self.assertOnlyHit(found)
                sentence = project.run([
                    "read", hit.handle, "--json", "--output-dir", output,
                ])
                self.assertRunResult(sentence, exitCode=0)
                self.assertReadText(sentence, equals=expected)

                # 第二个查询不限制数量，从真实命中中选择唯一 expansion 再读回。
                found = project.run([
                    "search", "details.md.md", "--json", "--output-dir", output,
                ])
                self.assertRunResult(found, exitCode=0)
                expansion = self.assertOnlyHitOfKind(found, kind="expansion")
                url = project.run([
                    "read", expansion.handle, "--json", "--output-dir", output,
                ])
                self.assertRunResult(url, exitCode=0)
                self.assertReadText(url, equals="details.md.md")

                # URL 是生成的字节；原句中每个实际 mapping 都只映射其余保留原文。
                self.assertAuthoredMappings(
                    reading,
                    text=expected,
                    original=original,
                    generatedText="details.md.md",
                    prefix="needle [下一篇](",
                )
