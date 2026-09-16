# Full content, rather than size or mtime, decides whether watch starts a new round.
# {% include "tests-e2e/fixtures/watch/observer.py" %}
import time
from support import E2ECase


class ContentChanges(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-MOD-004", "SPEC-PLG-003", "SPEC-SRH-003")

    def test_scenario(self):
        """同大小同 mtime 的正文更新页面和索引，静止时不重复运行插件"""
        with self.project({
            "docs/index.md": "needle before\n",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/observer.py"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                index = ".source-down/search/index.json"
                watch.waitForOutputState(filesPresent=[index])
                watch.waitForDiagnostics(contains=["watching"])
                page = ".source-down/pages/docs/index.md.md"
                oldIndex = project.readBytes(index)
                source = project.root / "docs/index.md"
                original = source.stat()

                project.writePreservingTimes("docs/index.md", "needle after!\n")
                self.assertEqual(source.stat().st_size, original.st_size)
                self.assertEqual(source.stat().st_mtime_ns, original.st_mtime_ns)
                watch.waitForOutputState(contains={page: "needle after!\n"})
                watch.waitForOutputState(changed={index: oldIndex})

                found = project.sourceDown.search("after")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"after!", found.raw.stdout)
                expectedEvents = b"initialize\nrun\nrun\n"
                self.assertFileContent(project, ".source-down/observer.events", expectedEvents)
                stableIndex = project.readBytes(index)
                time.sleep(1.1)
                self.assertFileContent(project, ".source-down/observer.events", expectedEvents)
                self.assertFileContent(project, index, stableIndex)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
