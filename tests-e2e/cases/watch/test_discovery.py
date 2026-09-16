# 目录选择每轮重新发现文件；只清理本次 watch 拥有的已退出页面。
from support import E2ECase


class InputDiscovery(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """目录新增、重命名和删除更新当前页面集合，其他调用的页面保持原值"""
        with self.project({"docs/keep.md": "Keep reading\n", "docs/before.md": "needle before\n"}) as project:
            project.writeFiles({"reading/nested/pages/other.md.md": "Another invocation\n"})
            with project.sourceDown.watch(inputs=["docs"], outputDir="reading/nested") as watch:
                index = "reading/nested/search/index.json"
                pages = "reading/nested/pages/docs"
                watch.waitForOutputState(filesPresent=[index])
                original = project.readBytes(index)
                project.writeInPlace("docs/added.py", "# needle added\ndef value():\n    return 7\n")
                added = watch.waitForOutputState(filesPresent=[f"{pages}/added.py.md"], changed={index: original})
                self.assertIndexManifest(added.files[index], fields={
                    "input_files": ["docs/added.py", "docs/before.md", "docs/keep.md"],
                })

                (project.root / "docs/before.md").rename(project.root / "docs/renamed.md")
                watch.waitForOutputState(filesPresent=[f"{pages}/renamed.md.md"], absent=[f"{pages}/before.md.md"])
                project.removeFile("docs/added.py")
                watch.waitForOutputState(absent=[f"{pages}/added.py.md"])
                watch.waitForOutputState(indexManifest={
                    index: {"input_files": ["docs/keep.md", "docs/renamed.md"]},
                })

                found = project.sourceDown.search("needle", outputDir="reading/nested")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"needle before", found.raw.stdout)
                self.assertFileContent(project, "reading/nested/pages/other.md.md", b"Another invocation\n")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
