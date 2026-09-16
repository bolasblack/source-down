# 删除默认配置会恢复默认值；坏配置期间旧发布保持可读。
from support import E2ECase
from support.filesystem import open_read


class ConfigurationRepair(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """默认配置从语法错误恢复，二次错误保留旧产物，删除后恢复默认配置"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/extra.md": "Extra chapter\n",
            "source-down.toml": "[broken TOML\n",
        }) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["configuration failure; watching"])
                project.writeInPlace("source-down.toml", 'config_version=1\n[inputs]\nexclude=["docs/extra.md"]\n')
                index = ".source-down/search/index.json"
                page = ".source-down/pages/docs/keep.md.md"
                extra = ".source-down/pages/docs/extra.md.md"
                watch.waitForOutputState(filesPresent=[index])
                self.assertPathAbsent(project, extra)
                savedIndex, savedPage = project.readBytes(index), project.readBytes(page)

                failure = watch.checkpoint()
                project.writeInPlace("source-down.toml", "config_version = false\n")
                watch.waitForDiagnostics(contains=["configuration failure; watching"], since=failure)
                self.assertFileContent(project, index, savedIndex)
                self.assertFileContent(project, page, savedPage)

                with open_read(project.root / index) as held:
                    project.writeInPlace("source-down.toml", "config_version=1\n")
                    repaired = watch.waitForOutputState(filesPresent=[extra], indexManifest={
                        index: {"input_files": ["docs/extra.md", "docs/keep.md"]},
                    })
                    self.assertEqual(held.read(), savedIndex)

                beforeRemoval = repaired.files[index]
                project.removeFile("source-down.toml")
                removed = watch.waitForOutputState(changed={index: beforeRemoval})
                self.assertIndexManifest(removed.files[index], fields={"config_sources": {}})
                found = project.sourceDown.search("Keep")
                self.assertRunResult(found, exitCode=0)
                self.assertEqual(watch.stdout, b"")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
