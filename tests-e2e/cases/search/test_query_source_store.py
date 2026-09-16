# 本例执行实施前批准的一条查询；每个输出根独立生成后再查询和读回。
# {% include "docs/engineering/search-queries.json" %}
from support.project import SelfUseCase


class QuerySourceStore(SelfUseCase):
    specs = ('SPEC-SRH-003', 'SPEC-SRH-004', 'SPEC-SRH-005', 'SPEC-SRH-006')

    def test_scenario(self):
        """查询 SourceStore 在两个输出根命中并能按句柄准确读回"""
        declarations = self.declaredSearchQueries()
        self.assertEqual(len(declarations), 5)
        self.assertEqual(declarations[3], {'query': 'SourceStore', 'path': 'src/model.rs', 'kind': 'code', 'top_k': 1, 'expected_input': 'src/model.rs', 'reason': 'The actual type and its source ownership implementation.'})

        with self.selfUseProject() as project:
            for outputDir in (".source-down", "custom-reading"):
                project.sourceDown.renderSuccessfully(
                    inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
                    outputDir=outputDir,
                )
                with self.subTest(output=outputDir):
                    found = project.sourceDown.search(
                        'SourceStore', path='src/model.rs', limit=1,
                        outputDir=outputDir,
                    )
                    self.assertSearchResult(found, exitCode=0, freshness="matched")
                    hit = self.assertMatchingHit(
                        found, kind='code', inputPath='src/model.rs',
                    )
                    current = project.sourceDown.read(hit.handle, outputDir=outputDir)
                    self.assertReadResult(
                        current, exitCode=0, snapshot=found.snapshot,
                        startsAt=0, contentIncludes=[hit.snippet],
                    )
                    self.assertCurrentSourceLinks(project, current)

                    historical = project.sourceDown.read(hit.handle, snapshot=True, outputDir=outputDir)
                    self.assertReadResult(
                        historical, exitCode=0, freshness="unchecked", sameBodyAs=current,
                    )
                    self.assertNoCurrentLinks(historical, sources=True)
