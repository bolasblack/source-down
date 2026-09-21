# 目录依赖只保存成员身份，递归不能跟随成员链接或打开 FIFO。
# {% include "tests-e2e/fixtures/search/directory_facts.py" %}
import os
import stat
from urllib.parse import quote
from support import E2ECase
from support.protocol import writeReportReply
from .fixtures import directoryFactsPluginFiles


class DirectoryMembers(E2ECase):
    specs = ("SPEC-SRH-002",)
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """目录快照保存链接和 FIFO 类型，目标树变化保持新鲜，链接与成员类型变化使其过期"""
        with self.project({"outside.txt": "Outside\n"}) as outside, self.project({
            "input.md": "needle\n", "target/a file.txt": "Target\n",
            "assets/nested/inside.txt": "Inside\n",
            **directoryFactsPluginFiles(self, dependencies=[
                {"kind": "directory", "path": "assets", "recursive": True},
                {"kind": "directory", "path": "assets", "recursive": False},
            ]),
        }) as project:
            project.symlink("assets/directory", target="../target", directory=True)
            project.symlink("assets/link name", target="../target/a file.txt")
            project.symlink("assets/outside", target=outside.root, directory=True)
            os.mkfifo(project.root / "assets/pipe")
            writeReportReply(project, reports={}, diagnostics=[])
            published = project.sourceDown.renderSuccessfully(inputs=["input.md"])
            direct = [
                {"path": "assets/directory", "node": {"kind": "symlink", "target": "../target"}},
                {"path": "assets/link%20name", "node": {"kind": "symlink", "target": "../target/a%20file.txt"}},
                {"path": "assets/nested", "node": {"kind": "directory"}},
                {"path": "assets/outside", "node": {"kind": "symlink", "target": quote(str(outside.root), safe="/.-_~")}},
                {"path": "assets/pipe", "node": {"kind": "other", "mode": stat.S_IFIFO}},
            ]
            recursive = direct[:3] + [{"path": "assets/nested/inside.txt", "node": {"kind": "file"}}] + direct[3:]
            facts = published.index.data["manifest"]["dependencies"]["project"]
            self.assertEqual(len(facts), 2)
            for fact, recurse, entries in zip(facts, [False, True], [direct, recursive], strict=True):
                self.assertEqual(fact, {"dependency": {"kind": "directory", "path": "assets", "recursive": recurse},
                                        "resolved": "assets", "links": [],
                                        "state": {"kind": "directory", "entries": entries}})

            project.writeInPlace("target/a file.txt", "Changed target bytes\n")
            project.writeFiles({"target/new.txt": "New target member\n"})
            outside.writeFiles({"new.txt": "New outside member\n"})
            project.writeInPlace("assets/nested/inside.txt", "Changed member contents\n")
            found = project.sourceDown.search("needle")
            self.assertSearchResult(found, exitCode=0, freshness="matched", returned=1)
            self.assertOutputUnchanged(project, since=published)

            project.removeFile("assets/link name")
            project.symlink("assets/link name", target="../target/new.txt")
            stale = project.sourceDown.search("needle")
            self.assertRunResult(stale, exitCode=1, stdout=b"", stderrContains=["stale search index"])
            self.assertOutputUnchanged(project, since=published)

            refreshed = project.sourceDown.renderSuccessfully(inputs=["input.md"])
            project.removeFile("assets/pipe")
            project.writeFiles({"assets/pipe": "now an ordinary file"})
            stale = project.sourceDown.search("needle")
            self.assertRunResult(stale, exitCode=1, stdout=b"", stderrContains=["stale search index"])
            self.assertOutputUnchanged(project, since=refreshed)
