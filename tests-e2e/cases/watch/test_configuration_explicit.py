# 显式配置缺失时持续等待同一路径，修复后查询仍明确使用该配置。
from support import E2ECase
from support.filesystem import open_read


class ExplicitConfigurationRepair(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """显式缺失配置可修复，二次错误保留旧产物，删除后仍等待同一路径"""
        with self.project({
            "docs/keep.md": "Keep reading\n",
            "docs/extra.md": "Extra chapter\n",
        }) as project:
            with project.sourceDown.watch(inputs=["docs"], config="settings.toml") as watch:
                watch.waitForDiagnostics(contains=["configuration failure; watching"])
                project.writeInPlace("settings.toml", 'config_version=1\n[inputs]\nexclude=["docs/extra.md"]\n')
                index = ".source-down/search/index.json"
                page = ".source-down/pages/docs/keep.md.md"
                extra = ".source-down/pages/docs/extra.md.md"
                watch.waitForOutputState(filesPresent=[index])
                self.assertPathAbsent(project, extra)
                savedIndex, savedPage = project.readBytes(index), project.readBytes(page)

                failure = watch.checkpoint()
                project.writeInPlace("settings.toml", "config_version = false\n")
                watch.waitForDiagnostics(contains=["configuration failure; watching"], since=failure)
                self.assertFileContent(project, index, savedIndex)
                self.assertFileContent(project, page, savedPage)

                with open_read(project.root / index) as held:
                    project.writeInPlace("settings.toml", "config_version=1\n")
                    repaired = watch.waitForOutputState(filesPresent=[extra], indexManifest={
                        index: {"input_files": ["docs/extra.md", "docs/keep.md"]},
                    })
                    self.assertEqual(held.read(), savedIndex)

                beforeRemoval = repaired.files[index]
                failure = watch.checkpoint()
                project.removeFile("settings.toml")
                watch.waitForDiagnostics(contains=["configuration failure; watching"], since=failure)
                project.writeInPlace("settings.toml", "config_version=1\n# repaired explicit configuration\n")
                watch.waitForOutputState(changed={index: beforeRemoval})
                found = project.run(["search", "Keep", "--json", "--config", "settings.toml"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertEqual(watch.stdout, b"")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
