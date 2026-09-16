# 修改真实项目插件脚本后，声明的文件依赖触发重载并更新页面与索引。
from support.project import SelfUseCase


class ProjectCode(SelfUseCase):
    specs = ("SPEC-CLI-011", "SPEC-PLG-013", "SPEC-SRH-003")

    def test_scenario(self):
        """随仓 Python 插件声明自身脚本，修改实际插件代码后自动重新加载并生成准确正文"""
        with self.selfUseProject() as project:
            project.writeFiles({
                "watch.md": "{% package %}\n",
                "source-down.toml": (
                    'config_version=1\n[plugins.project]\n'
                    'command=["python","tools/project_docs.py"]\n'
                    'directives=["package"]\n'
                ),
            })
            with project.sourceDown.watch(inputs=["watch.md"]) as watch:
                watch.waitForOutputState(filesPresent=[".source-down/search/index.json"])
                self.assertIn(b"Package:", project.readBytes(".source-down/pages/watch.md.md"))
                previous = project.readBytes(".source-down/search/index.json")
                self.assertIndexIncludesDependency(previous, owner="project", dependency={
                    "kind": "file", "path": "tools/project_docs.py",
                })
                project.replaceBytes("tools/project_docs.py", b'else "Package"', b'else "Updated project"')
                watch.waitForOutputState(
                    contains={".source-down/pages/watch.md.md": "Updated project:"},
                    changed={".source-down/search/index.json": previous},
                )
                found = project.sourceDown.searchSuccessfully("Updated project")
                self.assertIn(b"Updated project", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
