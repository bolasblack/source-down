# 无作者指令的插件仍完成检查；warning 与 error 决定页面发布，非法诊断阻止所有发布。
# {% include "tests-e2e/fixtures/search/directory_facts.py" %}
from support import E2ECase
from support.protocol import writeReportReply
from cases.search.fixtures import directoryFactsPluginFiles


class DiagnosticPublication(E2ECase):
    specs = ("SPEC-MOD-005", "SPEC-PLG-012")

    def test_scenario(self):
        """零请求 warning 发布页面和报告，error 只更新报告，非法诊断保留全部产物"""
        source = {"path": "docs/specs/missing.md", "start_byte": 0, "end_byte": 10,
                  "start_line": 1, "end_line": 1}
        with self.project({
            "a.rs": "// Original page\n", "docs/specs/missing.md": "# Missing\n",
            **directoryFactsPluginFiles(self, dependencies=[]),
        }) as project:
            writeReportReply(project, reports={"coverage": {"markdown": "Original report", "sources": []}}, diagnostics=[])
            project.sourceDown.renderSuccessfully(inputs=["a.rs"])
            original = project.snapshot()

            # A real source edit makes accidental suppression of warning pages observable.
            project.writeInPlace("a.rs", "// Warning page\n")
            diagnostic = {"severity": "warning", "code": "spec.unreferenced",
                          "message": "Missing reference", "sources": [source]}
            writeReportReply(project, reports={"coverage": {"markdown": "Warning report", "sources": [source]}},
                             diagnostics=[diagnostic])
            warning = project.sourceDown.render(inputs=["a.rs"])
            self.assertRunResult(warning, exitCode=0, stdout=b"",
                                 stderrContains=["project", "warning", "spec.unreferenced", "Missing reference", "docs/specs/missing.md:1"])
            warned = project.snapshot()
            self.assertNotEqual(warned["pages/a.rs.md"], original["pages/a.rs.md"])
            self.assertIn(b"Warning page", warned["pages/a.rs.md"])
            self.assertIn(b"Warning report", warned["reports/project/coverage.md"])

            # Same selected file and report name; the changed page must remain unpublished.
            project.writeInPlace("a.rs", "// Error page must stay unpublished\n")
            diagnostic["severity"] = "error"
            writeReportReply(project, reports={"coverage": {"markdown": "Error report", "sources": [source]}},
                             diagnostics=[diagnostic])
            error = project.sourceDown.render(inputs=["a.rs"])
            self.assertRunResult(error, exitCode=1, stdout=b"",
                                 stderrContains=["project", "error", "spec.unreferenced", "docs/specs/missing.md:1", "reports/project/coverage.md"])
            checked = project.snapshot()
            self.assertEqual(checked["pages/a.rs.md"], warned["pages/a.rs.md"])
            self.assertEqual(checked["search/index.json"], warned["search/index.json"])
            self.assertIn(b"Error report", checked["reports/project/coverage.md"])
            self.assertNotEqual(checked["reports/project/coverage.md"], warned["reports/project/coverage.md"])

            for invalid in [dict(diagnostic, severity="notice"),
                            dict(diagnostic, sources=[dict(source, path="absent.md")])]:
                with self.subTest(diagnostic=invalid):
                    writeReportReply(project, reports={"coverage": {"markdown": "Must not publish", "sources": []}},
                                     diagnostics=[invalid])
                    failed = project.sourceDown.render(inputs=["a.rs"])
                    self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=["project"])
                    self.assertEqual(project.snapshot(), checked)
