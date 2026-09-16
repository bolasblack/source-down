# 导航通过真实 alias 查询特殊文件名，页面身份仍来自规范目标。
import os
from pathlib import Path
from support import E2ECase


class UnselectedTargets(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-002", "SPEC-CLI-004", "SPEC-SRH-003")

    def test_scenario(self):
        """目标存在或被删除，只要未在本轮选择都拒绝导航并保留完整旧输出。"""
        target = "docs/targets/文件 😀 # % [a] (b) &.md"
        with self.project({target: "", "material.txt": "Only material"}) as project:
            os.symlink(Path(target), project.root / "alias.md")
            project.writeFiles({"docs/deep/index.md": '[next]({% link "alias.md" %})\n'})
            published = project.sourceDown.render(inputs=["docs"], outputDir=".source-down")
            self.assertRunResult(published, exitCode=0)

            # 目标仍存在，但本轮仅选择作者页；旧生成页不能补足目标资格。
            unselected = project.sourceDown.render(inputs=["docs/deep/index.md"])
            self.assertRunResult(unselected, exitCode=1, stderrContains=["error page_not_selected:"])
            self.assertOutputUnchanged(project, since=published)

            # 删除同一真实目标，再次执行同一个选择，保持同一份完整基线。
            (project.root / target).unlink()
            missing = project.sourceDown.render(inputs=["docs/deep/index.md"])
            self.assertRunResult(missing, exitCode=1, stderrContains=["error page_not_selected:"])
            self.assertOutputUnchanged(project, since=published)
