# 导航通过真实 alias 查询特殊文件名，页面身份仍来自规范目标。
import os
from pathlib import Path
from support import E2ECase


class MaterialTargets(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-002", "SPEC-CLI-004", "SPEC-SRH-003")

    def test_scenario(self):
        """include 已读取的材料仍不具备页面资格，link 失败并保留完整旧输出。"""
        target = "docs/targets/文件 😀 # % [a] (b) &.md"
        with self.project({target: "", "material.txt": "Only material"}) as project:
            os.symlink(Path(target), project.root / "alias.md")
            project.writeFiles({"docs/deep/index.md": '[next]({% link "alias.md" %})\n'})
            published = project.sourceDown.render(inputs=["docs"], outputDir=".source-down")
            self.assertRunResult(published, exitCode=0)

            project.writeInPlace("docs/deep/index.md", '{% include "material.txt" %}\n{% link "material.txt" %}\n')
            rejected = project.sourceDown.render(inputs=["docs/deep/index.md"])
            self.assertRunResult(rejected, exitCode=1, stderrContains=["error page_not_selected:"])
            self.assertOutputUnchanged(project, since=published)
