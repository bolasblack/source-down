# A plugin observes seven directory facts, including the reader's own output.
# Each complete report set determines whether a file blocks its child path.
# {% include "tests-e2e/fixtures/search/directory_facts.py" %}
# {% include "tests-e2e/fixtures/plugin_wire.py" %}
# {% include "tests-e2e/cases/search/fixtures.py" %}
from support import E2ECase
from support.protocol import writeReportReply
from .fixtures import directoryFactsPluginFiles


class PublicationFacts(E2ECase):
    specs = ("SPEC-SRH-002", "SPEC-SRH-003", "SPEC-CLI-004")

    def test_generated_directory_facts_match_the_published_files(self):
        """Search remains fresh after creating outputs and pruning an old report."""
        with self.project({
            "input.md": "needle\n",
            **directoryFactsPluginFiles(self, dependencies=[
                {"kind": "directory", "path": ".", "recursive": True},
                {"kind": "directory", "path": "review", "recursive": False},
                {"kind": "directory", "path": "review/search/index.json", "recursive": True},
                {"kind": "directory", "path": "review/search/index.json/child", "recursive": False},
                {"kind": "directory", "path": "review/reports/project/summary.md", "recursive": False},
                {"kind": "directory", "path": "review/reports/project/summary.md/child", "recursive": True},
                {"kind": "directory", "path": "missing/child", "recursive": False},
            ]),
        }) as project:
            writeReportReply(project, reports={
                "summary": {"markdown": "needle report", "sources": []},
            }, diagnostics=[])
            published = project.sourceDown.renderSuccessfully(inputs=["input.md"], outputDir="review")
            self.assertIndexDirectoryFacts(published, owner="project", includes={
                "review/search/index.json/child": {"kind": "missing", "reason": "NotADirectory"},
                "review/reports/project/summary.md/child": {"kind": "missing", "reason": "NotADirectory"},
                "missing/child": {"kind": "missing", "reason": "NotFound"},
            })
            beforeSearch = project.captureOutput(outputDir="review")
            found = project.sourceDown.search("needle", outputDir="review")
            self.assertSearchResult(found, exitCode=0, totalMatches=2)
            self.assertOutputUnchanged(project, since=beforeSearch)

            # An empty complete report set withdraws summary and unblocks its child.
            writeReportReply(project, reports={}, diagnostics=[])
            withdrawn = project.sourceDown.render(inputs=["input.md"], outputDir="review")
            self.assertRunResult(withdrawn, exitCode=0)
            self.assertPathAbsent(project, "review/reports/project/summary.md")
            self.assertIndexDirectoryFacts(withdrawn, owner="project", includes={
                "review/reports/project/summary.md/child": {"kind": "missing", "reason": "NotFound"},
            })
            found = project.sourceDown.search("needle", outputDir="review")
            self.assertSearchResult(found, exitCode=0, totalMatches=1)

            # Unrelated members still participate in directory freshness.
            project.writeInPlace("review/search/untracked.txt", "new member\n")
            stale = project.sourceDown.search("needle", outputDir="review")
            self.assertRunResult(stale, exitCode=1, stderrContains=["stale search index"])
