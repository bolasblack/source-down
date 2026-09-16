# 一次成功生成后引用缺失材料，检查失败应保留先前的页面与索引。
from support import E2ECase


class MissingMaterial(E2ECase):
    specs = ('SPEC-BLT-002', 'SPEC-CLI-004')

    def test_scenario(self):
        """材料缺失时保留上次页面和搜索快照"""
        with self.project({
            "main.rs": "// Original prose\nfn main() {}\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(
                inputs=["main.rs"],
                includesFiles=["pages/main.rs.md", "search/index.json"],
            )

            project.writeInPlace("main.rs", '// {% include "missing.md" %}\nfn main() {}\n')
            rejected = project.sourceDown.render(inputs=["main.rs"])

            self.assertRunResult(
                rejected, exitCode=1, stdout=b"", stderrContains=["missing.md"],
            )
            self.assertOutputUnchanged(project, since=published, files=[
                "pages/main.rs.md", "search/index.json",
            ])
