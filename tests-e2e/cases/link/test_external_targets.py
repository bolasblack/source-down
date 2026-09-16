# 导航通过真实 alias 查询特殊文件名，页面身份仍来自规范目标。
import os
from pathlib import Path
from support import E2ECase


class ExternalTargets(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-002", "SPEC-CLI-004", "SPEC-SRH-003")

    def test_scenario(self):
        """真实符号链接指向另一个项目时拒绝越界目标，并保留完整旧输出。"""
        target = "docs/targets/文件 😀 # % [a] (b) &.md"
        with self.project({target: "", "material.txt": "Only material"}) as project:
            os.symlink(Path(target), project.root / "alias.md")
            project.writeFiles({"docs/deep/index.md": '[next]({% link "alias.md" %})\n'})
            published = project.sourceDown.render(inputs=["docs"], outputDir=".source-down")
            self.assertRunResult(published, exitCode=0)

            with self.project({"outside.md": "Outside"}) as outside:
                os.symlink(outside.root / "outside.md", project.root / "outside.md")
                project.writeInPlace("docs/deep/index.md", '{% link "outside.md" %}\n')
                rejected = project.sourceDown.render(inputs=["docs/deep/index.md"])
                self.assertRunResult(rejected, exitCode=1, stderrContains=["error source_error:"])
                self.assertOutputUnchanged(project, since=published)
