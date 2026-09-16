# 本例执行实施前批准的一条查询；每个输出根独立生成后再查询和读回。
# {% include "docs/engineering/search-queries.json" %}
# 删除 kind 过滤后保留原排序：仅取首项，验证完整函数来源，不限定 kind 或 occurrence 页面。
from support import SourceRegion
from support.project import SelfUseCase


class QueryCodeSpan(SelfUseCase):
    specs = ('SPEC-SRH-003', 'SPEC-SRH-004', 'SPEC-SRH-005', 'SPEC-SRH-006')

    def test_scenario(self):
        """查询 code_span 在两个输出根命中并能按句柄准确读回"""
        declarations = self.declaredSearchQueries()
        self.assertEqual(len(declarations), 5)
        self.assertEqual(declarations[4], {'query': 'code_span', 'path': 'src/render.rs', 'kind': 'code', 'top_k': 1, 'expected_input': 'src/render.rs', 'reason': 'The complete identifier should locate the framing implementation.'})

        with self.selfUseProject() as project:
            for outputDir in (".source-down", "custom-reading"):
                project.sourceDown.renderSuccessfully(
                    inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
                    outputDir=outputDir,
                )
                with self.subTest(output=outputDir):
                    found = project.sourceDown.search(
                        'code_span', path='src/render.rs', limit=1,
                        outputDir=outputDir,
                    )
                    self.assertSearchResult(found, exitCode=0, freshness="matched")
                    expectedFunction = SourceRegion.between(
                        "src/render.rs", original=project.readBytes("src/render.rs"),
                        start=b"\npub fn code_span(", end=b"\n}", skipStart=1, includeEnd=True,
                    )
                    self.assertSearchResult(found, returned=1)
                    hit = self.assertOnlyHit(found, sourceSpans=[expectedFunction], sourceTotal=1)
                    current = project.sourceDown.read(hit.handle, outputDir=outputDir)
                    self.assertReadResult(
                        current, exitCode=0, snapshot=found.snapshot,
                        startsAt=0, contentIncludes=[hit.snippet],
                    )
                    self.assertReadResult(
                        current, contentIncludes=[expectedFunction.content],
                        sourceSpans=[expectedFunction],
                    )
                    self.assertCurrentSourceLinks(project, current)

                    historical = project.sourceDown.read(hit.handle, snapshot=True, outputDir=outputDir)
                    self.assertReadResult(
                        historical, exitCode=0, freshness="unchecked", sameBodyAs=current,
                    )
                    self.assertNoCurrentLinks(historical, sources=True)
