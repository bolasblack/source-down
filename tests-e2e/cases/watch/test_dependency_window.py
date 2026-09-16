# The response cannot publish material bytes that changed after the plugin read them.
# {% include "tests-e2e/fixtures/watch/dependency_window.py" %}
from support import E2ECase


class DependencyWindow(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-013", "SPEC-SRH-003")

    def test_scenario(self):
        """旧材料读取与响应之间发生变化时丢弃候选并发布下一轮准确字节"""
        with self.project({
            "docs/index.md": "{% material %}\n",
            "material.bin": b"\x00\xff",
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "plugin.py": self.fixture("watch/dependency_window.py"),
            "source-down.toml": 'config_version=1\n[plugins.material]\ncommand=["python","plugin.py"]\ndirectives=["material"]\n',
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                firstReady = ".source-down/read1.ready"
                page = ".source-down/pages/docs/index.md.md"
                index = ".source-down/search/index.json"
                watch.waitForOutputState(filesPresent=[firstReady])
                self.assertFileContent(project, firstReady, b"00ff")
                self.assertPathAbsent(project, page)

                project.writeInPlace("material.bin", b"\x00\xfe")
                project.writeInPlace(".source-down/read1.release", "continue")
                watch.waitForDiagnostics(contains=["candidate not published"])
                secondReady = ".source-down/read2.ready"
                watch.waitForOutputState(filesPresent=[secondReady])
                self.assertPathAbsent(project, page)
                self.assertPathAbsent(project, index)
                self.assertFileContent(project, secondReady, b"00fe")

                project.writeInPlace(".source-down/read2.release", "continue")
                watch.waitForOutputState(filesPresent=[index, page])
                self.assertIn(b"Material 00fe", project.readBytes(page))
                self.assertNotIn(b"Material 00ff", project.readBytes(page))
                found = project.sourceDown.search("00fe")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"Material 00fe", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
