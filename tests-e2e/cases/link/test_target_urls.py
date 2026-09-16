# 导航通过真实 alias 查询特殊文件名，页面身份仍来自规范目标。
import os
from pathlib import Path
from urllib.parse import unquote
from support import E2ECase


class TargetUrls(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-002", "SPEC-CLI-004", "SPEC-SRH-003")

    def test_scenario(self):
        """特殊文件名的完整 URL 在两个输出根准确定位规范页面，依赖保留 alias 查询拼写。"""
        target = "docs/targets/文件 😀 # % [a] (b) &.md"
        with self.project({target: "", "material.txt": "Only material"}) as project:
            os.symlink(Path(target), project.root / "alias.md")
            project.writeFiles({"docs/deep/index.md": '[next]({% link "alias.md" %})\n'})
            expected = "../targets/%E6%96%87%E4%BB%B6%20%F0%9F%98%80%20%23%20%25%20%5Ba%5D%20%28b%29%20%26.md.md"
            for output in (".source-down", "other/output"):
                reading = project.sourceDown.render(inputs=["docs"], outputDir=output)
                self.assertRunResult(reading, exitCode=0)
                self.assertExpansionTexts(reading, equals=[expected])
                self.assertPageContent(reading, "pages/docs/deep/index.md.md", contains=["[next](" + expected + ")"])
                self.assertEqual(
                    (reading.outputRoot / "pages/docs/deep" / unquote(expected)).resolve(),
                    (reading.outputRoot / "pages" / (target + ".md")).resolve(),
                )
                self.assertIndexDependencies(reading, owner="builtin:link", equals=[
                    {"kind": "file", "path": "alias.md"},
                ])
