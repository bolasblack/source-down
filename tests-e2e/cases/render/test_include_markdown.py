# 作者在源码中引用项目说明；页面按作者顺序展示材料和后续代码。
from support import E2ECase


class IncludeMarkdown(E2ECase):
    specs = ('SPEC-BLT-003', 'SPEC-REN-007')

    def test_scenario(self):
        """render 在指令位置展开 Markdown 材料"""
        with self.project({
            "main.rs": '// {% include "guide.md" %}\nfn main() {}\n',
            "guide.md": "这里是项目说明。\n",
        }) as project:
            reading = project.sourceDown.renderSuccessfully(inputs=["main.rs"])

            self.assertPageContent(
                reading,
                "pages/main.rs.md",
                containsInOrder=["这里是项目说明。\n", "fn main() {}\n"],
            )
